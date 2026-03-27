"""Automatic insights system — generates executive HTML report."""

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Template

from src.data_loader import load_all

OUTPUT_DIR = Path(__file__).parent / "reports"

# ── Insight Detectors ───────────────────────────────────────────


def detect_anomalies(df: pd.DataFrame, week_labels: list[str], threshold: float = 0.10) -> pd.DataFrame:
    """Flag zones with drastic week-over-week changes (>threshold).

    Uses abs((L0W - L1W) / L1W) > threshold.
    """
    if len(week_labels) < 2:
        return pd.DataFrame()
        
    current_week = week_labels[-1]
    prev_week = week_labels[-2]
    
    result = df[["COUNTRY", "CITY", "ZONE", "METRIC", prev_week, current_week]].copy()
    result["wow_change"] = (result[current_week] - result[prev_week]) / result[prev_week].replace(0, float("nan"))
    result["abs_change"] = result["wow_change"].abs()
    anomalies = result[result["abs_change"] > threshold].copy()
    anomalies = anomalies.sort_values("abs_change", ascending=False)
    anomalies["direction"] = anomalies["wow_change"].apply(
        lambda x: "improvement" if x > 0 else "deterioration"
    )
    anomalies["wow_change_pct"] = (anomalies["wow_change"] * 100).round(2)
    return anomalies.drop(columns=["abs_change"])


def detect_concerning_trends(df: pd.DataFrame, week_labels: list[str], consecutive_weeks: int = 3) -> pd.DataFrame:
    """Flag metrics decreasing for N+ consecutive weeks."""
    results = []

    for _, row in df.iterrows():
        values = [row[col] for col in week_labels if pd.notna(row[col])]
        if len(values) < consecutive_weeks + 1:
            continue

        streak = 0
        for i in range(1, len(values)):
            if values[i] < values[i - 1]:
                streak += 1
            else:
                streak = 0

        if streak >= consecutive_weeks:
            results.append({
                "COUNTRY": row["COUNTRY"],
                "CITY": row["CITY"],
                "ZONE": row["ZONE"],
                "METRIC": row["METRIC"],
                "consecutive_decline_weeks": streak,
                "start_value": round(values[-(streak + 1)], 4),
                "end_value": round(values[-1], 4),
                "total_decline_pct": round(
                    ((values[-1] - values[-(streak + 1)]) / abs(values[-(streak + 1)])) * 100, 2
                ) if values[-(streak + 1)] != 0 else None,
            })

    return pd.DataFrame(results).sort_values(
        "consecutive_decline_weeks", ascending=False
    ) if results else pd.DataFrame()


def benchmark_zones(df: pd.DataFrame, week_labels: list[str]) -> pd.DataFrame:
    """Flag zones performing >1 std below their COUNTRY+ZONE_TYPE group mean."""
    if not week_labels:
        return pd.DataFrame()
        
    current_week = week_labels[-1]
    results = []

    for (country, zone_type, metric), group in df.groupby(
        ["COUNTRY", "ZONE_TYPE", "METRIC"]
    ):
        mean = group[current_week].mean()
        std = group[current_week].std()
        if pd.isna(std) or std == 0:
            continue

        underperformers = group[group[current_week] < (mean - std)]
        for _, row in underperformers.iterrows():
            results.append({
                "COUNTRY": country,
                "ZONE_TYPE": zone_type,
                "CITY": row["CITY"],
                "ZONE": row["ZONE"],
                "METRIC": metric,
                "zone_value": round(row[current_week], 4),
                "group_mean": round(mean, 4),
                "group_std": round(std, 4),
                "z_score": round((row[current_week] - mean) / std, 2),
            })

    return pd.DataFrame(results).sort_values("z_score") if results else pd.DataFrame()


def compute_correlations(df: pd.DataFrame, week_labels: list[str], top_n: int = 10) -> pd.DataFrame:
    """Compute pearson correlations between metrics across zones."""
    if not week_labels:
        return pd.DataFrame()
        
    current_week = week_labels[-1]
    pivot = df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE"],
        columns="METRIC",
        values=current_week,
    )

    if pivot.shape[1] < 2:
        return pd.DataFrame()

    corr = pivot.corr()

    pairs = []
    seen = set()
    for m1 in corr.columns:
        for m2 in corr.columns:
            if m1 >= m2:
                continue
            key = tuple(sorted([m1, m2]))
            if key in seen:
                continue
            seen.add(key)
            val = corr.loc[m1, m2]
            if pd.notna(val):
                pairs.append({
                    "metric_1": m1,
                    "metric_2": m2,
                    "correlation": round(val, 4),
                    "strength": (
                        "strong" if abs(val) > 0.7
                        else "moderate" if abs(val) > 0.4
                        else "weak"
                    ),
                })

    result = pd.DataFrame(pairs)
    if result.empty:
        return pd.DataFrame()
        
    result["abs_corr"] = result["correlation"].abs()
    result = result.sort_values("abs_corr", ascending=False).head(top_n)
    return result.drop(columns=["abs_corr"])


# ── Report Generation ───────────────────────────────────────────

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rappi Operations — Executive Insights Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; color: #333; max-width: 1200px; margin: 0 auto; padding: 40px; }
        h1 { color: #ff441f; border-bottom: 3px solid #ff441f; padding-bottom: 10px; }
        h2 { color: #2c3e50; margin-top: 40px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        h3 { color: #555; }
        .summary { background: #f8f9fa; border-left: 4px solid #ff441f; padding: 20px; margin: 20px 0; border-radius: 4px; }
        .insight { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 12px 0; }
        .insight.deterioration { border-left: 4px solid #e74c3c; }
        .insight.improvement { border-left: 4px solid #27ae60; }
        .insight.warning { border-left: 4px solid #f39c12; }
        .insight.info { border-left: 4px solid #3498db; }
        table { border-collapse: collapse; width: 100%; margin: 16px 0; }
        th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; }
        th { background: #f5f5f5; font-weight: 600; }
        tr:nth-child(even) { background: #fafafa; }
        .metric-tag { background: #e8f4fd; color: #1976d2; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; }
        .timestamp { color: #999; font-size: 0.85em; }
        .recommendation { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 8px; }
    </style>
</head>
<body>
    <h1>📊 Rappi Operations — Executive Insights Report</h1>
    <p class="timestamp">Generated: {{ generated_at }}</p>

    <div class="summary">
        <h2>Executive Summary</h2>
        <ul>
            <li><strong>{{ anomaly_count }}</strong> anomalies detected (>10% week-over-week change)</li>
            <li><strong>{{ trend_count }}</strong> metrics showing concerning downward trends (3+ weeks)</li>
            <li><strong>{{ underperformer_count }}</strong> zones significantly underperforming their peer group</li>
            <li><strong>{{ strong_corr_count }}</strong> strong metric correlations identified</li>
        </ul>
    </div>

    <h2>1. Anomalies — Drastic Week-over-Week Changes</h2>
    <p>Zones with >10% change from last week ({{ prev_week }} to {{ current_week }}). Sorted by magnitude.</p>
    {% if anomalies %}
    <table>
        <tr><th>Country</th><th>Zone</th><th>Metric</th><th>Change</th><th>Direction</th></tr>
        {% for row in anomalies[:20] %}
        <tr>
            <td>{{ row.COUNTRY }}</td>
            <td>{{ row.ZONE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.wow_change_pct }}%</td>
            <td>{{ row.direction }}</td>
        </tr>
        {% endfor %}
    </table>
    {% if anomalies|length > 20 %}
    <p><em>... and {{ anomalies|length - 20 }} more anomalies.</em></p>
    {% endif %}
    {% else %}
    <p>No significant anomalies detected.</p>
    {% endif %}

    <h2>2. Concerning Trends — Consistent Deterioration</h2>
    <p>Metrics declining for 3+ consecutive weeks.</p>
    {% if trends %}
    <table>
        <tr><th>Country</th><th>Zone</th><th>Metric</th><th>Weeks Declining</th><th>Total Decline</th></tr>
        {% for row in trends[:20] %}
        <tr>
            <td>{{ row.COUNTRY }}</td>
            <td>{{ row.ZONE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.consecutive_decline_weeks }}</td>
            <td>{{ row.total_decline_pct }}%</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No concerning trends detected.</p>
    {% endif %}

    <h2>3. Benchmarking — Underperforming Zones</h2>
    <p>Zones performing >1 standard deviation below their country+zone_type peer group ({{ current_week }}).</p>
    {% if underperformers %}
    <table>
        <tr><th>Country</th><th>Zone</th><th>Type</th><th>Metric</th><th>Value</th><th>Group Avg</th><th>Z-Score</th></tr>
        {% for row in underperformers[:20] %}
        <tr>
            <td>{{ row.COUNTRY }}</td>
            <td>{{ row.ZONE }}</td>
            <td>{{ row.ZONE_TYPE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.zone_value }}</td>
            <td>{{ row.group_mean }}</td>
            <td>{{ row.z_score }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No significant underperformers detected.</p>
    {% endif %}

    <h2>4. Metric Correlations</h2>
    <p>Strongest relationships between operational metrics ({{ current_week }}).</p>
    {% if correlations %}
    <table>
        <tr><th>Metric 1</th><th>Metric 2</th><th>Correlation</th><th>Strength</th></tr>
        {% for row in correlations %}
        <tr>
            <td><span class="metric-tag">{{ row.metric_1 }}</span></td>
            <td><span class="metric-tag">{{ row.metric_2 }}</span></td>
            <td>{{ row.correlation }}</td>
            <td>{{ row.strength }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>Not enough data for correlation analysis.</p>
    {% endif %}

    <h2>5. Recommendations</h2>
    <div class="recommendation">
        <ul>
        {% for rec in recommendations %}
            <li>{{ rec }}</li>
        {% endfor %}
        </ul>
    </div>
</body>
</html>
"""


def generate_recommendations(
    anomalies: pd.DataFrame,
    trends: pd.DataFrame,
    underperformers: pd.DataFrame,
) -> list[str]:
    """Generate actionable recommendations based on detected insights."""
    recs = []

    if not anomalies.empty:
        worst = anomalies[anomalies["direction"] == "deterioration"]
        if not worst.empty:
            top = worst.iloc[0]
            recs.append(
                f"Investigate {top['ZONE']} ({top['COUNTRY']}) — "
                f"{top['METRIC']} dropped {abs(top['wow_change_pct'])}% this week."
            )

    if not trends.empty:
        top_trend = trends.iloc[0]
        recs.append(
            f"Urgent attention needed: {top_trend['ZONE']} ({top_trend['COUNTRY']}) — "
            f"{top_trend['METRIC']} has declined for {top_trend['consecutive_decline_weeks']} "
            f"consecutive weeks ({top_trend['total_decline_pct']}% total)."
        )

    if not underperformers.empty:
        worst_z = underperformers.iloc[0]
        recs.append(
            f"Benchmark gap: {worst_z['ZONE']} ({worst_z['COUNTRY']}) is significantly "
            f"underperforming peers on {worst_z['METRIC']} "
            f"(z-score: {worst_z['z_score']})."
        )

    if not recs:
        recs.append("All metrics are within normal ranges. Continue monitoring.")

    return recs


def generate_report(output_path: Path | None = None) -> Path:
    """Run all insight detectors and generate HTML executive report.

    Returns:
        Path to the generated HTML report.
    """
    df_metrics, _, week_labels = load_all()

    anomalies = detect_anomalies(df_metrics, week_labels)
    trends = detect_concerning_trends(df_metrics, week_labels)
    underperformers = benchmark_zones(df_metrics, week_labels)
    correlations = compute_correlations(df_metrics, week_labels)
    recommendations = generate_recommendations(anomalies, trends, underperformers)

    template = Template(REPORT_TEMPLATE)
    html = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        current_week=week_labels[-1] if week_labels else "N/A",
        prev_week=week_labels[-2] if len(week_labels) > 1 else "N/A",
        anomaly_count=len(anomalies),
        trend_count=len(trends),
        underperformer_count=len(underperformers),
        strong_corr_count=len(correlations[correlations["strength"] == "strong"])
        if not correlations.empty else 0,
        anomalies=anomalies.to_dict("records") if not anomalies.empty else [],
        trends=trends.to_dict("records") if not trends.empty else [],
        underperformers=underperformers.to_dict("records") if not underperformers.empty else [],
        correlations=correlations.to_dict("records") if not correlations.empty else [],
        recommendations=recommendations,
    )

    if output_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"insights_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"

    output_path.write_text(html)
    print(f"Report generated: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_report()

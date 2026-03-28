"""Automatic insights system — generates executive HTML report."""

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Template

from src.data_loader import get_dimension_columns, get_metric_column, load_all

OUTPUT_DIR = Path(__file__).parent / "reports"

# ── Configuration ───────────────────────────────────────────────
CONFIG = {
    "ANOMALY_THRESHOLD": 0.20,      # Increased to 20% for better signal
    "MIN_ABS_CHANGE": 0.02,         # Lowered to 0.02 to capture more genuine shifts
    "TREND_WEEKS": 3,
    "BENCHMARK_STD": 1.5,
    "CORRELATION_STRONG": 0.7,
    "CORRELATION_MODERATE": 0.4,
    "TOP_CORRELATIONS": 10,
    "DISPLAY_ROWS": 100,            # Increased significantly to avoid hiding data
}


# ── Insight Detectors ───────────────────────────────────────────

def detect_anomalies(
    df: pd.DataFrame,
    week_labels: list[str],
    dimensions: list[str],
    metric_col: str,
    threshold: float = CONFIG["ANOMALY_THRESHOLD"],
) -> pd.DataFrame:
    """Flag zones with drastic and significant week-over-week changes."""
    if len(week_labels) < 2:
        return pd.DataFrame()

    current_week = week_labels[-1]
    prev_week = week_labels[-2]

    # Deduplicate source data first
    df = df.drop_duplicates(subset=dimensions + [metric_col])

    result = df[dimensions + [metric_col, prev_week, current_week]].copy()
    
    # Calculate changes
    result["abs_diff"] = (result[current_week] - result[prev_week]).abs()
    result["wow_change"] = (result[current_week] - result[prev_week]) / result[prev_week].replace(0, float("nan"))
    
    # Filter for both % threshold AND a minimum absolute delta to remove "near-zero" noise
    mask = (result["wow_change"].abs() > threshold) & (result["abs_diff"] > CONFIG["MIN_ABS_CHANGE"])
    anomalies = result[mask].copy()
    
    # Sort by absolute difference (real world impact) rather than % magnitude
    anomalies = anomalies.sort_values("abs_diff", ascending=False)
    
    anomalies["direction"] = anomalies["wow_change"].apply(
        lambda x: "mejora" if x > 0 else "deterioro"
    )
    # Cap displayed % at 999% to keep UI clean
    anomalies["wow_change_pct"] = (anomalies["wow_change"] * 100).clip(-999, 999).round(2)
    
    return anomalies.drop(columns=["abs_diff"])


def detect_concerning_trends(
    df: pd.DataFrame,
    week_labels: list[str],
    dimensions: list[str],
    metric_col: str,
    consecutive_weeks: int = CONFIG["TREND_WEEKS"],
) -> pd.DataFrame:
    """Flag metrics decreasing for N+ consecutive weeks."""
    results = []
    
    # Deduplicate source
    df = df.drop_duplicates(subset=dimensions + [metric_col])

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
            entry = {dim: row[dim] for dim in dimensions}
            entry.update({
                "METRIC": row[metric_col],
                "consecutive_decline_weeks": streak,
                "start_value": round(values[-(streak + 1)], 4),
                "end_value": round(values[-1], 4),
                "total_decline_pct": round(
                    ((values[-1] - values[-(streak + 1)]) / abs(values[-(streak + 1)])) * 100, 2
                ) if values[-(streak + 1)] != 0 else None,
            })
            results.append(entry)

    return pd.DataFrame(results).sort_values(
        "consecutive_decline_weeks", ascending=False
    ) if results else pd.DataFrame()


def benchmark_zones(
    df: pd.DataFrame,
    week_labels: list[str],
    dimensions: list[str],
    metric_col: str,
    std_deviations: float = CONFIG["BENCHMARK_STD"],
) -> pd.DataFrame:
    """Flag zones performing >N std below their peer group mean."""
    if not week_labels:
        return pd.DataFrame()

    current_week = week_labels[-1]
    results = []
    
    # Deduplicate source
    df = df.drop_duplicates(subset=dimensions + [metric_col])

    class_dim = next((d for d in dimensions if "TYPE" in d or "CATEGORY" in d), None)
    group_dims = [dimensions[0]]
    if class_dim:
        group_dims.append(class_dim)
    group_dims.append(metric_col)

    for keys, group in df.groupby(group_dims):
        if len(group) < 5: continue # Ignore groups too small for stats
        
        mean = group[current_week].mean()
        std = group[current_week].std()
        if pd.isna(std) or std == 0:
            continue

        underperformers = group[group[current_week] < (mean - (std_deviations * std))]
        for _, row in underperformers.iterrows():
            entry = {dim: row[dim] for dim in dimensions}
            entry.update({
                "METRIC": row[metric_col],
                "zone_value": round(row[current_week], 4),
                "group_mean": round(mean, 4),
                "group_std": round(std, 4),
                "z_score": round((row[current_week] - mean) / std, 2),
            })
            results.append(entry)

    return pd.DataFrame(results).sort_values("z_score") if results else pd.DataFrame()


def compute_correlations(
    df: pd.DataFrame, 
    week_labels: list[str], 
    dimensions: list[str],
    metric_col: str,
    top_n: int = CONFIG["TOP_CORRELATIONS"]
) -> pd.DataFrame:
    """Compute pearson correlations between metrics across zones."""
    if not week_labels:
        return pd.DataFrame()
        
    current_week = week_labels[-1]
    pivot = df.pivot_table(
        index=dimensions,
        columns=metric_col,
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
                strength = (
                    "fuerte" if abs(val) >= CONFIG["CORRELATION_STRONG"]
                    else "moderada" if abs(val) >= CONFIG["CORRELATION_MODERATE"]
                    else "débil"
                )
                pairs.append({
                    "metric_1": m1,
                    "metric_2": m2,
                    "correlation": round(val, 4),
                    "strength": strength,
                })

    result = pd.DataFrame(pairs)
    if result.empty:
        return pd.DataFrame()
        
    result["abs_corr"] = result["correlation"].abs()
    result = result.sort_values("abs_corr", ascending=False).head(top_n)
    return result.drop(columns=["abs_corr"])


def detect_growth_opportunities(
    df_orders: pd.DataFrame,
    week_labels: list[str],
    dimensions: list[str],
    top_n: int = 5
) -> pd.DataFrame:
    """Identify zones with highest order growth (start to end)."""
    if len(week_labels) < 2:
        return pd.DataFrame()
        
    first_w = week_labels[0]
    last_w = week_labels[-1]
    
    # Filter only relevant dimension columns that exist in df_orders
    order_dims = [d for d in dimensions if d in df_orders.columns]
    
    df = df_orders.copy()
    # Calculate growth
    df["growth_pct"] = (df[last_w] - df[first_w]) / df[first_w].replace(0, float("nan"))
    df["growth_abs"] = df[last_w] - df[first_w]
    
    top_growth = df.sort_values("growth_pct", ascending=False).head(top_n)
    
    # Basic normalization for display
    top_growth["growth_pct_label"] = (top_growth["growth_pct"] * 100).round(1)
    
    return top_growth[order_dims + ["growth_pct_label", "growth_abs"]]


# ── Report Generation ───────────────────────────────────────────

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rappi Operations — Reporte Ejecutivo de Insights</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; color: #333; max-width: 1200px; margin: 0 auto; padding: 40px; }
        h1 { color: #ff441f; border-bottom: 3px solid #ff441f; padding-bottom: 10px; }
        h2 { color: #2c3e50; margin-top: 40px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
        h3 { color: #555; }
        .summary { background: #f8f9fa; border-left: 4px solid #ff441f; padding: 20px; margin: 20px 0; border-radius: 4px; }
        table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.9em; }
        th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; }
        th { background: #f5f5f5; font-weight: 600; }
        tr:nth-child(even) { background: #fafafa; }
        .metric-tag { background: #e8f4fd; color: #1976d2; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; }
        .growth-tag { background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; }
        .timestamp { color: #999; font-size: 0.85em; }
        .recommendation { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 8px; }
        .note { color: #666; font-style: italic; font-size: 0.85em; }
    </style>
</head>
<body>
    <h1>📊 Rappi Operations — Reporte Ejecutivo</h1>
    <p class="timestamp">Generado: {{ generated_at }}</p>

    <div class="summary">
        <h2>Resumen Ejecutivo</h2>
        <p>Este reporte resume los hallazgos estadísticos más significativos de la semana.</p>
        <ul>
            <li><strong>{{ growth_count }}</strong> zonas con alto crecimiento de órdenes.</li>
            <li><strong>{{ anomaly_count }}</strong> anomalías críticas detectadas.</li>
            <li><strong>{{ trend_count }}</strong> métricas en descenso prolongado.</li>
            <li><strong>{{ underperformer_count }}</strong> zonas con desempeño significativamente bajo.</li>
            <li><strong>{{ correlation_count }}</strong> correlaciones significativas entre métricas.</li>
        </ul>
    </div>

    <h2>1. Oportunidades: Top Crecimiento de Órdenes</h2>
    <p class="note">Zonas con mayor crecimiento porcentual entre {{ start_week }} y {{ current_week }}.</p>
    {% if growth %}
    <table>
        <tr><th>Ubicación</th><th>Crecimiento %</th><th>Incremento Absoluto</th></tr>
        {% for row in growth %}
        <tr>
            <td>{{ row.COUNTRY }} - {{ row.CITY }} - {{ row.ZONE }}</td>
            <td><span class="growth-tag">+{{ row.growth_pct_label }}%</span></td>
            <td>{{ row.growth_abs|int }} órdenes</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}

    <h2>2. Anomalías Críticas (Semana a Semana)</h2>
    <p class="note">Mostrando variaciones >{{ (config.ANOMALY_THRESHOLD * 100)|int }}% de cambio y >{{ config.MIN_ABS_CHANGE }} unidades.</p>
    {% if anomalies %}
    <table>
        <tr><th>Ubicación</th><th>Métrica</th><th>Cambio %</th><th>Dirección</th></tr>
        {% for row in anomalies[:config.DISPLAY_ROWS] %}
        <tr>
            <td>{{ row.COUNTRY }} - {{ row.CITY }} - {{ row.ZONE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.wow_change_pct }}%</td>
            <td>{{ row.direction }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No se detectaron anomalías significativas esta semana.</p>
    {% endif %}

    <h2>3. Deterioro Continuo (3+ Semanas)</h2>
    {% if trends %}
    <table>
        <tr><th>Ubicación</th><th>Métrica</th><th>Semanas</th><th>Descenso Total</th></tr>
        {% for row in trends[:config.DISPLAY_ROWS] %}
        <tr>
            <td>{{ row.COUNTRY }} - {{ row.CITY }} - {{ row.ZONE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.consecutive_decline_weeks }}</td>
            <td>{{ row.total_decline_pct }}%</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No hay tendencias de deterioro consistente detectadas.</p>
    {% endif %}

    <h2>4. Benchmarking: Zonas con Bajo Desempeño</h2>
    <p class="note">Zonas con desempeño >{{ config.BENCHMARK_STD }} desviaciones estándar por debajo de sus pares.</p>
    {% if underperformers %}
    <table>
        <tr><th>Ubicación</th><th>Métrica</th><th>Valor</th><th>Promedio Grupo</th><th>Z-Score</th></tr>
        {% for row in underperformers[:config.DISPLAY_ROWS] %}
        <tr>
            <td>{{ row.COUNTRY }} - {{ row.ZONE }}</td>
            <td><span class="metric-tag">{{ row.METRIC }}</span></td>
            <td>{{ row.zone_value }}</td>
            <td>{{ row.group_mean }}</td>
            <td>{{ row.z_score }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>Todas las zonas operan dentro de los rangos normales de sus pares.</p>
    {% endif %}

    <h2>5. Correlaciones entre Métricas</h2>
    <p class="note">Top {{ config.TOP_CORRELATIONS }} pares de métricas con mayor correlación de Pearson (r >= {{ config.CORRELATION_MODERATE }}).</p>
    {% if correlations %}
    <table>
        <tr><th>Métrica 1</th><th>Métrica 2</th><th>Correlación (r)</th><th>Fuerza</th></tr>
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
    <p>No se detectaron correlaciones significativas entre las métricas disponibles.</p>
    {% endif %}

    <h2>6. Recomendaciones Prioritarias</h2>
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
    growth: pd.DataFrame,
) -> list[str]:
    """Generate actionable recommendations based on detected insights."""
    recs = []

    if not growth.empty:
        top = growth.iloc[0]
        recs.append(
            f"Escalar éxito: {top['ZONE']} ({top['COUNTRY']}) creció un {top['growth_pct_label']}% en órdenes. Investigar estrategia comercial."
        )

    if not anomalies.empty:
        worst = anomalies[anomalies["direction"] == "deterioro"]
        if not worst.empty:
            top = worst.iloc[0]
            recs.append(
                f"Mitigar caída: Revisar caída de {abs(top['wow_change_pct'])}% en {top['METRIC']} para {top['ZONE']}."
            )

    if not underperformers.empty:
        worst_z = underperformers.iloc[0]
        recs.append(
            f"Brecha de desempeño: {worst_z['ZONE']} ({worst_z['COUNTRY']}) está operando muy por debajo del promedio en {worst_z['METRIC']}."
        )

    if not recs:
        recs.append("No hay acciones críticas pendientes. Continuar con el monitoreo estándar.")

    return recs[:3] # Show top 3 max


def generate_report(output_path: Path | None = None) -> tuple[Path, str, dict]:
    """Run all insight detectors and generate HTML executive report.

    Returns:
        (path_to_report, html_content, stats)
    """
    df_metrics, df_orders, week_labels = load_all()
    
    # Normalize column names and week labels globally
    df_metrics.columns = [str(c).upper() for c in df_metrics.columns]
    df_orders.columns = [str(c).upper() for c in df_orders.columns]
    week_labels = [str(w).upper() for w in week_labels]
    
    dimensions = get_dimension_columns(df_metrics, week_labels)
    metric_col = get_metric_column(df_metrics)

    anomalies = detect_anomalies(df_metrics, week_labels, dimensions, metric_col)
    trends = detect_concerning_trends(df_metrics, week_labels, dimensions, metric_col)
    underperformers = benchmark_zones(df_metrics, week_labels, dimensions, metric_col)
    correlations = compute_correlations(df_metrics, week_labels, dimensions, metric_col)
    growth = detect_growth_opportunities(df_orders, week_labels, dimensions)
    recommendations = generate_recommendations(anomalies, trends, underperformers, growth)

    template = Template(REPORT_TEMPLATE)
    html = template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        current_week=week_labels[-1] if week_labels else "N/A",
        start_week=week_labels[0] if week_labels else "N/A",
        prev_week=week_labels[-2] if len(week_labels) > 1 else "N/A",
        config=CONFIG,
        growth_count=len(growth),
        anomaly_count=len(anomalies),
        trend_count=len(trends),
        underperformer_count=len(underperformers),
        correlation_count=len(correlations),
        growth=growth.to_dict("records") if not growth.empty else [],
        anomalies=anomalies.to_dict("records") if not anomalies.empty else [],
        trends=trends.to_dict("records") if not trends.empty else [],
        underperformers=underperformers.to_dict("records") if not underperformers.empty else [],
        correlations=correlations.to_dict("records") if not correlations.empty else [],
        recommendations=recommendations,
    )

    if output_path is None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"reporte_insights_{datetime.now().strftime('%Y%m%d_%H%M')}.html"

    output_path.write_text(html)
    print(f"Report generated: {output_path}")
    
    stats = {
        "anomalies": len(anomalies),
        "trends": len(trends),
        "underperformers": len(underperformers),
        "correlations": len(correlations),
        "growth": len(growth)
    }
    
    return output_path, html, stats


if __name__ == "__main__":
    generate_report()

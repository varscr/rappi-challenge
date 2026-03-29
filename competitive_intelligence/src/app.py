"""Competitive Intelligence Dashboard — Streamlit app.

Loads scraped data from data/raw/ and presents interactive comparisons
across Rappi, Uber Eats, and DiDi Food in Mexico.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import json
import os

st.set_page_config(page_title="Rappi Competitive Intelligence", layout="wide")

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_data() -> pd.DataFrame:
    """Load the most recent scrape results JSON into a flat DataFrame."""
    data_path = "data/raw/"
    if not os.path.exists(data_path):
        return pd.DataFrame()

    files = sorted(f for f in os.listdir(data_path) if f.endswith(".json"))
    if not files:
        return pd.DataFrame()

    latest = os.path.join(data_path, files[-1])
    with open(latest) as f:
        records = json.load(f)

    if not records:
        return pd.DataFrame()

    rows = []
    for rec in records:
        base = {k: v for k, v in rec.items() if k != "products"}
        products = rec.get("products", [])

        # Find Big Mac price as primary comparison product
        bigmac_price = 0.0
        for p in products:
            if "big mac" in p.get("name", "").lower():
                bigmac_price = p["price"]
                break

        base["product_count"] = len(products)
        base["bigmac_price"] = bigmac_price
        base["has_discounts"] = len(rec.get("active_discounts", [])) > 0
        base["discount_text"] = "; ".join(rec.get("active_discounts", []))
        rows.append(base)

    df = pd.DataFrame(rows)
    # Parse city from address_name (format: "Neighborhood, City")
    if "address_name" in df.columns:
        df["city"] = df["address_name"].apply(lambda x: x.split(", ")[-1] if ", " in str(x) else x)
        df["neighborhood"] = df["address_name"].apply(lambda x: x.split(", ")[0] if ", " in str(x) else x)
    return df


df = load_data()

if df.empty:
    st.warning("No scrape data found. Run the pipeline first: `python -m src.main`")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------------------------------
st.sidebar.title("Filters")

platforms = st.sidebar.multiselect(
    "Platforms", df["platform"].unique().tolist(), default=df["platform"].unique().tolist()
)
cities = st.sidebar.multiselect(
    "Cities", df["city"].unique().tolist(), default=df["city"].unique().tolist()
)
only_available = st.sidebar.checkbox("Only open stores", value=False)

mask = df["platform"].isin(platforms) & df["city"].isin(cities)
if only_available:
    mask &= df["availability"] == True  # noqa: E712
fdf = df[mask]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Rappi Competitive Intelligence")
st.markdown(f"**{len(fdf)}** data points across **{fdf['platform'].nunique()}** platforms "
            f"and **{fdf['address_name'].nunique()}** zones")

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------

def platform_avg(col: str, platform: str) -> str:
    vals = fdf.loc[fdf["platform"] == platform, col]
    if vals.empty:
        return "N/A"
    return f"${vals.mean():.1f}"


cols = st.columns(4)
cols[0].metric("Zones Scraped", fdf["address_name"].nunique())
cols[1].metric("Rappi Avg Delivery Fee", platform_avg("delivery_fee", "Rappi"))
cols[2].metric("Uber Avg Delivery Fee", platform_avg("delivery_fee", "Uber Eats"))
cols[3].metric("DiDi Avg Delivery Fee", platform_avg("delivery_fee", "DiDi Food"))

st.markdown("---")

# ---------------------------------------------------------------------------
# 1. Delivery Fee Comparison
# ---------------------------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Delivery Fee by Platform")
    fig = px.box(
        fdf, x="platform", y="delivery_fee", color="platform",
        points="all", hover_data=["address_name"],
        labels={"delivery_fee": "Delivery Fee (MXN)", "platform": ""},
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("ETA by Platform")
    fig = px.box(
        fdf, x="platform", y="time_minutes", color="platform",
        points="all", hover_data=["address_name"],
        labels={"time_minutes": "ETA (min)", "platform": ""},
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Big Mac Price Comparison (bar chart per zone)
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Big Mac Price by Zone")

bigmac_df = fdf[fdf["bigmac_price"] > 0]
if not bigmac_df.empty:
    fig = px.bar(
        bigmac_df.sort_values("address_name"),
        x="address_name", y="bigmac_price", color="platform",
        barmode="group",
        labels={"bigmac_price": "Price (MXN)", "address_name": "Zone"},
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No Big Mac price data available yet.")

# ---------------------------------------------------------------------------
# 3. Total Final Price Comparison
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Total Final Price (Products + Fees)")

if "total_final_price" in fdf.columns:
    fig = px.bar(
        fdf.sort_values("address_name"),
        x="address_name", y="total_final_price", color="platform",
        barmode="group",
        labels={"total_final_price": "Total Price (MXN)", "address_name": "Zone"},
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 4. Geographic Heatmap
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Geographic Price Map")

# Center on median lat/lon
center_lat = fdf["lat"].median()
center_lon = fdf["lon"].median()
m = folium.Map(location=[center_lat, center_lon], zoom_start=5)

color_map = {"Rappi": "red", "Uber Eats": "blue", "DiDi Food": "green"}

for _, row in fdf.iterrows():
    color = color_map.get(row["platform"], "gray")
    popup_html = (
        f"<b>{row['platform']}</b><br>"
        f"Zone: {row['address_name']}<br>"
        f"Fee: ${row['delivery_fee']}<br>"
        f"ETA: {row['estimated_time']}<br>"
        f"Products: {row['product_count']}"
    )
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=8,
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=f"{row['platform']} — {row['address_name']}",
        color=color, fill=True, fillOpacity=0.7,
    ).add_to(m)

st_folium(m, width=900, height=500)

# ---------------------------------------------------------------------------
# 5. Delivery Fee by City (grouped bar)
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Average Delivery Fee by City")

city_fees = fdf.groupby(["city", "platform"])["delivery_fee"].mean().reset_index()
if not city_fees.empty:
    fig = px.bar(
        city_fees, x="city", y="delivery_fee", color="platform",
        barmode="group",
        labels={"delivery_fee": "Avg Fee (MXN)", "city": "City"},
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 6. ETA by Zone (grouped bar)
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Delivery Time by Zone")

fig = px.bar(
    fdf.sort_values("address_name"),
    x="address_name", y="time_minutes", color="platform",
    barmode="group",
    labels={"time_minutes": "ETA (min)", "address_name": "Zone"},
)
fig.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 7. Availability & Discounts
# ---------------------------------------------------------------------------
st.markdown("---")
col_avail, col_disc = st.columns(2)

with col_avail:
    st.subheader("Store Availability")
    avail_counts = fdf.groupby("platform")["availability"].value_counts().unstack(fill_value=0)
    avail_counts.columns = ["Closed", "Open"] if False in avail_counts.columns else ["Open"]
    st.dataframe(avail_counts, use_container_width=True)

with col_disc:
    st.subheader("Active Promotions")
    promo_df = fdf[fdf["has_discounts"]][["platform", "address_name", "discount_text"]]
    if not promo_df.empty:
        st.dataframe(promo_df, use_container_width=True)
    else:
        st.info("No active promotions detected.")

# ---------------------------------------------------------------------------
# 8. Raw Data Table
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Raw Data")
display_cols = [
    "platform", "store_name", "address_name", "delivery_fee",
    "estimated_time", "time_minutes", "availability", "bigmac_price",
    "total_final_price", "product_count", "discount_text",
]
existing_cols = [c for c in display_cols if c in fdf.columns]
st.dataframe(fdf[existing_cols].sort_values(["address_name", "platform"]), use_container_width=True)

# ---------------------------------------------------------------------------
# 9. Dynamic Insights
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Top 5 Actionable Insights")

insights = []

# Insight 1: Delivery Fee Gap
avg_fees = fdf.groupby("platform")["delivery_fee"].mean()
if not avg_fees.empty:
    cheapest = avg_fees.idxmin()
    most_expensive = avg_fees.idxmax()
    diff_pct = ((avg_fees[most_expensive] - avg_fees[cheapest]) / avg_fees[cheapest] * 100) if avg_fees[cheapest] > 0 else 0
    insights.append({
        "title": "Delivery Fee Gap",
        "finding": (
            f"{most_expensive} charges an average delivery fee of "
            f"${avg_fees[most_expensive]:.1f} MXN, while {cheapest} averages "
            f"${avg_fees[cheapest]:.1f} MXN — a {diff_pct:.0f}% premium."
        ),
        "impact": (
            f"Users comparing platforms in real-time will perceive {cheapest} as the "
            f"cheaper option, potentially reducing Rappi order volume in fee-sensitive zones."
        ),
        "recommendation": (
            f"Monitor fee-sensitive peripheral zones where competitors undercut. "
            f"Consider targeted delivery subsidies in high-churn areas to defend market share."
        ),
    })

# Insight 2: Delivery Speed
avg_eta = fdf.groupby("platform")["time_minutes"].mean()
if not avg_eta.empty:
    fastest = avg_eta.idxmin()
    slowest = avg_eta.idxmax()
    gap = avg_eta[slowest] - avg_eta[fastest]
    insights.append({
        "title": "Delivery Speed Advantage",
        "finding": (
            f"{fastest} is the fastest platform at {avg_eta[fastest]:.0f} min avg ETA, "
            f"while {slowest} averages {avg_eta[slowest]:.0f} min — a {gap:.0f}-minute gap."
        ),
        "impact": (
            "Slower ETAs directly correlate with lower conversion rates during peak hours "
            "(lunch/dinner rushes), risking loss of the 'urgent hunger' market segment."
        ),
        "recommendation": (
            f"Optimize courier dispatch density in zones where Rappi's ETA exceeds "
            f"{avg_eta[fastest]:.0f} min. Prioritize high-demand corridors during peak hours."
        ),
    })

# Insight 3: Price Positioning
if not bigmac_df.empty:
    bm_stats = bigmac_df.groupby("platform")["bigmac_price"].agg(["mean", "std"])
    if len(bm_stats) > 1:
        cheapest_bm = bm_stats["mean"].idxmin()
        priciest_bm = bm_stats["mean"].idxmax()
        price_diff = bm_stats.loc[priciest_bm, "mean"] - bm_stats.loc[cheapest_bm, "mean"]
        insights.append({
            "title": "Product Price Positioning",
            "finding": (
                f"{cheapest_bm} offers the lowest Big Mac price at "
                f"${bm_stats.loc[cheapest_bm, 'mean']:.1f} MXN avg, while {priciest_bm} "
                f"charges ${bm_stats.loc[priciest_bm, 'mean']:.1f} MXN — ${price_diff:.1f} more."
            ),
            "impact": (
                "Price perception on flagship products shapes repeat purchase behavior. "
                "A consistent price disadvantage on popular items erodes brand loyalty."
            ),
            "recommendation": (
                "Review pricing agreements with McDonald's to match or beat competitor "
                "pricing on high-visibility combos. Consider absorbing part of the margin "
                "on flagship items to drive basket size."
            ),
        })

# Insight 4: Availability
avail_rate = fdf.groupby("platform")["availability"].mean() * 100
if not avail_rate.empty:
    best_avail = avail_rate.idxmax()
    worst_avail = avail_rate.idxmin()
    insights.append({
        "title": "Store Availability",
        "finding": (
            f"{best_avail} leads with {avail_rate[best_avail]:.0f}% open-store rate, "
            f"while {worst_avail} shows {avail_rate[worst_avail]:.0f}%."
        ),
        "impact": (
            "Every closed store is a lost order. Low availability during peak hours "
            "pushes users to competitors and reduces platform GMV."
        ),
        "recommendation": (
            "Work with restaurant partners to extend operating hours in underserved "
            "zones. Flag and investigate stores with recurring downtime."
        ),
    })

# Insight 5: Promotional Activity
promo_rate = fdf.groupby("platform")["has_discounts"].mean() * 100
if not promo_rate.empty and promo_rate.max() > 0:
    most_promos = promo_rate.idxmax()
    least_promos = promo_rate.idxmin()
    insights.append({
        "title": "Promotional Strategy",
        "finding": (
            f"{most_promos} runs the most aggressive promotions, active in "
            f"{promo_rate[most_promos]:.0f}% of zones scraped. {least_promos} "
            f"has promotions in only {promo_rate[least_promos]:.0f}% of zones."
        ),
        "impact": (
            "Aggressive competitor promotions in expansion zones erode user loyalty "
            "and incentivize platform-switching behavior."
        ),
        "recommendation": (
            f"Deploy targeted counter-promotions in zones where {most_promos} is most "
            f"active. Focus on retention offers for high-frequency users in those areas."
        ),
    })

for i, ins in enumerate(insights, 1):
    st.markdown(f"### Insight {i}: {ins['title']}")
    st.markdown(f"**Finding:** {ins['finding']}")
    st.markdown(f"**Impact:** {ins['impact']}")
    st.markdown(f"**Recommendation:** {ins['recommendation']}")
    st.markdown("---")

if not insights:
    st.info("Run the scraper across multiple platforms to generate comparative insights.")

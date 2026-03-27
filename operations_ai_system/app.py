"""Streamlit chatbot UI for Rappi Operations AI System."""

import streamlit as st
import plotly.express as px

from src.data_loader import load_all
from src.llm_client import LLMClient
from src.query_engine import QueryEngine, QueryResult


st.set_page_config(
    page_title="Rappi Operations AI",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Rappi Operations AI Assistant")
st.caption("Ask questions about operational metrics in natural language.")


# ── Initialize session state ────────────────────────────────────

@st.cache_data
def load_data():
    return load_all()


def get_engine() -> QueryEngine:
    """Get or create the query engine (persisted in session state)."""
    if "engine" not in st.session_state:
        df_metrics, df_orders, week_labels = load_data()
        llm = LLMClient()
        st.session_state.engine = QueryEngine(llm, df_metrics, df_orders, week_labels)
    return st.session_state.engine


if "messages" not in st.session_state:
    st.session_state.messages = []


# ── Rendering helpers ───────────────────────────────────────────

def render_result(result: QueryResult, chart_type: str | None = None) -> None:
    """Display DataFrame and optional chart."""
    if result.df.empty:
        return

    st.dataframe(result.df, use_container_width=True, hide_index=True)

    if chart_type == "bar":
        render_bar_chart(result)
    elif chart_type == "line":
        render_line_chart(result)


def render_bar_chart(result: QueryResult) -> None:
    """Render a bar chart from the query result."""
    df = result.df
    metric = result.metric if isinstance(result.metric, str) else result.metric[0]

    if result.query_type == "filter_rank":
        fig = px.bar(df, x="ZONE", y=metric, color="COUNTRY", title=f"Top Zones by {metric}")
    elif result.query_type == "compare":
        x_col = df.columns[0]
        fig = px.bar(df, x=x_col, y=metric, title=f"{metric} by {x_col}")
    elif result.query_type == "aggregate":
        x_col = df.columns[0]
        avg_col = f"{metric} (avg)"
        fig = px.bar(df, x=x_col, y=avg_col, title=f"Average {metric} by {x_col}")
    elif result.query_type == "order_growth":
        fig = px.bar(df, x="ZONE", y="growth_pct", color="COUNTRY", title="Order Growth (%)")
    else:
        return

    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(result: QueryResult) -> None:
    """Render a line chart for trend queries."""
    df = result.df
    metric = result.metric if isinstance(result.metric, str) else result.metric[0]

    if "ZONE" in df.columns and df["ZONE"].nunique() > 1:
        fig = px.line(df, x="Week", y=metric, color="ZONE", title=f"{metric} Trend")
    else:
        zone_name = df["ZONE"].iloc[0] if "ZONE" in df.columns and not df.empty else "Zone"
        fig = px.line(df, x="Week", y=metric, title=f"{metric} — {zone_name}")

    st.plotly_chart(fig, use_container_width=True)


# ── Render chat history ─────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "result" in msg:
            render_result(msg["result"], msg.get("chart_type"))


# ── Chat input ──────────────────────────────────────────────────

if prompt := st.chat_input("Ask about Rappi operations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            engine = get_engine()
            try:
                result, narration, suggestions = engine.process_question(prompt)

                st.markdown(narration)
                render_result(result, result.chart_type)

                if suggestions:
                    st.markdown("---")
                    st.markdown("**Suggested follow-ups:**")
                    for s in suggestions:
                        st.markdown(f"- {s}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": narration,
                    "result": result,
                    "chart_type": result.chart_type,
                })

            except Exception as e:
                error_msg = f"Sorry, I couldn't process that question. Error: {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })


# ── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("About")
    st.markdown(
        "This assistant helps Operations teams query Rappi's operational "
        "metrics using natural language. Ask about zones, metrics, trends, "
        "and comparisons."
    )

    st.header("Example Questions")
    examples = [
        "Top 5 zones with highest Lead Penetration",
        "Compare Perfect Orders between Wealthy and Non Wealthy in Mexico",
        "Show Gross Profit UE trend in Chapinero for 8 weeks",
        "Average Lead Penetration by country",
        "Zones with high Lead Penetration but low Perfect Orders",
        "Which zones are growing the most in orders?",
    ]
    for ex in examples:
        st.markdown(f"- *{ex}*")

    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        if "engine" in st.session_state:
            st.session_state.engine.llm.memory.clear()
        st.rerun()

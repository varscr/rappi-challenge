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

st.title("📊 Asistente de IA para Operaciones Rappi")
st.caption("Realiza consultas sobre métricas operacionales en lenguaje natural.")


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
        fig = px.bar(df, x="ZONE", y=metric, color="COUNTRY", title=f"Top Zonas por {metric}")
    elif result.query_type == "compare":
        x_col = df.columns[0]
        fig = px.bar(df, x=x_col, y=metric, title=f"{metric} por {x_col}")
    elif result.query_type == "aggregate":
        x_col = df.columns[0]
        avg_col = f"{metric} (avg)"
        fig = px.bar(df, x=x_col, y=avg_col, title=f"Promedio de {metric} por {x_col}")
    elif result.query_type == "order_growth":
        fig = px.bar(df, x="ZONE", y="growth_pct", color="COUNTRY", title="Crecimiento de Órdenes (%)")
    else:
        return

    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(result: QueryResult) -> None:
    """Render a line chart for trend queries."""
    df = result.df
    metric = result.metric if isinstance(result.metric, str) else result.metric[0]

    if "ZONE" in df.columns and df["ZONE"].nunique() > 1:
        fig = px.line(df, x="Week", y=metric, color="ZONE", title=f"Tendencia de {metric}")
    else:
        zone_name = df["ZONE"].iloc[0] if "ZONE" in df.columns and not df.empty else "Zona"
        fig = px.line(df, x="Week", y=metric, title=f"{metric} — {zone_name}")

    st.plotly_chart(fig, use_container_width=True)


# ── Render chat history ─────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "result" in msg:
            render_result(msg["result"], msg.get("chart_type"))


# ── Chat input ──────────────────────────────────────────────────

if prompt := st.chat_input("Consulta sobre operaciones de Rappi..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            engine = get_engine()
            try:
                result, narration, suggestions = engine.process_question(prompt)

                st.markdown(narration)
                render_result(result, result.chart_type)

                if suggestions:
                    st.markdown("---")
                    st.markdown("**Seguimientos sugeridos:**")
                    for s in suggestions:
                        st.markdown(f"- {s}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": narration,
                    "result": result,
                    "chart_type": result.chart_type,
                })

            except Exception as e:
                error_msg = f"Lo siento, no pude procesar esa pregunta. Error: {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })


# ── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("Sobre el asistente")
    st.markdown(
        "Este asistente ayuda a los equipos de Operaciones a consultar "
        "métricas operacionales de Rappi usando lenguaje natural. "
        "Pregunta sobre zonas, métricas, tendencias y comparaciones."
    )

    st.header("Preguntas de ejemplo")
    examples = [
        "¿Cuáles son las 5 zonas con mayor % Lead Penetration esta semana?",
        "Compara el Perfect Order entre zonas Wealthy y Non Wealthy en México",
        "Muestra la evolución de Gross Profit UE en Chapinero últimas 8 semanas",
        "¿Cuál es el promedio de Lead Penetration por país?",
        "¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order?",
        "¿Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas y qué podría explicar el crecimiento?",
    ]
    for ex in examples:
        st.markdown(f"- *{ex}*")

    st.divider()
    if st.button("🗑️ Borrar chat"):
        st.session_state.messages = []
        if "engine" in st.session_state:
            st.session_state.engine.llm.memory.clear()
        st.rerun()

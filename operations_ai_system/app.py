"""Streamlit chatbot UI for Rappi Operations AI System."""

import streamlit as st
import plotly.express as px
import pandas as pd

from src.data_loader import load_all
from src.llm_client import LLMClient
from src.query_engine import QueryEngine, QueryResult


# ── Page Configuration ──────────────────────────────────────────

st.set_page_config(
    page_title="Rappi Operations AI",
    page_icon="📊",
    layout="wide",
)

# Rappi Brand Colors
RAPPI_ORANGE = "#FF441F"

# Custom Styling
st.markdown(f"""
    <style>
    .main .block-container {{ padding-top: 2rem; }}
    h1 {{ color: {RAPPI_ORANGE}; }}
    .stButton>button {{ background-color: {RAPPI_ORANGE}; color: white; border-radius: 5px; }}
    .stTextInput>div>div>input {{ border-radius: 5px; }}
    </style>
    """, unsafe_allow_html=True)

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

def _chart_dims(df: pd.DataFrame, exclude: set[str]) -> tuple[str, str | None]:
    """Find the most granular (x-axis) and broadest (color) dimension columns."""
    dims = [c for c in df.columns if c not in exclude]
    x_col = dims[-1] if dims else df.columns[0]
    color_col = dims[0] if len(dims) > 1 and dims[0] != x_col else None
    return x_col, color_col


def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply business formatting to the dataframe for display."""
    formatted = df.copy()
    for col in formatted.columns:
        # If it looks like a ratio (0-1) and isn't 'Orders', format as percentage
        if formatted[col].dtype in ['float64', 'float32'] and "Orders" not in col and "growth" not in col:
            if formatted[col].max() <= 1.1 and formatted[col].min() >= -0.1:
                formatted[col] = formatted[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else x)
        # Format growth as %
        elif "growth" in col.lower():
            formatted[col] = formatted[col].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else x)
    return formatted


def render_result(result: QueryResult, chart_type: str | None = None) -> None:
    """Display DataFrame and optional chart."""
    if result.df.empty:
        return

    # Display formatted table
    st.dataframe(format_dataframe(result.df), use_container_width=True, hide_index=True)

    if chart_type == "bar":
        render_bar_chart(result)
    elif chart_type == "line":
        render_line_chart(result)


def render_bar_chart(result: QueryResult) -> None:
    """Render a bar chart from the query result."""
    df = result.df
    metric = result.metric if isinstance(result.metric, str) else result.metric[0]

    if result.query_type == "filter_rank":
        x_col, color_col = _chart_dims(df, {metric})
        fig = px.bar(df, x=x_col, y=metric, color=color_col, title=f"Top Zonas por {metric}",
                     color_discrete_sequence=px.colors.qualitative.Bold)
    elif result.query_type == "compare":
        x_col = df.columns[0]
        fig = px.bar(df, x=x_col, y=metric, title=f"{metric} por {x_col}",
                     color_discrete_sequence=[RAPPI_ORANGE])
    elif result.query_type == "aggregate":
        x_col = df.columns[0]
        avg_col = f"{metric} (avg)"
        fig = px.bar(df, x=x_col, y=avg_col, title=f"Promedio de {metric} por {x_col}",
                     color_discrete_sequence=[RAPPI_ORANGE])
    elif result.query_type == "order_growth":
        x_col, color_col = _chart_dims(df, {"growth_pct", f"Orders ({df.columns[-3]})" if len(df.columns) > 3 else ""})
        fig = px.bar(df, x=x_col, y="growth_pct", color=color_col, title="Crecimiento de Órdenes (%)",
                     color_discrete_sequence=px.colors.qualitative.Safe)
    else:
        return

    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(result: QueryResult) -> None:
    """Render a line chart for trend queries."""
    df = result.df
    metric = result.metric if isinstance(result.metric, str) else result.metric[0]
    _, color_col = _chart_dims(df, {metric, "Week"})

    if color_col and df[color_col].nunique() > 1:
        fig = px.line(df, x="Week", y=metric, color=color_col, title=f"Tendencia de {metric}",
                      color_discrete_sequence=px.colors.qualitative.Bold)
    else:
        label = df[color_col].iloc[0] if color_col and color_col in df.columns and not df.empty else "Zona"
        fig = px.line(df, x="Week", y=metric, title=f"{metric} — {label}",
                      color_discrete_sequence=[RAPPI_ORANGE])

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
    ]
    for ex in examples:
        st.markdown(f"- *{ex}*")

    st.divider()
    
    with st.sidebar.expander("📋 Reporte Ejecutivo de Insights", expanded=True):
        st.write("Análisis automático de anomalías, tendencias y benchmarking.")
        
        if st.button("🚀 Generar Nuevo Análisis", use_container_width=True):
            from generate_report import generate_report
            with st.spinner("Analizando..."):
                path, html, stats = generate_report()
                st.session_state.last_report = {"path": path, "html": html, "stats": stats}
                st.toast("¡Análisis completado!", icon="🚀")

        if "last_report" in st.session_state:
            report = st.session_state.last_report
            
            # --- Actions Tabs ---
            st.markdown("---")
            tab_dl, tab_em = st.tabs(["💾 Descargar", "📧 Enviar"])
            
            with tab_dl:
                st.download_button(
                    label="📥 Bajar HTML",
                    data=report["html"],
                    file_name=report["path"].name,
                    mime="text/html",
                    use_container_width=True
                )
            
            with tab_em:
                email_recipient = st.text_input("Email:", placeholder="ejemplo@rappi.com")
                if st.button("Enviar Reporte", use_container_width=True):
                    if not email_recipient:
                        st.error("Falta el email")
                    elif "@" not in email_recipient or "." not in email_recipient.split("@")[-1]:
                        st.error("Por favor, ingresa un correo electrónico válido.")
                    else:
                        from src.email_utils import send_report_email
                        with st.spinner("Enviando..."):
                            success, message = send_report_email(email_recipient, report["html"], report["path"])
                            if success:
                                st.success(message)
                                st.toast(message, icon="📧")
                            else:
                                st.error(message)

    st.divider()
    if st.button("🗑️ Borrar chat"):
        st.session_state.messages = []
        if "engine" in st.session_state:
            st.session_state.engine.llm.memory.clear()
        st.rerun()

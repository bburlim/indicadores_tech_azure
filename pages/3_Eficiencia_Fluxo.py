"""Página: Eficiência de Fluxo."""
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from components.charts import line_chart_monthly, kpi_card, scatter_trend
from metrics.flow_efficiency import (
    flow_efficiency_by_month, flow_efficiency_by_team_month, flow_efficiency_trend,
)
from metrics.lead_cycle_time import pivot_team_month
import config

st.set_page_config(layout="wide")
st.title("Eficiência de Fluxo")

if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df = st.session_state.filtered_df if "filtered_df" in st.session_state else st.session_state.items_df

# Filtros específicos
with st.expander("**Filtros Específicos** — aplicáveis às visões de Eficiência de Fluxo e Tempo por Status"):
    col1, col2, col3 = st.columns(3)
    flow_type = col1.selectbox("Tipo Fluxo", ["Downstream", "All"])
    status_type = col2.selectbox("Tipo Status", ["All", "Active Only", "Wait Only"])
    status_filter = col3.selectbox("Status", ["All"] + config.ALL_STATUSES)

# ─── KPI e gráfico principal ──────────────────────────────────────────────────
fe_month = flow_efficiency_by_month(df)

if "flow_efficiency" in df.columns:
    delivered = df[df["closed_date"].notna()]
    fe_geral = round(delivered["flow_efficiency"].mean(), 1) if not delivered.empty else 0
else:
    fe_geral = 0

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown(kpi_card("Eficiência de Fluxo", f"{fe_geral}%"), unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:12px;margin-top:8px;">
    A eficiência de fluxo compara o <b style="color:#4472C4;">tempo ativo de trabalho (Touch Time) com o tempo total</b>, incluindo status de fila.<br><br>
    <b>Alta Eficiência:</b> Indica que a equipe trabalha de forma contínua e otimizada, com poucas interrupções.
    Segundo as melhores práticas, uma eficiência de <b style="color:#4472C4;">fluxo acima de 40% é considerada ideal.</b><br><br>
    <b>Baixa Eficiência:</b> Revela que a equipe enfrenta muitas pausas e esperas, sugerindo problemas no processo.
    </div>
    """, unsafe_allow_html=True)

with col2:
    if not fe_month.empty:
        fig = line_chart_monthly(
            fe_month, "month", "flow_efficiency",
            title=f"Eficiência de Fluxo (Ideal {config.FLOW_EFFICIENCY_BENCH}%)",
            bench_value=config.FLOW_EFFICIENCY_BENCH,
            bench_label=f"Ideal {config.FLOW_EFFICIENCY_BENCH}%",
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Tabela por Equipe e Tendência ─────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    fe_team = flow_efficiency_by_team_month(df)
    if not fe_team.empty:
        st.markdown("**Cycle Time por Equipe** (Eficiência de Fluxo %)")
        styled = fe_team.style.set_table_styles([
            {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white")]},
            {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#DCE6F1")]},
        ])
        st.dataframe(styled, use_container_width=True, hide_index=True)

with col2:
    fe_trend = flow_efficiency_trend(df)
    if not fe_trend.empty:
        fig_trend = scatter_trend(
            fe_trend, "week_ordinal", "flow_efficiency",
            "Tendência Eficiência de Fluxo", "#4472C4",
        )
        fig_trend.update_layout(yaxis=dict(tickformat=".0f", ticksuffix="%"))
        st.plotly_chart(fig_trend, use_container_width=True)

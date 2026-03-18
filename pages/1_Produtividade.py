"""Página: Produtividade - Abertura, Entregas, Backlog e Vazão."""
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from components.charts import (
    bar_chart_monthly, kpi_card, dataframe_table,
    horizontal_bar, scatter_trend, dual_bar_chart,
)
from metrics.throughput import (
    throughput_by_month, backlog_snapshot_by_month, burn_down_time,
    vazao_qualificada_by_month, vazao_qualificada_by_team_month,
)
import config

st.set_page_config(layout="wide")
st.title("Produtividade - Estamos conseguindo entregar valor para o cliente?")

# Verifica se os dados estão carregados
if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df = st.session_state.filtered_df if "filtered_df" in st.session_state else st.session_state.items_df

# ─── Abertura, Entregas e Backlog ────────────────────────────────────────────
st.subheader("Abertura, Entregas e Backlog")

tp = throughput_by_month(df)
bp = backlog_snapshot_by_month(df)
bdt = burn_down_time(df)
delivered_count = df[df["closed_date"].notna()].shape[0]

# Média mensal de entregas
avg_monthly = round(tp["total"].mean(), 1) if not tp.empty and "total" in tp.columns else 0
backlog_total = df[df["closed_date"].isna()].shape[0]

# KPIs
col1, col2, col3 = st.columns(3)
col1.markdown(kpi_card("Backlog", str(backlog_total)), unsafe_allow_html=True)
col2.markdown(kpi_card("Média de Entregas", str(avg_monthly)), unsafe_allow_html=True)
col3.markdown(kpi_card("Burn-Down Time", f"{bdt} Meses"), unsafe_allow_html=True)

st.markdown("""
<div style="background:#f5f5f5;border-radius:8px;padding:12px;margin:8px 0;font-size:13px;">
<b>Backlog:</b> Itens criados que ainda não foram concluídos.<br>
<b>Média de Entregas:</b> Quantidade de entregas por mês.<br>
<b>Burn-Down Time (tempo de esgotamento):</b> Estimativa de meses necessários para finalizar os itens do backlog, baseado na média de entrega mensal.
Fórmula: média de entregas por quantidade de itens em backlog.
</div>
""", unsafe_allow_html=True)

# Gráfico Abertura x Throughput
if not tp.empty:
    opened_by_month = df.copy()
    opened_by_month["month"] = opened_by_month["created_date"].dt.to_period("M").dt.to_timestamp()
    opened_monthly = opened_by_month.groupby("month").size().reset_index(name="opened")

    merged = tp.merge(opened_monthly, on="month", how="outer").sort_values("month")

    fig = bar_chart_monthly(
        merged,
        x_col="month",
        y_cols=["opened", "total"],
        labels={"opened": "Itens Abertos", "total": "Itens Entregues"},
        colors=["#FFA500", "#6666CC"],
        title="Abertura x Throughput de Defeito e História",
        text_outside=True,
    )
    st.plotly_chart(fig, use_container_width=True)

# Throughput e Backlog por tipo
col1, col2 = st.columns(2)
with col1:
    if not tp.empty:
        fig2 = bar_chart_monthly(
            tp, "month",
            ["Defeito", "História"] if "Defeito" in tp.columns else [c for c in tp.columns if c not in ["month", "total"]],
            {"Defeito": "Defeito", "História": "História"},
            ["#8B2252", "#87CEEB"],
            "Throughput - Defeito x História",
            stacked=True,
        )
        st.plotly_chart(fig2, use_container_width=True)

with col2:
    if not bp.empty:
        fig3 = bar_chart_monthly(
            bp, "month",
            ["Defeito", "História"] if "Defeito" in bp.columns else [c for c in bp.columns if c not in ["month", "backlog_total"]],
            {"Defeito": "Defeito", "História": "História"},
            ["#8B2252", "#87CEEB"],
            "Backlog - Defeito x História",
            stacked=True,
        )
        st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ─── Vazão Qualificada ────────────────────────────────────────────────────────
st.subheader("Vazão Qualificada")

st.markdown("""
<div style="background:#f5f5f5;border-radius:8px;padding:12px;margin:8px 0;font-size:13px;">
No indicador de produtividade por <b>Vazão Qualificada</b>, são atribuídos pesos levando em consideração
o tipo de item e seu respectivo Cycle Time (tempo de desenvolvimento):<br><br>
<b>Defeitos</b> – 0,5 pontos<br>
<b>Histórias (até 1 dia)</b> – 0 pontos<br>
<b>Histórias (1 a 3 dias)</b> – 0,5 pontos<br>
<b>Histórias (4 a 10 dias)</b> – 1 ponto<br>
<b>Histórias (11 dias ou mais)</b> – 2 pontos
</div>
""", unsafe_allow_html=True)

vq = vazao_qualificada_by_month(df)
vq_team = vazao_qualificada_by_team_month(df)

col1, col2 = st.columns(2)
with col1:
    if not vq.empty:
        # Horizontal bar total
        total_by_type = df[df["closed_date"].notna()].groupby("item_type_general")["vazao_qualificada"].sum().reset_index()
        total_by_type.columns = ["tipo", "total"]
        fig_h = horizontal_bar(total_by_type, "tipo", "total",
                                ["#1C1C1C", "#4472C4"],
                                "Vazão Qualificada por Tipo Original")
        st.plotly_chart(fig_h, use_container_width=True)

with col2:
    if not vq.empty:
        tipo_cols = [c for c in vq.columns if c not in ["month", "total"]]
        fig_vq = bar_chart_monthly(
            vq, "month", tipo_cols,
            {"Defeito": "Bug - Tec", "História": "History - Tec"},
            ["#1C1C1C", "#4472C4"],
            "Vazão Qualificada por Tipo Original",
            stacked=True,
        )
        st.plotly_chart(fig_vq, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    if not vq_team.empty:
        st.markdown("**Vazão Qualificada Por Equipe**")
        st.dataframe(vq_team.style.set_table_styles([
            {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white")]},
        ]), use_container_width=True, hide_index=True)

with col2:
    if not vq.empty:
        delivered = df[df["closed_date"].notna()].copy()
        delivered["week_ordinal"] = delivered["closed_date"].apply(
            lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if not hasattr(x, 'isocalendar') or x != x else None
        )
        week_agg = delivered.groupby("week_ordinal")["vazao_qualificada"].sum().reset_index()
        fig_scatter = scatter_trend(week_agg, "week_ordinal", "vazao_qualificada",
                                     "Tendência Vazão Qualificada (Semanal)", "#1C1C1C")
        fig_scatter.update_layout(yaxis_title="Sum of Vazão Qualificada")
        st.plotly_chart(fig_scatter, use_container_width=True)

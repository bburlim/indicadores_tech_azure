"""Página: Qualidade - Retrabalho, Saúde Backlog, SLA, Defeitos."""
import streamlit as st
import sys, os
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from components.charts import (
    kpi_card, bar_chart_monthly, line_chart_monthly,
    dual_bar_chart, scatter_trend,
)
from metrics.quality import (
    rework_rate_by_month, rework_rate_by_team_month, rework_trend_weekly,
    backlog_health_by_month,
    sla_bugs_by_month,
    defects_by_origin_month, defects_delivered_by_origin_month, defects_opened_by_origin_month,
)
import config

st.set_page_config(layout="wide")
st.title("Qualidade — Esse valor está sendo entregue com qualidade?")

if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df = st.session_state.items_df
df_filtered = st.session_state.filtered_df if "filtered_df" in st.session_state else df
time_by_status = st.session_state.get("time_by_status_df", None)
if time_by_status is None:
    import pandas as pd
    time_by_status = pd.DataFrame()

# ─── KPIs de topo ─────────────────────────────────────────────────────────────
st.subheader("Aberturas, entregas e backlog de defeitos")

rw_month = rework_rate_by_month(df_filtered, time_by_status)
rw_geral = rw_month["rework_rate"].mean() if not rw_month.empty else 0

col1, = st.columns(1)
col1.markdown(kpi_card("Percentual de Retrabalho", f"{rw_geral:.1f}%",
               "#FF0000" if rw_geral > config.REWORK_BENCH else "#228B22"),
               unsafe_allow_html=True)

# ─── Abertura x Defeitos Entregues ────────────────────────────────────────────
bugs_delivered_month = defects_delivered_by_origin_month(df_filtered)
bugs_opened_month = defects_opened_by_origin_month(df_filtered)

import pandas as pd
col1, col2 = st.columns(2)
with col1:
    # Agrupa entregues e abertos por mês (sem distinção origem)
    del_monthly = bugs_delivered_month.groupby("month")["count"].sum().reset_index(name="delivered")
    opened_monthly = bugs_opened_month.groupby("month")["count"].sum().reset_index(name="opened")
    ab_del = del_monthly.merge(opened_monthly, on="month", how="outer").fillna(0)

    fig = bar_chart_monthly(
        ab_del, "month", ["opened", "delivered"],
        {"opened": "Defeitos Abertos", "delivered": "Defeitos Entregues"},
        ["#FFA500", "#4472C4"],
        "Abertura x Defeitos Entregues",
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Tendência semanal backlog
    bugs_df = df_filtered[df_filtered["item_type_general"] == "Defeito"].copy()
    if not bugs_df.empty:
        bugs_df["week_ordinal"] = bugs_df["closed_date"].apply(
            lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if pd.notna(x) else None
        )
        # Backlog acumulado por semana
        weeks = sorted(bugs_df["week_ordinal"].dropna().unique())
        rows = []
        for w in weeks:
            open_w = df_filtered.copy()
            open_w["week_ordinal"] = open_w["created_date"].apply(
                lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if pd.notna(x) else None
            )
            created = open_w[open_w["week_ordinal"] <= w]
            delivered = created[created["closed_date"].notna() & (
                created["closed_date"].apply(lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if pd.notna(x) else None) <= w
            )]
            backlog_w = len(created) - len(delivered)
            opened_w = len(open_w[open_w["week_ordinal"] == w])
            rows.append({"week": w, "backlog": backlog_w, "opened": opened_w})
        weekly_df = pd.DataFrame(rows)

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=weekly_df["week"], y=weekly_df["opened"],
                                        mode="lines+markers", name="Itens Abertos",
                                        line=dict(color="#FFA500")))
        fig_trend.add_trace(go.Scatter(x=weekly_df["week"], y=weekly_df["backlog"],
                                        mode="lines+markers", name="Backlog",
                                        line=dict(color="#1C1C1C")))
        fig_trend.update_layout(title="Tendência de Abertura e Backlog de Defeitos (Semanal)",
                                  plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ─── Saúde Backlog ────────────────────────────────────────────────────────────
st.subheader("Saúde Backlog")

bh = backlog_health_by_month(df)
bh_geral = bh["backlog_health"].mean() if not bh.empty else 0

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown(kpi_card("% Saúde Backlog", f"{bh_geral:.0f}%"), unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:12px;margin-top:8px;">
    A Saúde Backlog, determinada pela relação entre defeitos e o total de itens, é um indicador da qualidade e prioridades da equipe de desenvolvimento.
    Um grande número de defeitos no backlog revela um <b style="color:#4472C4;">foco em novos recursos ao invés de correções, podendo acarretar problemas técnicos a longo prazo.</b><br><br>
    <b>OBS:</b> Quanto maior for a quantidade de defeitos em relação a histórias, menor será a saúde do backlog.
    </div>
    """, unsafe_allow_html=True)

with col2:
    if not bh.empty:
        fig_bh = bar_chart_monthly(
            bh, "month", ["backlog_health"],
            {"backlog_health": "% Saúde Backlog"},
            ["#6666CC"],
            "Saúde Backlog",
        )
        fig_bh.update_layout(yaxis=dict(range=[0, 110], ticksuffix="%"), showlegend=False)
        st.plotly_chart(fig_bh, use_container_width=True)

st.divider()

# ─── SLA ─────────────────────────────────────────────────────────────────────
st.subheader("Acordo de Nível de Serviço (SLA)")

sla = sla_bugs_by_month(df_filtered)
sla_geral = sla["sla_pct"].mean() if not sla.empty else 0

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown(kpi_card("% SLA", f"{sla_geral:.1f}%"), unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:12px;margin-top:8px;">
    O <b style="color:#4472C4;">SLA (Acordo de Nível de Serviço)</b> define os termos e expectativas de entregas de correção de defeito entre a empresa e seus clientes.
    Este acordo é essencial para assegurar a satisfação do cliente, mantendo a transparência e a confiabilidade nos serviços de software oferecidos.<br><br>
    <b>Formula:</b> defeitos entregues no prazo por total de defeitos com SLA.
    </div>
    """, unsafe_allow_html=True)

with col2:
    if not sla.empty:
        fig_sla = bar_chart_monthly(
            sla, "month", ["not_sla_pct"],
            {"not_sla_pct": "Não Atendido"},
            ["#FFA500"],
            "SLA de Defeitos Entregues",
        )
        fig_sla.update_layout(yaxis=dict(range=[0, 120], ticksuffix="%"), showlegend=True)
        st.plotly_chart(fig_sla, use_container_width=True)

st.divider()

# ─── Taxa de Retrabalho ───────────────────────────────────────────────────────
st.subheader("Taxa de Retrabalho")

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:12px;">
    O indicador de retrabalho mede a <b style="color:#4472C4;">proporção do tempo gasto pela equipe em correções (defeitos) em comparação às melhorias (histórias)</b>, dentro de um mês.<br><br>
    Segundo o livro <b>"Accelerate"</b>, empresas de alta performance apresentam um índice de retrabalho inferior a <b>20%</b>.<br><br>
    Este índice é derivado do touch time, que representa a soma dos períodos em que os itens estiveram ativamente em desenvolvimento.<br><br>
    <b>Fórmula:</b> Touch Time Defeitos / (Touch Time Defeitos + Touch Time Histórias).
    </div>
    """, unsafe_allow_html=True)

with col2:
    if not rw_month.empty:
        fig_rw = line_chart_monthly(
            rw_month, "month", "rework_rate",
            f"Taxa de Retrabalho (Bench {config.REWORK_BENCH}%)",
            bench_value=config.REWORK_BENCH,
            bench_label=f"Bench {config.REWORK_BENCH}%",
            color="#FFA500",
        )
        fig_rw.update_layout(yaxis=dict(ticksuffix="%"))
        st.plotly_chart(fig_rw, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    rw_team = rework_rate_by_team_month(df_filtered, time_by_status)
    if not rw_team.empty:
        st.markdown("**Taxa de Retrabalho por Equipe**")
        st.dataframe(rw_team.style.set_table_styles([
            {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white")]},
            {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#DCE6F1")]},
        ]).format({c: "{:.1f}%" for c in rw_team.columns if c != "Equipe"}, na_rep="--"),
        use_container_width=True, hide_index=True)

with col2:
    rw_trend = rework_trend_weekly(df_filtered, time_by_status)
    if not rw_trend.empty:
        fig_rw_trend = scatter_trend(rw_trend, "week_ordinal", "rework_rate",
                                      "Tendência Taxa de Retrabalho (Semanal)", "#FFA500")
        st.plotly_chart(fig_rw_trend, use_container_width=True)

st.divider()

# ─── Defeitos por Origem ──────────────────────────────────────────────────────
st.subheader("Defeitos por Origem (Cliente x Interno)")

backlog_origin = defects_by_origin_month(df_filtered)
delivered_origin = defects_delivered_by_origin_month(df_filtered)
opened_origin = defects_opened_by_origin_month(df_filtered)

def pivot_origin(df_orig: pd.DataFrame) -> pd.DataFrame:
    if df_orig.empty:
        return pd.DataFrame()
    pivot = df_orig.pivot(index="month", columns="origin", values="count").fillna(0).reset_index()
    pivot["total"] = pivot.drop(columns="month").sum(axis=1)
    return pivot

col1, col2 = st.columns(2)
with col1:
    bp = pivot_origin(backlog_origin)
    if not bp.empty:
        cols = [c for c in ["Cliente", "Interno"] if c in bp.columns]
        fig_bo = bar_chart_monthly(bp, "month", cols,
                                    {c: c for c in cols}, ["#8B2252", "#20B2AA"],
                                    "Backlog Defeitos por Origem", stacked=True)
        st.plotly_chart(fig_bo, use_container_width=True)

with col2:
    # Tendência backlog por origem (semanal)
    if not backlog_origin.empty:
        backlog_weekly = backlog_origin.copy()
        backlog_weekly["week"] = pd.to_datetime(backlog_weekly["month"]).apply(
            lambda x: (x.year - 2020) * 52 + x.isocalendar()[1]
        )
        fig_bo_trend = go.Figure()
        for origin, color in [("Cliente", "#8B2252"), ("Interno", "#20B2AA")]:
            od = backlog_weekly[backlog_weekly["origin"] == origin] if "origin" in backlog_weekly.columns else pd.DataFrame()
            if od.empty:
                continue
            fig_bo_trend.add_trace(go.Scatter(x=od["week"], y=od["count"],
                                               mode="lines+markers", name=origin,
                                               line=dict(color=color)))
        fig_bo_trend.update_layout(title="Tendência de Backlog de Defeitos por Origem",
                                    plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_bo_trend, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    dp = pivot_origin(delivered_origin)
    if not dp.empty:
        cols = [c for c in ["Cliente", "Interno"] if c in dp.columns]
        fig_del = bar_chart_monthly(dp, "month", cols,
                                     {c: c for c in cols}, ["#8B2252", "#20B2AA"],
                                     "Defeitos Entregue por Origem")
        st.plotly_chart(fig_del, use_container_width=True)

with col2:
    op = pivot_origin(opened_origin)
    if not op.empty:
        cols = [c for c in ["Cliente", "Interno"] if c in op.columns]
        fig_op = bar_chart_monthly(op, "month", cols,
                                    {c: c for c in cols}, ["#8B2252", "#20B2AA"],
                                    "Entrada de Defeitos por Origem")
        st.plotly_chart(fig_op, use_container_width=True)

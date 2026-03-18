"""Página: Lead Time e Cycle Time."""
import streamlit as st
import sys, os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from components.charts import (
    bar_chart_monthly, dual_bar_chart, scatter_trend,
    team_month_pivot_table, kpi_card, MONTH_PT,
)
from metrics.lead_cycle_time import (
    lct_p85_by_month, lct_p85_by_type_month, lct_by_team_month,
    lct_std_by_month, lct_trend_by_item, pivot_team_month,
)

st.set_page_config(layout="wide")
st.title("Lead Time e Cycle Time")

if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df = st.session_state.filtered_df if "filtered_df" in st.session_state else st.session_state.items_df

# Explicação
st.markdown("""
<div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:13px;">
<b style="color:#4472C4;">- Lead Time:</b> representa o tempo total em dias corridos, desde a criação até a entrega do item.<br>
<b style="color:#4472C4;">- Cycle Time:</b> representa o tempo em dias corridos, desde o início de desenvolvimento até a entrega (Downstream).<br>
<b style="color:#4472C4;">Percentil 85%:</b> Com esse cálculo focamos nos valores mais comuns, eliminando extremos.
</div>
""", unsafe_allow_html=True)

# ─── KPIs e P85 geral ─────────────────────────────────────────────────────────
p85 = lct_p85_by_month(df)

delivered = df[df["closed_date"].notna()]
lt_p85_geral = round(np.percentile(delivered["lead_time"].dropna(), 85), 1) if delivered["lead_time"].dropna().shape[0] > 0 else 0
ct_p85_geral = round(np.percentile(delivered["cycle_time"].dropna(), 85), 1) if delivered["cycle_time"].dropna().shape[0] > 0 else 0

col1, col2 = st.columns(2)
col1.markdown(kpi_card("Lead Time 85%", f"{lt_p85_geral}"), unsafe_allow_html=True)
col2.markdown(kpi_card("Cycle Time 85%", f"{ct_p85_geral}"), unsafe_allow_html=True)

# Gráfico principal P85 mensal
if not p85.empty:
    fig = dual_bar_chart(
        p85, "month",
        "lead_time_p85", "cycle_time_p85",
        "Lead Time Perc 85%", "Cycle Time Perc 85%",
        "#4040AA", "#228B22",
        "Lead Time vs Cycle Time (Percentil 85%)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ─── P85 por Tipo ─────────────────────────────────────────────────────────────
p85_type = lct_p85_by_type_month(df)

col1, col2 = st.columns(2)
with col1:
    if not p85_type.empty:
        for tipo_label, col_name, title in [("Defeito", "lead_time_p85", "LeadTime 85% por Tipo de Item"),
                                              ("Defeito", "cycle_time_p85", None)]:
            break
        # Lead Time por tipo
        for tipo in ["Defeito", "História"]:
            tipo_df = p85_type[p85_type["item_type_general"] == tipo].copy()

        # Reorganiza para gráfico dual por tipo
        from metrics.lead_cycle_time import lct_p85_by_type_month
        lt_pivot = p85_type.pivot(index="month", columns="item_type_general", values="lead_time_p85").fillna(0).reset_index()
        fig_lt = dual_bar_chart(
            lt_pivot, "month",
            "Defeito" if "Defeito" in lt_pivot.columns else lt_pivot.columns[1],
            "História" if "História" in lt_pivot.columns else lt_pivot.columns[2],
            "Defeito", "História",
            "#8B2252", "#87CEEB",
            "LeadTime 85% por Tipo de Item",
        )
        st.plotly_chart(fig_lt, use_container_width=True)

with col2:
    if not p85_type.empty:
        ct_pivot = p85_type.pivot(index="month", columns="item_type_general", values="cycle_time_p85").fillna(0).reset_index()
        col_def = "Defeito" if "Defeito" in ct_pivot.columns else ct_pivot.columns[1]
        col_his = "História" if "História" in ct_pivot.columns else (ct_pivot.columns[2] if len(ct_pivot.columns) > 2 else ct_pivot.columns[1])
        fig_ct = dual_bar_chart(
            ct_pivot, "month",
            col_def, col_his,
            "Defeito", "História",
            "#8B2252", "#87CEEB",
            "Cycle Time 85% por Tipo de Item",
        )
        st.plotly_chart(fig_ct, use_container_width=True)

st.divider()

# ─── Tabelas por Equipe ────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    lt_team = pivot_team_month(df, "lead_time")
    if not lt_team.empty:
        st.markdown("**Lead Time por Equipe**")
        st.dataframe(lt_team.style.set_table_styles([
            {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white")]},
        ]), use_container_width=True, hide_index=True)

with col2:
    ct_team = pivot_team_month(df, "cycle_time")
    if not ct_team.empty:
        st.markdown("**Cycle Time por Equipe**")
        st.dataframe(ct_team.style.set_table_styles([
            {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white")]},
        ]), use_container_width=True, hide_index=True)

st.divider()

# ─── Tendências ────────────────────────────────────────────────────────────────
st.markdown("**Tendências Lead Time e Cycle Time (por item entregue)**")

trend_df = lct_trend_by_item(df)
col1, col2 = st.columns(2)

with col1:
    if not trend_df.empty:
        fig_lt_trend = go.Figure()
        for tipo, color in [("Defeito", "#8B2252"), ("História", "#87CEEB")]:
            t = trend_df[trend_df["item_type_general"] == tipo]
            if t.empty:
                continue
            fig_lt_trend.add_trace(go.Scatter(
                x=t["week_ordinal"], y=t["lead_time"],
                mode="lines+markers", name=tipo,
                line=dict(color=color, width=1),
                marker=dict(size=5),
            ))
            # Trendline
            z = np.polyfit(t["week_ordinal"].dropna(), t["lead_time"].dropna(), 1)
            p = np.poly1d(z)
            x_vals = t["week_ordinal"].dropna().values
            fig_lt_trend.add_trace(go.Scatter(
                x=x_vals, y=p(x_vals), mode="lines",
                line=dict(color=color, dash="dash", width=1),
                showlegend=False,
            ))
        fig_lt_trend.update_layout(title="Tendência Lead Time", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_lt_trend, use_container_width=True)

with col2:
    if not trend_df.empty:
        fig_ct_trend = go.Figure()
        for tipo, color in [("Defeito", "#8B2252"), ("História", "#87CEEB")]:
            t = trend_df[trend_df["item_type_general"] == tipo]
            if t.empty:
                continue
            fig_ct_trend.add_trace(go.Scatter(
                x=t["week_ordinal"], y=t["cycle_time"],
                mode="lines+markers", name=tipo,
                line=dict(color=color, width=1),
                marker=dict(size=5),
            ))
            z = np.polyfit(t["week_ordinal"].dropna(), t["cycle_time"].dropna(), 1)
            p = np.poly1d(z)
            x_vals = t["week_ordinal"].dropna().values
            fig_ct_trend.add_trace(go.Scatter(
                x=x_vals, y=p(x_vals), mode="lines",
                line=dict(color=color, dash="dash", width=1),
                showlegend=False,
            ))
        fig_ct_trend.update_layout(title="Tendência Cycle Time", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_ct_trend, use_container_width=True)

st.divider()

# ─── Desvio Padrão ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#f5f5f5;border-radius:8px;padding:12px;font-size:13px;">
O desvio padrão do <b style="color:#4472C4;">Cycle Time e do Lead Time</b> quantifica a variação dos tempos de conclusão
de itens em torno da média pela equipe.<br>
<b style="color:#8B2252;">Desvio Padrão Elevado (negativo):</b> indica que os valores estão mais dispersos, refletindo uma maior variabilidade nos processos ou na quebra das entregas.<br>
<b style="color:#4472C4;">Desvio Padrão Baixo (positivo):</b> mostra que os tempos de conclusão estão mais próximos da média, sinalizando uma maior consistência.
</div>
""", unsafe_allow_html=True)

std_geral, std_tipo = lct_std_by_month(df)

col1, col2 = st.columns(2)
with col1:
    if not std_geral.empty:
        fig_std = dual_bar_chart(
            std_geral, "month",
            "lead_time_std", "cycle_time_std",
            "Lead Time Desvio Padrão", "Cycle Time Desvio Padrão",
            "#4040AA", "#1C1C1C",
            "Lead Time vs Cycle Time (Desvio Padrão)",
        )
        st.plotly_chart(fig_std, use_container_width=True)

if not std_tipo.empty:
    col1, col2 = st.columns(2)
    with col1:
        lt_std_pivot = std_tipo.pivot(index="month", columns="item_type_general", values="lead_time_std").fillna(0).reset_index()
        col_def = "Defeito" if "Defeito" in lt_std_pivot.columns else lt_std_pivot.columns[1]
        col_his = "História" if "História" in lt_std_pivot.columns else (lt_std_pivot.columns[2] if len(lt_std_pivot.columns) > 2 else lt_std_pivot.columns[1])
        fig_lt_std = dual_bar_chart(lt_std_pivot, "month", col_def, col_his,
                                     "Defeito", "História", "#8B2252", "#87CEEB",
                                     "Desvio Padrão Lead Time")
        st.plotly_chart(fig_lt_std, use_container_width=True)

    with col2:
        ct_std_pivot = std_tipo.pivot(index="month", columns="item_type_general", values="cycle_time_std").fillna(0).reset_index()
        col_def = "Defeito" if "Defeito" in ct_std_pivot.columns else ct_std_pivot.columns[1]
        col_his = "História" if "História" in ct_std_pivot.columns else (ct_std_pivot.columns[2] if len(ct_std_pivot.columns) > 2 else ct_std_pivot.columns[1])
        fig_ct_std = dual_bar_chart(ct_std_pivot, "month", col_def, col_his,
                                     "Defeito", "História", "#8B2252", "#87CEEB",
                                     "Desvio Padrão Cycle Time")
        st.plotly_chart(fig_ct_std, use_container_width=True)

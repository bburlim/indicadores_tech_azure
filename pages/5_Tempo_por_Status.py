"""Página: Tempo por Status."""
import streamlit as st
import sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from components.charts import horizontal_bar, stacked_bar_pct_monthly
from metrics.flow_efficiency import time_in_status_totals, time_in_status_by_month
import config

st.set_page_config(layout="wide")
st.title("Tempo por Status")

if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df = st.session_state.filtered_df if "filtered_df" in st.session_state else st.session_state.items_df
time_by_status = st.session_state.get("time_by_status_df", pd.DataFrame())

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("""
    <div style="background:#f5f5f5;border-radius:8px;padding:14px;font-size:13px;">
    A métrica de tempo por status <b style="color:#4472C4;">quantifica o tempo, em horas úteis, que cada item permanece em um determinado status dentro de um processo.</b>
    Este cálculo é feito somando-se as horas que os itens ficam em cada status, permitindo a identificação e análise de possíveis pontos de congestionamento no fluxo de trabalho.<br><br>
    <b style="color:#FFA500;">OBS:</b> o cálculo de horas úteis leva em consideração o intervalo de 8h às 18h.
    Sendo computado no máximo 8 horas por dia útil (excluindo feriado nacional e fim de semana).
    </div>
    """, unsafe_allow_html=True)

with col2:
    totals = time_in_status_totals(time_by_status)
    if not totals.empty:
        totals["hours_k"] = totals["hours"] / 1000
        fig = horizontal_bar(totals, "status", "hours", list(config.STATUS_COLORS.values()),
                              "Tempo por Status (horas) - Geral")
        # Formata labels em K
        import plotly.graph_objects as go
        import plotly.colors as pc
        _palette = pc.qualitative.Plotly + pc.qualitative.D3 + pc.qualitative.Set3
        _status_list = list(totals["status"])
        fig2 = go.Figure()
        for i, (_, row) in enumerate(totals.iterrows()):
            color = config.STATUS_COLORS.get(row["status"], _palette[i % len(_palette)])
            label = f"{row['hours']/1000:.1f}K" if row["hours"] >= 1000 else f"{row['hours']:.0f}"
            fig2.add_trace(go.Bar(
                y=[row["status"]],
                x=[row["hours"]],
                orientation="h",
                marker_color=color,
                text=[label],
                textposition="outside",
                showlegend=False,
            ))
        fig2.update_layout(title="Tempo por Status (horas) - Geral",
                            plot_bgcolor="white", paper_bgcolor="white",
                            margin=dict(l=160, r=40, t=40, b=20))
        st.plotly_chart(fig2, use_container_width=True)

# ─── Stacked bar % por mês ────────────────────────────────────────────────────
st.subheader("Tempo por Status - Geral (% mensal)")

monthly_pct = time_in_status_by_month(df, time_by_status)

with st.expander("🔍 Debug: Tempo por Status Mensal", expanded=False):
    st.write(f"**time_by_status shape:** {time_by_status.shape}")
    st.write(f"**df (filtered) shape:** {df.shape}")
    st.write(f"**df entregues (closed_date notna):** {df['closed_date'].notna().sum()}")
    if not time_by_status.empty:
        st.write(f"**time_by_status item_ids (amostra):** {list(time_by_status['item_id'].head(5))}")
        st.write(f"**df ids (amostra):** {list(df['id'].head(5))}")
        ids_comuns = set(time_by_status['item_id']).intersection(set(df['id']))
        st.write(f"**IDs em comum:** {len(ids_comuns)}")
    st.write(f"**monthly_pct shape:** {monthly_pct.shape}")
    if not monthly_pct.empty:
        st.dataframe(monthly_pct.head())

if not monthly_pct.empty:
    status_cols = [c for c in monthly_pct.columns if c != "month"]
    fig_stack = stacked_bar_pct_monthly(monthly_pct, "month", status_cols,
                                         "Tempo por Status - Geral")
    st.plotly_chart(fig_stack, use_container_width=True)
else:
    st.info("Dados de histórico de estados não disponíveis. Certifique-se de que o histórico foi carregado.")

# ─── Relação de Itens Entregues ────────────────────────────────────────────────
st.subheader("Relação de Itens Entregues")

delivered = df[df["closed_date"].notna()].copy()
if not delivered.empty:
    cols_show = {
        "id": "Código Item",
        "title": "Título",
        "team": "Equipe",
        "priority": "Prioridade",
        "item_type_general": "Tipo Item Geral",
        "type": "Tipo Item Original",
        "closed_date": "Dt. Criação",
        "cycle_time": "Cycle Time",
        "lead_time": "Lead Time",
        "vazao_qualificada": "Vazão Qualificada",
    }
    show_df = delivered[[c for c in cols_show.keys() if c in delivered.columns]].copy()
    show_df = show_df.rename(columns=cols_show)

    if "Dt. Criação" in show_df.columns:
        show_df["Dt. Criação"] = show_df["Dt. Criação"].dt.strftime("%m/%d/%Y %I:%M:%S %p")
    if "Cycle Time" in show_df.columns:
        show_df["Cycle Time"] = show_df["Cycle Time"].round(2)
    if "Lead Time" in show_df.columns:
        show_df["Lead Time"] = show_df["Lead Time"].round(2)

    # Adiciona link para o Azure DevOps
    org = config.AZURE_ORG
    proj = config.AZURE_PROJECT
    if org and proj and "Código Item" in show_df.columns:
        show_df["Código Item"] = show_df["Código Item"].apply(
            lambda x: f"TEC-{x}"
        )

    st.dataframe(show_df.sort_values("Dt. Criação", ascending=False) if "Dt. Criação" in show_df.columns else show_df,
                  use_container_width=True, hide_index=True)

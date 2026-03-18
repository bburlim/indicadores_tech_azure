"""Página principal: seleção de período e carregamento de dados."""
import streamlit as st
import pandas as pd
from datetime import date
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config

st.set_page_config(
    page_title="Indicadores de Eficiência de Tecnologia",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Cabeçalho ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(90deg,#4472C4,#7B7BC8);border-radius:10px;padding:16px 24px;margin-bottom:16px;">
    <h1 style="color:white;margin:0;font-size:22px;">📊 Indicadores de Eficiência de Tecnologia</h1>
</div>
""", unsafe_allow_html=True)

# Valida se as credenciais estão configuradas
if not config.AZURE_ORG or not config.AZURE_PROJECT or not config.AZURE_PAT:
    st.error(
        "Credenciais do Azure DevOps não configuradas. "
        "Preencha `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT` e `AZURE_DEVOPS_PAT` "
        "no arquivo `.env` (local) ou em **Settings → Secrets** no Streamlit Cloud."
    )
    st.code("""
# .env
AZURE_DEVOPS_ORG=emiteai
AZURE_DEVOPS_PROJECT=seu-projeto
AZURE_DEVOPS_PAT=seu-pat-aqui
    """)
    st.stop()

# ─── Controles de carregamento ────────────────────────────────────────────────
with st.expander("⚙️ Período e opções de carregamento", expanded="items_df" not in st.session_state):
    col1, col2 = st.columns(2)
    with col1:
        start_date = col1.date_input("Data início", value=date(date.today().year, 1, 1))
        end_date = col2.date_input("Data fim", value=date.today())
    with col2:
        load_history = st.checkbox(
            "Carregar histórico de estados",
            value=True,
            help="Necessário para Tempo por Status e Eficiência de Fluxo. Mais lento na primeira carga.",
        )
        backlog_window = st.slider(
            "Janela do backlog aberto (dias atrás)",
            min_value=30, max_value=730, value=180, step=30,
            help="Itens abertos criados há mais tempo que isso são ignorados.",
        )

    load_btn = st.button("🔄 Carregar Dados", type="primary")

# ─── Carregamento ─────────────────────────────────────────────────────────────
if load_btn:
    from data.azure_client import fetch_work_items, fetch_state_history
    from data.processor import enrich_items

    with st.spinner("Buscando work items..."):
        items_df = fetch_work_items(str(start_date), str(end_date), backlog_window_days=backlog_window)

    if items_df.empty:
        st.warning("Nenhum item encontrado para o período selecionado.")
    else:
        st.success(f"✅ {len(items_df)} itens carregados.")

        history_df = pd.DataFrame()
        if load_history:
            delivered_ids = tuple(items_df[items_df["closed_date"].notna()]["id"].tolist())
            st.info(
                f"🔎 Buscando histórico de {len(delivered_ids)} itens entregues "
                f"(de {len(items_df)} total) em paralelo..."
            )
            history_df = fetch_state_history(delivered_ids)
            st.success(f"✅ {len(history_df)} transições de estado carregadas.")

        with st.spinner("Calculando métricas..."):
            from metrics.flow_efficiency import flow_efficiency_per_item
            items_enriched, time_by_status = enrich_items(items_df, history_df)
            if not time_by_status.empty:
                items_enriched = flow_efficiency_per_item(items_enriched, time_by_status)

        st.session_state["items_df"] = items_enriched
        st.session_state["history_df"] = history_df
        st.session_state["time_by_status_df"] = time_by_status
        st.session_state["filtered_df"] = items_enriched.copy()
        st.rerun()

# ─── Filtros Globais (sidebar) ────────────────────────────────────────────────
if "items_df" in st.session_state and st.session_state.items_df is not None:
    df = st.session_state.items_df

    st.sidebar.header("🔍 Filtros Globais")

    all_dates = df["closed_date"].dropna()
    min_d = all_dates.min().date() if not all_dates.empty else date(2025, 1, 1)
    max_d = all_dates.max().date() if not all_dates.empty else date.today()

    c1, c2 = st.sidebar.columns(2)
    f_start = c1.date_input("Início", value=min_d, min_value=min_d, max_value=max_d, key="f_start")
    f_end = c2.date_input("Fim", value=max_d, min_value=min_d, max_value=max_d, key="f_end")

    def ms(label, col):
        opts = sorted([x for x in df[col].dropna().unique() if x != ""]) if col in df.columns else []
        return st.sidebar.multiselect(label, options=opts, key=f"ms_{col}")

    teams = ms("Equipe", "team")
    segment = ms("Segmento", "segment")
    product = ms("Produto", "product")
    functional_team = ms("Time Funcional", "functional_team")
    journey = ms("Jornada", "journey")
    project = ms("Projeto", "project")
    feature = ms("Funcionalidade", "feature")
    platform = ms("Plataforma", "platform")
    book_team = ms("Equipe Book de Tech", "book_team")

    from data.processor import filter_items
    filtered = filter_items(
        df,
        start_date=str(f_start), end_date=str(f_end),
        teams=teams or None,
        segment=segment or None,
        product=product or None,
        functional_team=functional_team or None,
        journey=journey or None,
        project=project or None,
        feature=feature or None,
        platform=platform or None,
        book_team=book_team or None,
    )
    st.session_state["filtered_df"] = filtered

    # ─── Resumo ───────────────────────────────────────────────────────────────
    st.subheader("Resumo dos Dados Carregados")

    delivered = filtered[filtered["closed_date"].notna()]
    backlog = filtered[filtered["closed_date"].isna()]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total de Itens", len(filtered))
    m2.metric("Entregues", len(delivered))
    m3.metric("Backlog", len(backlog))
    m4.metric("Equipes", filtered["team"].nunique())
    m5.metric("Data Atualização", pd.Timestamp.now().strftime("%m/%d/%Y %H:%M"))

    st.markdown("**Preview dos Itens** (10 primeiros entregues)")
    preview_cols = ["id", "title", "team", "type", "state", "created_date", "closed_date", "cycle_time", "lead_time", "vazao_qualificada"]
    preview = delivered[[c for c in preview_cols if c in delivered.columns]].head(10)
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.info("👈 Use o menu lateral para navegar entre as páginas de indicadores.")

else:
    st.markdown("""
    Selecione o período desejado e clique em **Carregar Dados** para iniciar.

    **Páginas disponíveis após o carregamento:**
    - **Produtividade** — Throughput, Backlog, Burn-down, Vazão Qualificada
    - **Lead/Cycle Time** — P85, Desvio Padrão, por Equipe, Tendências
    - **Eficiência de Fluxo** — Touch Time vs. Wait Time
    - **Qualidade** — Retrabalho, Saúde Backlog, SLA, Defeitos por Origem
    - **Tempo por Status** — Horas úteis em cada status
    """)

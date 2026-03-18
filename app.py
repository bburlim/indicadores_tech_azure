"""Página principal: configuração de credenciais e carregamento de dados."""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

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

# ─── Configuração de Credenciais ──────────────────────────────────────────────
with st.expander("⚙️ Configuração — Azure DevOps", expanded="items_df" not in st.session_state):
    col1, col2 = st.columns(2)
    with col1:
        azure_org = st.text_input("Organização", value=os.getenv("AZURE_DEVOPS_ORG", ""),
                                   placeholder="minha-org", key="azure_org")
        azure_project = st.text_input("Projeto", value=os.getenv("AZURE_DEVOPS_PROJECT", ""),
                                       placeholder="meu-projeto", key="azure_project")
    with col2:
        azure_pat = st.text_input("Personal Access Token (PAT)", value=os.getenv("AZURE_DEVOPS_PAT", ""),
                                   type="password", key="azure_pat",
                                   help="Crie um PAT com permissão de leitura em Work Items")
        load_history = st.checkbox("Carregar histórico de estados (mais lento, necessário para Tempo por Status e Eficiência de Fluxo)",
                                    value=True)

    st.markdown("**Período de Entrega**")
    c1, c2 = st.columns(2)
    start_date = c1.date_input("Data início", value=date(date.today().year, 1, 1))
    end_date = c2.date_input("Data fim", value=date.today())

    load_btn = st.button("🔄 Carregar Dados", type="primary")

# ─── Carregamento ─────────────────────────────────────────────────────────────
if load_btn:
    if not azure_org or not azure_project or not azure_pat:
        st.error("Preencha Organização, Projeto e PAT antes de carregar os dados.")
    else:
        # Atualiza config dinâmico
        import config
        config.AZURE_ORG = azure_org
        config.AZURE_PROJECT = azure_project
        config.AZURE_PAT = azure_pat
        config.AZURE_BASE_URL = f"https://dev.azure.com/{azure_org}/{azure_project}/_apis"

        from data.azure_client import fetch_work_items, fetch_state_history
        from data.processor import enrich_items

        with st.spinner("Buscando work items..."):
            items_df = fetch_work_items(str(start_date), str(end_date))

        if items_df.empty:
            st.warning("Nenhum item encontrado para o período e filtros selecionados.")
        else:
            st.success(f"✅ {len(items_df)} itens carregados.")

            history_df = pd.DataFrame()
            if load_history:
                # Histórico só é necessário para itens entregues (ciclo completo)
                # Itens em aberto no backlog não têm closed_date e não precisam de histórico
                delivered_ids = tuple(
                    items_df[items_df["closed_date"].notna()]["id"].tolist()
                )
                total_items = len(items_df)
                st.info(
                    f"🔎 {len(delivered_ids)} itens entregues (de {total_items} total) "
                    f"— buscando histórico de estados em paralelo..."
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

    # Datas
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

    # Aplica filtros
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

    # Preview
    st.markdown("**Preview dos Itens** (10 primeiros entregues)")
    preview_cols = ["id", "title", "team", "type", "state", "created_date", "closed_date", "cycle_time", "lead_time", "vazao_qualificada"]
    preview = delivered[[c for c in preview_cols if c in delivered.columns]].head(10)
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.info("👈 Use o menu lateral para navegar entre as páginas de indicadores.")

else:
    st.markdown("""
    ## Como usar

    1. **Configure as credenciais** do Azure DevOps acima (Organização, Projeto, PAT)
    2. **Selecione o período** de entrega desejado
    3. Clique em **Carregar Dados**
    4. Use os **filtros** na sidebar para refinar a visualização
    5. Navegue pelas **páginas** de indicadores no menu lateral

    ---

    ### Páginas disponíveis:
    - **Produtividade**: Throughput, Backlog, Vazão Qualificada
    - **Lead/Cycle Time**: P85, Desvio Padrão, por Equipe, Tendências
    - **Eficiência de Fluxo**: Touch Time vs. Wait Time por mês e equipe
    - **Qualidade**: Retrabalho, Saúde Backlog, SLA, Defeitos por Origem
    - **Tempo por Status**: Horas em cada status (horas úteis), visão mensal

    ---

    ### Como criar um PAT no Azure DevOps:
    1. Acesse `https://dev.azure.com/{sua-org}` → User Settings → Personal Access Tokens
    2. Crie um novo token com permissão **Work Items: Read**
    3. Cole o token acima
    """)

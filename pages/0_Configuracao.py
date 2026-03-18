"""Página: Configuração e diagnóstico de campos do Azure DevOps."""
import streamlit as st
import sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

st.set_page_config(layout="wide")
st.title("⚙️ Configuração e Diagnóstico")

# ─── Status da Conexão ────────────────────────────────────────────────────────
st.subheader("Status da Conexão")

col1, col2, col3 = st.columns(3)
col1.metric("Organização", config.AZURE_ORG or "❌ Não configurado")
col2.metric("Projeto", config.AZURE_PROJECT or "❌ Não configurado")
col3.metric("PAT", "✅ Configurado" if config.AZURE_PAT else "❌ Não configurado")

if config.AZURE_ORG and config.AZURE_PROJECT and config.AZURE_PAT:
    st.success(f"Conectado em: https://dev.azure.com/{config.AZURE_ORG}/{config.AZURE_PROJECT}")

    # ─── Campos Descobertos ───────────────────────────────────────────────────
    st.subheader("Campos Customizados Descobertos")
    st.markdown("O sistema detecta automaticamente os campos do seu processo no Azure DevOps:")

    with st.spinner("Consultando campos..."):
        from data.azure_client import get_discovered_fields, discover_custom_fields
        try:
            field_map = discover_custom_fields()
            rows = []
            labels = {
                "team": "Equipe",
                "segment": "Segmento",
                "product": "Produto",
                "functional_team": "Time Funcional",
                "journey": "Jornada",
                "project": "Projeto",
                "feature": "Funcionalidade",
                "platform": "Plataforma",
                "book_team": "Equipe Book de Tech",
            }
            for key, ref in field_map.items():
                rows.append({
                    "Campo Interno": labels.get(key, key),
                    "Referência Azure DevOps": ref,
                    "Status": "✅ Descoberto automaticamente" if not ref.startswith("Custom.") or key else "⚠️ Usando padrão",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Erro ao consultar campos: {e}")

    # ─── Work Item Types ──────────────────────────────────────────────────────
    st.subheader("Tipos de Work Item no Projeto")
    with st.spinner("Consultando tipos..."):
        try:
            import base64, requests
            token = base64.b64encode(f":{config.AZURE_PAT}".encode()).decode()
            headers = {"Authorization": f"Basic {token}"}
            url = f"https://dev.azure.com/{config.AZURE_ORG}/{config.AZURE_PROJECT}/_apis/wit/workitemtypes?api-version=7.1"
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                types = resp.json().get("value", [])
                type_names = [t["name"] for t in types]
                st.write(", ".join(type_names))

                # Detecta Bug e História
                bug_types = [t for t in type_names if "bug" in t.lower()]
                hist_types = [t for t in type_names if "hist" in t.lower() or "story" in t.lower() or "feature" in t.lower()]
                col1, col2 = st.columns(2)
                col1.info(f"**Tipos de Bug detectados:** {', '.join(bug_types) or 'Nenhum'}")
                col2.info(f"**Tipos de História detectados:** {', '.join(hist_types) or 'Nenhum'}")
            else:
                st.warning(f"Não foi possível listar tipos: {resp.status_code}")
        except Exception as e:
            st.error(f"Erro: {e}")

    # ─── Estados (Statuses) ───────────────────────────────────────────────────
    st.subheader("Verificação de Estados")
    st.markdown("Estados configurados no `config.py` vs. estados reais do seu processo:")

    all_cfg_statuses = config.ACTIVE_STATUSES + config.WAIT_STATUSES
    if "items_df" in st.session_state and st.session_state.items_df is not None:
        real_states = st.session_state.items_df["state"].unique().tolist()
        matched = [s for s in all_cfg_statuses if s in real_states]
        unmatched_cfg = [s for s in all_cfg_statuses if s not in real_states]
        extra_real = [s for s in real_states if s not in all_cfg_statuses]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.success(f"**Mapeados ({len(matched)}):**")
            for s in matched:
                st.write(f"  ✅ {s}")
        with col2:
            if unmatched_cfg:
                st.warning(f"**No config, não nos dados ({len(unmatched_cfg)}):**")
                for s in unmatched_cfg:
                    st.write(f"  ⚠️ {s}")
        with col3:
            if extra_real:
                st.info(f"**Nos dados, não no config ({len(extra_real)}):**")
                for s in extra_real:
                    st.write(f"  ℹ️ {s}")
        # Detecta estado de início do Cycle Time
        st.markdown("**Estado de início do Cycle Time detectado:**")
        history_df = st.session_state.get("history_df")
        if history_df is not None and not history_df.empty:
            all_hist_states = history_df["to_state"].dropna().unique().tolist()
            exact = config.CYCLE_TIME_START_STATUS
            if exact in all_hist_states:
                st.success(f"✅ Match exato: `{exact}`")
            else:
                fallback = [s for s in all_hist_states if "in progress" in s.lower() or "em andamento" in s.lower()]
                if fallback:
                    st.warning(f"⚠️ `{exact}` não encontrado. Usando fallback: `{', '.join(fallback)}`")
                    st.info(f"Para corrigir, altere `CYCLE_TIME_START_STATUS` em `config.py` para um desses valores.")
                else:
                    st.error(f"❌ Nenhum estado 'In Progress' encontrado. Estados disponíveis: {', '.join(sorted(all_hist_states))}")
        else:
            st.info("Carregue dados com histórico para verificar.")
    else:
        st.info("Carregue os dados na página principal para verificar os estados.")

    # ─── Ajuste Manual de Campos ──────────────────────────────────────────────
    st.subheader("Ajuste Manual de Campos (opcional)")
    st.markdown("Se algum campo não foi detectado corretamente, edite o `config.py` ou informe aqui:")

    with st.expander("Sobrescrever mapeamento de campos"):
        st.code("""
# Exemplo: se o campo de Equipe se chama 'Custom.Time' no seu projeto
# Edite o arquivo config.py ou .env e adicione:
FIELD_TEAM=Custom.Time
FIELD_SEGMENT=Custom.Segmento
        """)
        st.info("Por enquanto, edite diretamente o arquivo `data/azure_client.py`, função `_default_field_map()`.")

else:
    st.warning("Configure as credenciais na página inicial para usar o diagnóstico.")
    st.markdown("""
    **Como criar um PAT no Azure DevOps:**
    1. Acesse `https://dev.azure.com/emiteai` → avatar no canto superior direito → **Personal Access Tokens**
    2. Clique em **+ New Token**
    3. Nome: `indicadores-streamlit`
    4. Validade: 1 ano
    5. Permissões: marque **Work Items → Read**
    6. Copie o token e cole no arquivo `.env`:
    ```
    AZURE_DEVOPS_PAT=seu-token-aqui
    ```
    """)

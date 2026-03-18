"""Azure DevOps REST API client."""
import base64
import requests
import pandas as pd
import streamlit as st
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# Mapeamento de campos customizados descobertos dinamicamente
# chave interna → referência do campo no Azure DevOps
_CUSTOM_FIELD_MAP: dict = {}


def _get_headers() -> dict:
    token = base64.b64encode(f":{config.AZURE_PAT}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _get(url: str, params: dict = None) -> dict:
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _post(url: str, body: dict) -> dict:
    resp = requests.post(url, headers=_get_headers(), json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=config.CACHE_TTL, show_spinner="Descobrindo campos do Azure DevOps...")
def discover_custom_fields() -> dict:
    """
    Consulta a API do Azure DevOps para descobrir os campos disponíveis
    no processo e mapear automaticamente os campos customizados.

    Retorna dict: {campo_interno: referencia_azure}
    """
    try:
        # Busca todos os campos do projeto
        url = f"{config.AZURE_BASE_URL}/wit/fields?api-version=7.1"
        data = _get(url)
        fields = data.get("value", [])
    except Exception:
        return _default_field_map()

    # Normaliza nomes para comparação (lower, sem espaços/underscores)
    def normalize(s: str) -> str:
        return s.lower().replace(" ", "").replace("_", "").replace("-", "")

    # Nomes que queremos encontrar (interno → variações possíveis)
    targets = {
        "team": ["equipe", "team", "squad"],
        "segment": ["segmento", "segment"],
        "product": ["produto", "product"],
        "functional_team": ["timefuncional", "functionalteam", "timefunc"],
        "journey": ["jornada", "journey"],
        "project": ["projeto", "project"],
        "feature": ["funcionalidade", "feature"],
        "platform": ["plataforma", "platform"],
        "book_team": ["equipebookdetech", "bookoftech", "booktech"],
    }

    result = {}
    custom_fields = [f for f in fields if f.get("referenceName", "").startswith(("Custom.", "System.") is False or True)]
    custom_fields = [f for f in fields if not f.get("referenceName", "").startswith("System.")
                     and not f.get("referenceName", "").startswith("Microsoft.")]

    for internal_key, variations in targets.items():
        for field in custom_fields:
            ref = field.get("referenceName", "")
            name = normalize(field.get("name", ""))
            ref_norm = normalize(ref.split(".")[-1])  # parte após o ponto

            for variation in variations:
                if variation in name or variation in ref_norm:
                    result[internal_key] = ref
                    break
            if internal_key in result:
                break

    # Fallback para campos não encontrados
    defaults = _default_field_map()
    for key, val in defaults.items():
        if key not in result:
            result[key] = val

    return result


def _default_field_map() -> dict:
    """Mapeamento padrão caso a auto-descoberta falhe."""
    return {
        "team": "Custom.Equipe",
        "segment": "Custom.Segmento",
        "product": "Custom.Produto",
        "functional_team": "Custom.TimeFuncional",
        "journey": "Custom.Jornada",
        "project": "Custom.Projeto",
        "feature": "Custom.Funcionalidade",
        "platform": "Custom.Plataforma",
        "book_team": "Custom.EquipeBookDeTech",
    }


@st.cache_data(ttl=config.CACHE_TTL, show_spinner="Consultando work items no Azure DevOps...")
def fetch_work_items(
    start_date: str,
    end_date: str,
    work_item_types: Optional[list] = None,
) -> pd.DataFrame:
    """
    Busca work items entregues (Done/Closed) no período e items em aberto.
    Retorna DataFrame com campos básicos.
    """
    types_filter = ""
    if work_item_types:
        types_str = ", ".join(f"'{t}'" for t in work_item_types)
        types_filter = f"AND [System.WorkItemType] IN ({types_str})"

    wiql = f"""
    SELECT [System.Id]
    FROM WorkItems
    WHERE [System.TeamProject] = '{config.AZURE_PROJECT}'
    {types_filter}
    AND (
        (
            [System.State] IN ('Done', 'Closed', 'Resolved')
            AND [Microsoft.VSTS.Common.ClosedDate] >= '{start_date}'
            AND [Microsoft.VSTS.Common.ClosedDate] <= '{end_date}'
        )
        OR [System.State] NOT IN ('Done', 'Closed', 'Resolved', 'Removed')
    )
    ORDER BY [System.Id] DESC
    """

    url = f"{config.AZURE_BASE_URL}/wit/wiql?api-version=7.1"
    result = _post(url, {"query": wiql})
    ids = [item["id"] for item in result.get("workItems", [])]

    if not ids:
        return pd.DataFrame()

    # Descobre campos customizados
    field_map = discover_custom_fields()
    return _fetch_item_details(ids, field_map)


def _fetch_item_details(ids: list, field_map: dict) -> pd.DataFrame:
    """Busca detalhes dos work items em lotes de 200."""
    base_fields = [
        "System.Id",
        "System.Title",
        "System.WorkItemType",
        "System.State",
        "System.CreatedDate",
        "Microsoft.VSTS.Common.ClosedDate",
        "System.AreaPath",
        "System.Tags",
        "Microsoft.VSTS.Common.Priority",
    ]
    custom_fields = list(set(field_map.values()))
    fields = base_fields + custom_fields

    all_items = []
    batch_size = 200

    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        ids_str = ",".join(str(x) for x in batch)
        fields_str = ",".join(fields)
        url = f"{config.AZURE_BASE_URL}/wit/workitems?ids={ids_str}&fields={fields_str}&api-version=7.1"
        try:
            data = _get(url)
            all_items.extend(data.get("value", []))
        except Exception as e:
            # Tenta sem os campos customizados se der erro
            fields_str = ",".join(base_fields)
            url = f"{config.AZURE_BASE_URL}/wit/workitems?ids={ids_str}&fields={fields_str}&api-version=7.1"
            data = _get(url)
            all_items.extend(data.get("value", []))

    rows = []
    for item in all_items:
        f = item.get("fields", {})

        # Resolve campos customizados com fallback para area path
        team_ref = field_map.get("team", "Custom.Equipe")
        team_val = f.get(team_ref) or _extract_team_from_area(f.get("System.AreaPath", ""))

        rows.append(
            {
                "id": item["id"],
                "title": f.get("System.Title", ""),
                "type": f.get("System.WorkItemType", ""),
                "state": f.get("System.State", ""),
                "created_date": f.get("System.CreatedDate"),
                "closed_date": f.get("Microsoft.VSTS.Common.ClosedDate"),
                "area_path": f.get("System.AreaPath", ""),
                "tags": f.get("System.Tags", ""),
                "priority": f.get("Microsoft.VSTS.Common.Priority", ""),
                "team": team_val,
                "segment": f.get(field_map.get("segment", "Custom.Segmento"), ""),
                "product": f.get(field_map.get("product", "Custom.Produto"), ""),
                "functional_team": f.get(field_map.get("functional_team", "Custom.TimeFuncional"), ""),
                "journey": f.get(field_map.get("journey", "Custom.Jornada"), ""),
                "project": f.get(field_map.get("project", "Custom.Projeto"), ""),
                "feature": f.get(field_map.get("feature", "Custom.Funcionalidade"), ""),
                "platform": f.get(field_map.get("platform", "Custom.Plataforma"), ""),
                "book_team": f.get(field_map.get("book_team", "Custom.EquipeBookDeTech"), ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["created_date"] = pd.to_datetime(df["created_date"], utc=True)
    df["closed_date"] = pd.to_datetime(df["closed_date"], utc=True)
    df["item_type_general"] = df["type"].apply(_classify_type_general)

    return df


def _extract_team_from_area(area_path: str) -> str:
    if not area_path:
        return ""
    parts = area_path.split("\\")
    return parts[-1] if len(parts) > 1 else area_path


def _classify_type_general(work_item_type: str) -> str:
    wt = work_item_type.lower()
    if "bug" in wt or "defeito" in wt:
        return "Defeito"
    return "História"


@st.cache_data(ttl=config.CACHE_TTL, show_spinner="Buscando histórico de estados...")
def fetch_state_history(item_ids: tuple) -> pd.DataFrame:
    """
    Busca o histórico de mudanças de estado para uma lista de IDs.
    Retorna DataFrame com: item_id, from_state, to_state, changed_date
    """
    rows = []
    for item_id in item_ids:
        url = f"{config.AZURE_BASE_URL}/wit/workitems/{item_id}/updates?api-version=7.1"
        try:
            data = _get(url)
        except Exception:
            continue

        for update in data.get("value", []):
            fields = update.get("fields", {})
            state_change = fields.get("System.State")
            if state_change:
                rows.append(
                    {
                        "item_id": item_id,
                        "from_state": state_change.get("oldValue", ""),
                        "to_state": state_change.get("newValue", ""),
                        "changed_date": (
                            update.get("revisedDate")
                            or update.get("fields", {})
                            .get("System.ChangedDate", {})
                            .get("newValue")
                        ),
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["item_id", "from_state", "to_state", "changed_date"])

    df = pd.DataFrame(rows)
    df["changed_date"] = pd.to_datetime(df["changed_date"], utc=True)
    df = df.sort_values(["item_id", "changed_date"]).reset_index(drop=True)
    return df


def get_discovered_fields() -> dict:
    """Retorna o mapeamento de campos descoberto (para debug na UI)."""
    try:
        return discover_custom_fields()
    except Exception:
        return _default_field_map()

"""
Configurações do projeto.
Lê credenciais do .env (local) ou st.secrets (Streamlit Cloud).
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str, default: str = "") -> str:
    """Lê do st.secrets (Streamlit Cloud) ou env vars (local)."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# Azure DevOps
AZURE_ORG = _get_secret("AZURE_DEVOPS_ORG", "emiteai")
AZURE_PROJECT = _get_secret("AZURE_DEVOPS_PROJECT", "")
AZURE_PAT = _get_secret("AZURE_DEVOPS_PAT", "")

AZURE_BASE_URL = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis"

# Cache
CACHE_TTL = int(_get_secret("CACHE_TTL", "3600"))

# ─── Status do processo ───────────────────────────────────────────────────────
ACTIVE_STATUSES = [
    "In Progress - Tec",
    "Dev Adjust - Tec",
    "Review - Tec",
    "Qa - Tec",
    "Releasing - Tec",
    "Infra - Tec",
]

WAIT_STATUSES = [
    "Selected - Tec",
    "Waiting Review - Tec",
    "Waiting Qa - Tec",
    "Waiting Infra - Tec",
    "Waiting Release - Tec",
]

ALL_STATUSES = ACTIVE_STATUSES + WAIT_STATUSES

CYCLE_TIME_START_STATUS = "In Progress - Tec"

DONE_STATES = ["Done", "Closed", "Resolved"]

# Tipos de item
BUG_TYPES = ["Bug - Tec", "Bug"]
HISTORY_TYPES = ["History - Tec", "User Story", "História"]

# Horário útil (horas úteis para Tempo por Status)
WORK_START_HOUR = 8
WORK_END_HOUR = 18
MAX_HOURS_PER_DAY = WORK_END_HOUR - WORK_START_HOUR  # 10h

# ─── Benchmarks ───────────────────────────────────────────────────────────────
FLOW_EFFICIENCY_BENCH = 40   # % (ideal > 40%)
REWORK_BENCH = 20            # % (ideal < 20%)
BACKLOG_HEALTH_BENCH = 80    # % histórias no backlog

# ─── Vazão Qualificada - pesos ─────────────────────────────────────────────────
# Defeitos: 0.5 pts | Histórias: ≤1d=0, 1-3d=0.5, 4-10d=1, ≥11d=2
VAZAO_WEIGHTS = [
    {"min": 0, "max": 1, "type": "historia", "weight": 0},
    {"min": 1, "max": 3, "type": "historia", "weight": 0.5},
    {"min": 4, "max": 10, "type": "historia", "weight": 1},
    {"min": 11, "max": float("inf"), "type": "historia", "weight": 2},
    {"min": 0, "max": float("inf"), "type": "bug", "weight": 0.5},
]

# ─── Cores por status ─────────────────────────────────────────────────────────
STATUS_COLORS = {
    "Dev Adjust - Tec":     "#4040FF",
    "In Progress - Tec":    "#1C1C1C",
    "Infra - Tec":          "#D3D3D3",
    "Qa - Tec":             "#228B22",
    "Releasing - Tec":      "#00CED1",
    "Review - Tec":         "#87CEEB",
    "Selected - Tec":       "#FFA500",
    "Waiting Infra - Tec":  "#8B0000",
    "Waiting Qa - Tec":     "#008080",
    "Waiting Release - Tec":"#FFB6C1",
    "Waiting Review - Tec": "#90EE90",
}

TEAM_COLORS = ["#4472C4", "#ED7D31", "#A9D18E", "#FF0000", "#FFC000", "#70AD47", "#5B9BD5"]

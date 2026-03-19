"""Página: Bugs — Dashboard de acompanhamento de defeitos."""
import streamlit as st
import sys, os
import pandas as pd
import plotly.graph_objects as go
import plotly.colors as pc
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

st.set_page_config(layout="wide")
st.title("Bugs")

if "items_df" not in st.session_state or st.session_state.items_df is None:
    st.warning("Configure as credenciais do Azure DevOps na página inicial e carregue os dados.")
    st.stop()

df_all = st.session_state.items_df
df = st.session_state.filtered_df if "filtered_df" in st.session_state else df_all

today = pd.Timestamp.now(tz="UTC").normalize()
SLA_DAYS = 15

# ─── Base de bugs ─────────────────────────────────────────────────────────────
bugs = df[df["item_type_general"] == "Defeito"].copy()
bugs_open = bugs[bugs["closed_date"].isna()].copy()
bugs_closed = bugs[bugs["closed_date"].notna()].copy()

# ─── Bugs Pendentes Time Sustentação (primeiro donut) ─────────────────────────
# Query: Bug | State IN (estados pendentes) | Categoria = Externo | Chamado > 0
# | Area Path = EmiteAi\Prod Time Sustentação
_PENDING_STATES = [
    "ag. desenvolvimento", "para fazer", "validação", "validacao",
    "impedimento", "em andamento", "code review", "aguardando release",
    "aguardando code review", "release", "aguardando", "backlog",
    "pronta para desenvolvimento", "refinamento", "discovery",
]

def _is_pending_state(state: str) -> bool:
    sl = str(state).lower()
    return any(s in sl for s in _PENDING_STATES)

bugs_sustentacao = bugs[
    bugs["area_path"].str.contains("Sustenta", na=False, case=False) |
    bugs["team"].str.contains("Sustenta", na=False, case=False)
].copy()

bugs_sustentacao_pendentes = bugs_sustentacao[
    bugs_sustentacao["state"].apply(_is_pending_state) &
    bugs_sustentacao["closed_date"].isna()
].copy()

# Filtro Categoria = Externo (se campo disponível e preenchido)
if "categoria" in bugs_sustentacao_pendentes.columns:
    filled = bugs_sustentacao_pendentes["categoria"].notna() & (bugs_sustentacao_pendentes["categoria"] != "")
    if filled.any():
        bugs_sustentacao_pendentes = bugs_sustentacao_pendentes[
            bugs_sustentacao_pendentes["categoria"].str.lower().str.contains("externo|external", na=False)
        ]

# Filtro Chamado > 0 (se campo disponível e preenchido)
if "chamado" in bugs_sustentacao_pendentes.columns:
    chamado_num = pd.to_numeric(bugs_sustentacao_pendentes["chamado"], errors="coerce")
    if chamado_num.notna().any():
        bugs_sustentacao_pendentes = bugs_sustentacao_pendentes[chamado_num.fillna(0) > 0]

# Dias em aberto para bugs sem entrega
bugs_open["days_open"] = (today - bugs_open["created_date"]).dt.days.fillna(0).astype(int)

# ─── KPIs ─────────────────────────────────────────────────────────────────────
total_open = len(bugs_open)
total_pendentes = len(bugs_open)

# Abertos hoje
opened_today = len(bugs[
    bugs["created_date"].dt.normalize() == today
])

# Concluídos hoje
closed_today = len(bugs_closed[
    bugs_closed["closed_date"].dt.normalize() == today
])

# Bugs abertos no mês atual
abertos_mes = len(bugs[
    (bugs["created_date"].dt.year == today.year) &
    (bugs["created_date"].dt.month == today.month)
])

# SLA
a_vencer = len(bugs_open[
    (bugs_open["days_open"] >= SLA_DAYS - 3) &
    (bugs_open["days_open"] < SLA_DAYS)
])
a_vencer_3 = len(bugs_open[
    (bugs_open["days_open"] >= SLA_DAYS - 3) &
    (bugs_open["days_open"] < SLA_DAYS)
])
vencidos = len(bugs_open[bugs_open["days_open"] >= SLA_DAYS])

# Prioridade
def _is_high(row):
    s = str(row.get("severity", row.get("priority", ""))).lower().strip()
    return any(k in s for k in ("1", "2", "alta", "alto", "críti", "criti", "high", "critical"))

def _is_medium(row):
    s = str(row.get("severity", row.get("priority", ""))).lower().strip()
    return any(k in s for k in ("3", "média", "medio", "médio", "medium"))

bugs_alta_sup = len(bugs_open[bugs_open.apply(_is_high, axis=1)])
bugs_media = len(bugs_open[bugs_open.apply(_is_medium, axis=1)])

# Dúvidas (tipo ou tag com "dúvida"/"duvida")
duvidas = len(bugs_open[
    bugs_open["type"].str.lower().str.contains("dúvida|duvida|doubt", na=False) |
    bugs_open.get("tags", pd.Series("", index=bugs_open.index)).str.lower().str.contains("dúvida|duvida", na=False)
])

# Estado específico
def _count_by_state(df_bugs, keyword):
    return len(df_bugs[df_bugs["state"].str.lower().str.contains(keyword, na=False)])

bugs_validacao = _count_by_state(bugs_open, "valid")
bugs_impedimento = _count_by_state(bugs_open, "impedi")
bugs_code_review = _count_by_state(bugs_open, "code review|codereview")

# ─── Bugs por status (donut) ──────────────────────────────────────────────────
palette = pc.qualitative.Plotly + pc.qualitative.D3 + pc.qualitative.Set3

def donut_by_state(df_bugs, title):
    counts = df_bugs["state"].value_counts().reset_index()
    counts.columns = ["state", "count"]
    colors = [config.STATUS_COLORS.get(s, palette[i % len(palette)])
              for i, s in enumerate(counts["state"])]
    fig = go.Figure(go.Pie(
        labels=counts["state"],
        values=counts["count"],
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+value",
        textposition="outside",
        showlegend=True,
    ))
    fig.update_layout(
        title=title,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=60),
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        annotations=[dict(text=str(len(df_bugs)), x=0.5, y=0.5,
                          font_size=36, showarrow=False, font_color="#333")],
    )
    return fig

# ─── Bugs por prioridade (donut) ─────────────────────────────────────────────
_SEV_LABEL_MAP = {
    "1": "Crítica", "2": "Alta", "3": "Média", "4": "Baixa",
    1: "Crítica", 2: "Alta", 3: "Média", 4: "Baixa",
    "1 - critical": "Crítica", "2 - high": "Alta",
    "3 - medium": "Média", "4 - low": "Baixa",
    "1 - crítico": "Crítica", "2 - alto": "Alta",
    "3 - médio": "Média", "4 - baixo": "Baixa",
    "crítica": "Crítica", "alta": "Alta",
    "média": "Média", "baixa": "Baixa",
    "critical": "Crítica", "high": "Alta",
    "medium": "Média", "low": "Baixa",
}
_SEV_COLOR_MAP = {
    "Crítica": "#CC0000", "Alta": "#FF6600",
    "Média": "#FFA500", "Baixa": "#4472C4",
    "Sem severidade": "#AAAAAA",
}

def donut_by_priority(df_bugs, title):
    col = "severity" if "severity" in df_bugs.columns else "priority"
    labels = df_bugs[col].apply(
        lambda x: _SEV_LABEL_MAP.get(str(x).lower().strip(),
                  str(x)) if pd.notna(x) and str(x) != "" else "Sem severidade"
    )
    counts = labels.value_counts().reset_index()
    counts.columns = ["severity", "count"]
    order = ["Crítica", "Alta", "Média", "Baixa", "Sem severidade"]
    counts["_ord"] = counts["severity"].apply(lambda x: order.index(x) if x in order else 99)
    counts = counts.sort_values("_ord").drop(columns="_ord")

    colors = [_SEV_COLOR_MAP.get(p, "#AAAAAA") for p in counts["severity"]]
    fig = go.Figure(go.Pie(
        labels=counts["severity"],
        values=counts["count"],
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+value",
        textposition="outside",
        showlegend=True,
    ))
    fig.update_layout(
        title=title,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=20, r=20, t=40, b=60),
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        annotations=[dict(text=str(len(df_bugs)), x=0.5, y=0.5,
                          font_size=36, showarrow=False, font_color="#333")],
    )
    return fig

# ─── Bugs abertos por dia (últimos 10 dias) ───────────────────────────────────
def bar_daily_opened(df_bugs, days=10):
    rows = []
    for i in range(days - 1, -1, -1):
        d = (today - pd.Timedelta(days=i)).date()
        count = len(df_bugs[df_bugs["created_date"].dt.normalize() == pd.Timestamp(d, tz="UTC")])
        rows.append({"date": str(d), "count": count})
    day_df = pd.DataFrame(rows)
    colors = [palette[i % len(palette)] for i in range(len(day_df))]
    fig = go.Figure(go.Bar(x=day_df["date"], y=day_df["count"],
                            marker_color=colors, text=day_df["count"],
                            textposition="outside"))
    fig.update_layout(title="Bugs Abertos por Dia (últimos 10 dias)",
                      plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=20, r=20, t=40, b=20),
                      showlegend=False, yaxis=dict(title=""))
    return fig

def bar_daily_closed(df_bugs, days=10):
    rows = []
    for i in range(days - 1, -1, -1):
        d = (today - pd.Timedelta(days=i)).date()
        count = len(df_bugs[df_bugs["closed_date"].dt.normalize() == pd.Timestamp(d, tz="UTC")])
        rows.append({"date": str(d), "count": count})
    day_df = pd.DataFrame(rows)
    colors = [palette[i % len(palette)] for i in range(len(day_df))]
    fig = go.Figure(go.Bar(x=day_df["date"], y=day_df["count"],
                            marker_color=colors, text=day_df["count"],
                            textposition="outside"))
    fig.update_layout(title="Bugs Concluídos nos últimos 10 dias",
                      plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=20, r=20, t=40, b=20),
                      showlegend=False, yaxis=dict(title=""))
    return fig

# ─── KPI card colorido ────────────────────────────────────────────────────────
def kpi_colored(label, value, bg_color, text_color="#FFFFFF"):
    return f"""
    <div style="background:{bg_color};border-radius:8px;padding:16px 12px;text-align:left;height:100px;">
        <div style="font-size:13px;font-weight:bold;color:{text_color};">{label}</div>
        <div style="font-size:38px;font-weight:bold;color:{text_color};line-height:1.1;">{value}</div>
        <div style="font-size:11px;color:{text_color};opacity:0.85;">Work items</div>
    </div>
    """

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Linha 1: donuts (esquerda, empilhados) + KPI cards (direita) ─────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.plotly_chart(donut_by_state(
        bugs_sustentacao_pendentes,
        "Bugs Pendentes — Time Sustentação"
    ), use_container_width=True)
    st.plotly_chart(donut_by_priority(bugs_open, "Bugs Abertos por Severidade"), use_container_width=True)

with col_right:
    card_html = "".join([
        f"""<div style="background:{bg};border-radius:8px;padding:16px 12px;margin-bottom:10px;">
            <div style="font-size:13px;font-weight:bold;color:#fff;">{label}</div>
            <div style="font-size:38px;font-weight:bold;color:#fff;line-height:1.1;">{value}</div>
            <div style="font-size:11px;color:#fff;opacity:0.85;">Work items</div>
        </div>"""
        for label, value, bg in [
            ("Bugs Abertos",        total_open,     "#1E90FF"),
            ("Dúvidas Abertos",     duvidas,        "#20B2AA"),
            ("Bugs Média Severidade", bugs_media,   "#FFA500"),
            ("Bugs Alta / Sup",     bugs_alta_sup,  "#CC0000"),
        ]
    ])
    st.markdown(card_html, unsafe_allow_html=True)

st.divider()

# ─── Linha 2: barras diárias lado a lado ──────────────────────────────────────
col_bar1, col_bar2 = st.columns(2)
with col_bar1:
    st.plotly_chart(bar_daily_opened(bugs), use_container_width=True)
with col_bar2:
    st.plotly_chart(bar_daily_closed(bugs_closed), use_container_width=True)

st.divider()

# ─── Linha 3: 10 KPI cards coloridos ──────────────────────────────────────────
kpis = [
    ("Abertos no Mês",      abertos_mes,       "#E6A817"),
    ("Pendentes",           total_pendentes,   "#D17A00"),
    ("Abertos HOJE",        opened_today,      "#F0C040"),
    ("À Vencer",            a_vencer,          "#D45B00"),
    ("À Vencer Próx 3 dias",a_vencer_3,        "#228B22"),
    ("Concluídos HOJE",     closed_today,      "#2E8B57"),
    ("Validação",           bugs_validacao,    "#2E8B8B"),
    ("Vencidos",            vencidos,          "#CC0000"),
    ("Bugs Impedimento",    bugs_impedimento,  "#8B0000"),
    ("Code Review",         bugs_code_review,  "#1C5C1C"),
]

cols = st.columns(len(kpis))
for col, (label, value, color) in zip(cols, kpis):
    col.markdown(kpi_colored(label, value, color), unsafe_allow_html=True)

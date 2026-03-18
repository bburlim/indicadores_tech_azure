"""Métricas de Qualidade: Retrabalho, Saúde Backlog, SLA, Defeitos."""
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def _compute_touch_time(time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula touch_time_q por item a partir das colunas de status reais.
    Usa classify_states para identificar estados ativos automaticamente.
    Retorna colunas ["item_id", "touch_time_q"] para evitar conflito com
    a coluna touch_time já existente nos itens enriquecidos.
    """
    if time_by_status_df.empty:
        return pd.DataFrame(columns=["item_id", "touch_time_q"])

    from data.processor import classify_states
    status_cols = [c for c in time_by_status_df.columns if c != "item_id"]
    active_states, _ = classify_states(status_cols)

    tbs = time_by_status_df.copy()
    if active_states:
        tbs["touch_time_q"] = tbs[[c for c in active_states if c in tbs.columns]].sum(axis=1)
    else:
        tbs["touch_time_q"] = 0.0
    return tbs[["item_id", "touch_time_q"]]


# ─── Taxa de Retrabalho ───────────────────────────────────────────────────────

def rework_rate_by_month(df: pd.DataFrame, time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """
    Taxa de retrabalho = Touch Time Defeitos / (Touch Time Defeitos + Touch Time Histórias)
    Por mês de entrega.
    """
    if df.empty:
        return pd.DataFrame()

    delivered = df[df["closed_date"].notna()].copy()
    delivered["month"] = delivered["closed_date"].dt.to_period("M")

    tbs_touch = _compute_touch_time(time_by_status_df)
    if not tbs_touch.empty:
        merged = delivered.merge(tbs_touch, left_on="id", right_on="item_id", how="left")
        merged["touch_time_q"] = merged["touch_time_q"].fillna(0)
    else:
        merged = delivered.copy()
        merged["touch_time_q"] = merged.get("cycle_time", pd.Series(0, index=merged.index)).fillna(0)

    rows = []
    for month, group in merged.groupby("month"):
        bugs = group[group["item_type_general"] == "Defeito"]["touch_time_q"].sum()
        histories = group[group["item_type_general"] == "História"]["touch_time_q"].sum()
        total = bugs + histories
        rate = round(bugs / total * 100, 1) if total > 0 else 0.0
        rows.append({"month": month.to_timestamp(), "rework_rate": rate})

    return pd.DataFrame(rows)


def rework_rate_by_team_month(df: pd.DataFrame, time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """Taxa de retrabalho por equipe e mês."""
    if df.empty:
        return pd.DataFrame()

    delivered = df[df["closed_date"].notna()].copy()
    delivered["month"] = delivered["closed_date"].dt.to_period("M")

    tbs_touch = _compute_touch_time(time_by_status_df)
    if not tbs_touch.empty:
        merged = delivered.merge(tbs_touch, left_on="id", right_on="item_id", how="left")
        merged["touch_time_q"] = merged["touch_time_q"].fillna(0)
    else:
        merged = delivered.copy()
        merged["touch_time_q"] = merged.get("cycle_time", pd.Series(0, index=merged.index)).fillna(0)

    rows = []
    for (team, month), group in merged.groupby(["team", "month"]):
        bugs = group[group["item_type_general"] == "Defeito"]["touch_time_q"].sum()
        histories = group[group["item_type_general"] == "História"]["touch_time_q"].sum()
        total = bugs + histories
        rate = round(bugs / total * 100, 1) if total > 0 else 0.0
        rows.append({"team": team, "month": month.to_timestamp(), "rework_rate": rate})

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    pivot = result.pivot(index="team", columns="month", values="rework_rate").fillna(0)
    pivot.columns = [c.strftime("%b") for c in pivot.columns]
    return pivot.reset_index().rename(columns={"team": "Equipe"})


def rework_trend_weekly(df: pd.DataFrame, time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """Tendência semanal da taxa de retrabalho."""
    if df.empty:
        return pd.DataFrame()

    delivered = df[df["closed_date"].notna()].copy()

    tbs_touch = _compute_touch_time(time_by_status_df)
    if not tbs_touch.empty:
        merged = delivered.merge(tbs_touch, left_on="id", right_on="item_id", how="left")
        merged["touch_time_q"] = merged["touch_time_q"].fillna(0)
    else:
        merged = delivered.copy()
        merged["touch_time_q"] = merged.get("cycle_time", pd.Series(0, index=merged.index)).fillna(0)

    merged["week_ordinal"] = merged["closed_date"].apply(
        lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if not pd.isna(x) else None
    )

    rows = []
    for week, group in merged.groupby("week_ordinal"):
        bugs = group[group["item_type_general"] == "Defeito"]["touch_time_q"].sum()
        histories = group[group["item_type_general"] == "História"]["touch_time_q"].sum()
        total = bugs + histories
        rate = round(bugs / total * 100, 1) if total > 0 else 0.0
        rows.append({"week_ordinal": week, "rework_rate": rate})

    return pd.DataFrame(rows)


# ─── Saúde Backlog ────────────────────────────────────────────────────────────

def backlog_health_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Saúde Backlog = % de Histórias no backlog total.
    Para itens em aberto, agrupados por mês de criação.
    """
    rows = []
    months = sorted(df["created_date"].dt.to_period("M").unique())

    for month in months:
        # Backlog até o fim do mês = criados até o mês e não entregues ainda
        month_end_ts = month.to_timestamp("M")
        created_until = df[df["created_date"].dt.to_period("M") <= month]
        backlog = created_until[
            created_until["closed_date"].isna()
            | (created_until["closed_date"].dt.to_period("M") > month)
        ]
        total = len(backlog)
        if total == 0:
            continue
        histories = len(backlog[backlog["item_type_general"] == "História"])
        health = round(histories / total * 100)
        rows.append({"month": month.to_timestamp(), "backlog_health": health})

    return pd.DataFrame(rows)


# ─── SLA ─────────────────────────────────────────────────────────────────────

def sla_bugs_by_month(df: pd.DataFrame, sla_days: int = 15) -> pd.DataFrame:
    """
    SLA: defeitos entregues dentro do prazo (cycle_time <= sla_days).
    Por mês de entrega.
    """
    delivered_bugs = df[
        (df["closed_date"].notna()) & (df["item_type_general"] == "Defeito")
    ].copy()

    if delivered_bugs.empty:
        return pd.DataFrame()

    delivered_bugs["month"] = delivered_bugs["closed_date"].dt.to_period("M")
    delivered_bugs["within_sla"] = delivered_bugs["cycle_time"] <= sla_days

    result = delivered_bugs.groupby("month").agg(
        total=("id", "count"),
        within_sla=("within_sla", "sum"),
    ).reset_index()
    result["sla_pct"] = (result["within_sla"] / result["total"] * 100).round(1)
    result["not_sla_pct"] = (100 - result["sla_pct"]).round(1)
    result["month"] = result["month"].dt.to_timestamp()
    return result


# ─── Defeitos por Origem ─────────────────────────────────────────────────────

def defects_by_origin_month(df: pd.DataFrame) -> pd.DataFrame:
    """Backlog de defeitos por origem (tags: Cliente / Interno)."""
    bugs = df[df["item_type_general"] == "Defeito"].copy()
    if bugs.empty:
        return pd.DataFrame()

    def _get_origin(tags: str) -> str:
        if not tags:
            return "Interno"
        tags_lower = str(tags).lower()
        if "cliente" in tags_lower or "client" in tags_lower:
            return "Cliente"
        return "Interno"

    bugs["origin"] = bugs["tags"].apply(_get_origin)
    bugs["month"] = bugs["created_date"].dt.to_period("M")

    # Backlog acumulado por mês
    months = sorted(bugs["month"].unique())
    rows = []
    for month in months:
        bugs_until = bugs[bugs["month"] <= month]
        delivered_until = bugs_until[
            bugs_until["closed_date"].notna()
            & (bugs_until["closed_date"].dt.to_period("M") <= month)
        ]
        backlog = bugs_until[~bugs_until["id"].isin(delivered_until["id"])]

        for origin in ["Cliente", "Interno"]:
            rows.append({
                "month": month.to_timestamp(),
                "origin": origin,
                "count": len(backlog[backlog["origin"] == origin]),
            })

    return pd.DataFrame(rows)


def defects_delivered_by_origin_month(df: pd.DataFrame) -> pd.DataFrame:
    """Defeitos entregues por origem e mês."""
    bugs = df[(df["item_type_general"] == "Defeito") & (df["closed_date"].notna())].copy()
    if bugs.empty:
        return pd.DataFrame()

    def _get_origin(tags):
        if not tags:
            return "Interno"
        return "Cliente" if "cliente" in str(tags).lower() else "Interno"

    bugs["origin"] = bugs["tags"].apply(_get_origin)
    bugs["month"] = bugs["closed_date"].dt.to_period("M")

    result = (
        bugs.groupby(["month", "origin"]).size().reset_index(name="count")
    )
    result["month"] = result["month"].dt.to_timestamp()
    return result


def defects_opened_by_origin_month(df: pd.DataFrame) -> pd.DataFrame:
    """Entrada de defeitos (abertos) por origem e mês."""
    bugs = df[df["item_type_general"] == "Defeito"].copy()
    if bugs.empty:
        return pd.DataFrame()

    def _get_origin(tags):
        if not tags:
            return "Interno"
        return "Cliente" if "cliente" in str(tags).lower() else "Interno"

    bugs["origin"] = bugs["tags"].apply(_get_origin)
    bugs["month"] = bugs["created_date"].dt.to_period("M")

    result = bugs.groupby(["month", "origin"]).size().reset_index(name="count")
    result["month"] = result["month"].dt.to_timestamp()
    return result

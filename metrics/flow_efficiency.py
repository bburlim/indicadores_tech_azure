"""Métricas de Eficiência de Fluxo."""
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def flow_efficiency_per_item(items_df: pd.DataFrame, time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula eficiência de fluxo por item:
    touch_time / (touch_time + wait_time) * 100
    """
    if time_by_status_df.empty:
        return items_df.copy()

    tbs = time_by_status_df.copy()

    touch_cols = [c for c in config.ACTIVE_STATUSES if c in tbs.columns]
    wait_cols = [c for c in config.WAIT_STATUSES if c in tbs.columns]

    tbs["touch_time"] = tbs[touch_cols].sum(axis=1)
    tbs["wait_time"] = tbs[wait_cols].sum(axis=1)
    tbs["total_time"] = tbs["touch_time"] + tbs["wait_time"]
    tbs["flow_efficiency"] = np.where(
        tbs["total_time"] > 0,
        tbs["touch_time"] / tbs["total_time"] * 100,
        0,
    )

    merged = items_df.merge(tbs[["item_id", "touch_time", "wait_time", "total_time", "flow_efficiency"]], left_on="id", right_on="item_id", how="left")
    return merged


def flow_efficiency_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Eficiência de fluxo média por mês de entrega."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty or "flow_efficiency" not in delivered.columns:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = delivered.groupby("month")["flow_efficiency"].mean().reset_index()
    result["month"] = result["month"].dt.to_timestamp()
    result["flow_efficiency"] = result["flow_efficiency"].round(1)
    return result


def flow_efficiency_by_team_month(df: pd.DataFrame) -> pd.DataFrame:
    """Eficiência de fluxo por equipe e mês."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty or "flow_efficiency" not in delivered.columns:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = delivered.groupby(["team", "month"])["flow_efficiency"].mean().reset_index()
    result["month"] = result["month"].dt.to_timestamp()
    result["flow_efficiency"] = result["flow_efficiency"].round(1)

    pivot = result.pivot(index="team", columns="month", values="flow_efficiency").fillna("")
    pivot.columns = [c.strftime("%b") for c in pivot.columns]
    return pivot.reset_index().rename(columns={"team": "Equipe"})


def flow_efficiency_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Tendência semanal da eficiência de fluxo."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty or "flow_efficiency" not in delivered.columns:
        return pd.DataFrame()

    delivered["week_ordinal"] = delivered["closed_date"].apply(
        lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if not pd.isna(x) else None
    )
    return delivered[["week_ordinal", "flow_efficiency"]].dropna()


def time_in_status_totals(time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """Total de horas por status (geral)."""
    if time_by_status_df.empty:
        return pd.DataFrame()

    all_statuses = config.ACTIVE_STATUSES + config.WAIT_STATUSES
    cols = [c for c in all_statuses if c in time_by_status_df.columns]
    totals = time_by_status_df[cols].sum().reset_index()
    totals.columns = ["status", "hours"]
    totals["hours"] = totals["hours"].round(0)
    return totals.sort_values("hours", ascending=False)


def time_in_status_by_month(items_df: pd.DataFrame, time_by_status_df: pd.DataFrame) -> pd.DataFrame:
    """Percentual de tempo em cada status por mês."""
    if time_by_status_df.empty or items_df.empty:
        return pd.DataFrame()

    # Junta para ter o mês de entrega
    merged = items_df[["id", "closed_date"]].merge(
        time_by_status_df, left_on="id", right_on="item_id", how="inner"
    )
    delivered = merged[merged["closed_date"].notna()].copy()
    delivered["month"] = delivered["closed_date"].dt.to_period("M")

    all_statuses = config.ACTIVE_STATUSES + config.WAIT_STATUSES
    cols = [c for c in all_statuses if c in delivered.columns]

    monthly = delivered.groupby("month")[cols].sum()
    row_totals = monthly.sum(axis=1)
    pct = monthly.div(row_totals, axis=0) * 100
    pct = pct.round(1)
    pct.index = pct.index.to_timestamp()
    return pct.reset_index().rename(columns={"index": "month"})

"""Métricas de Lead Time e Cycle Time."""
import pandas as pd
import numpy as np


def percentile_85(series: pd.Series) -> float:
    vals = series.dropna()
    if vals.empty:
        return 0.0
    return round(np.percentile(vals, 85), 1)


def lct_p85_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Lead Time e Cycle Time P85 por mês de entrega."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = delivered.groupby("month").agg(
        lead_time_p85=("lead_time", percentile_85),
        cycle_time_p85=("cycle_time", percentile_85),
    ).reset_index()
    result["month"] = result["month"].dt.to_timestamp()
    return result


def lct_p85_by_type_month(df: pd.DataFrame) -> pd.DataFrame:
    """Lead Time e Cycle Time P85 por tipo de item e mês."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = delivered.groupby(["month", "item_type_general"]).agg(
        lead_time_p85=("lead_time", percentile_85),
        cycle_time_p85=("cycle_time", percentile_85),
    ).reset_index()
    result["month"] = result["month"].dt.to_timestamp()
    return result


def lct_by_team_month(df: pd.DataFrame) -> pd.DataFrame:
    """Lead Time e Cycle Time P85 por equipe e mês."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = delivered.groupby(["team", "month"]).agg(
        lead_time_p85=("lead_time", percentile_85),
        cycle_time_p85=("cycle_time", percentile_85),
    ).reset_index()
    result["month_str"] = result["month"].dt.to_timestamp().dt.strftime("%b")
    return result


def lct_std_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Desvio padrão de Lead Time e Cycle Time por mês e tipo."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")

    # Geral
    geral = delivered.groupby("month").agg(
        lead_time_std=("lead_time", "std"),
        cycle_time_std=("cycle_time", "std"),
    ).fillna(0).reset_index()
    geral["month"] = geral["month"].dt.to_timestamp()

    # Por tipo
    por_tipo = delivered.groupby(["month", "item_type_general"]).agg(
        lead_time_std=("lead_time", "std"),
        cycle_time_std=("cycle_time", "std"),
    ).fillna(0).reset_index()
    por_tipo["month"] = por_tipo["month"].dt.to_timestamp()

    return geral, por_tipo


def lct_trend_by_item(df: pd.DataFrame) -> pd.DataFrame:
    """Dados de tendência por item (scatter por semana ordinal)."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["week_ordinal"] = delivered["closed_date"].apply(
        lambda x: (x.year - 2020) * 52 + x.isocalendar()[1] if not pd.isna(x) else None
    )
    return delivered[["id", "week_ordinal", "lead_time", "cycle_time", "item_type_general"]].dropna()


def pivot_team_month(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Pivota métrica por equipe e mês."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    agg = delivered.groupby(["team", "month"])[metric].apply(percentile_85).reset_index()
    agg.columns = ["Equipe", "month", metric]
    pivot = agg.pivot(index="Equipe", columns="month", values=metric).fillna("")
    pivot.columns = [str(c) for c in pivot.columns]
    return pivot.reset_index()

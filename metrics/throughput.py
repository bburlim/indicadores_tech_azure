"""Métricas de Throughput (Vazão) e Backlog."""
import pandas as pd
import numpy as np


def throughput_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Contagem de itens entregues por mês, separado por tipo."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = (
        delivered.groupby(["month", "item_type_general"])
        .size()
        .reset_index(name="count")
        .pivot(index="month", columns="item_type_general", values="count")
        .fillna(0)
    )
    result.index = result.index.to_timestamp()
    result["total"] = result.sum(axis=1)
    return result.reset_index()


def backlog_snapshot_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Backlog acumulado por mês (itens ainda não entregues até o fim do mês)."""
    if df.empty:
        return pd.DataFrame()

    months = pd.period_range(df["created_date"].min().to_period("M"), df["closed_date"].max().to_period("M") if df["closed_date"].notna().any() else pd.Period.now("M"), freq="M")

    rows = []
    for month in months:
        month_end = month.to_timestamp("M")
        # Criados até o fim do mês
        created_until = df[df["created_date"].dt.to_period("M") <= month]
        # Entregues até o fim do mês
        delivered_until = created_until[
            created_until["closed_date"].notna()
            & (created_until["closed_date"].dt.to_period("M") <= month)
        ]
        backlog = created_until[~created_until["id"].isin(delivered_until["id"])]

        row = {"month": month.to_timestamp(), "backlog_total": len(backlog)}
        for tipo in backlog["item_type_general"].unique():
            row[tipo] = len(backlog[backlog["item_type_general"] == tipo])
        rows.append(row)

    return pd.DataFrame(rows).fillna(0)


def burn_down_time(df: pd.DataFrame) -> float:
    """Burn-down time em meses: backlog_atual / media_mensal_entregas."""
    backlog = df[df["closed_date"].isna()].shape[0]
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return 0.0

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    avg_monthly = delivered.groupby("month").size().mean()
    if avg_monthly == 0:
        return 0.0
    return round(backlog / avg_monthly, 1)


def vazao_qualificada_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Vazão qualificada por mês e tipo."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = (
        delivered.groupby(["month", "item_type_general"])["vazao_qualificada"]
        .sum()
        .reset_index()
        .pivot(index="month", columns="item_type_general", values="vazao_qualificada")
        .fillna(0)
    )
    result.index = result.index.to_timestamp()
    result["total"] = result.sum(axis=1)
    return result.reset_index()


def vazao_qualificada_by_team_month(df: pd.DataFrame) -> pd.DataFrame:
    """Vazão qualificada por equipe e mês."""
    delivered = df[df["closed_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame()

    delivered["month"] = delivered["closed_date"].dt.to_period("M")
    result = (
        delivered.groupby(["team", "month"])["vazao_qualificada"]
        .sum()
        .reset_index()
        .pivot(index="team", columns="month", values="vazao_qualificada")
        .fillna(0)
    )
    result.columns = [str(c) for c in result.columns]
    return result.reset_index()


def vazao_por_hc(df: pd.DataFrame, hc_df: pd.DataFrame, mode: str = "contabil") -> pd.DataFrame:
    """Vazão qualificada por headcount por mês."""
    vazao = vazao_qualificada_by_month(df)
    if vazao.empty or hc_df is None or hc_df.empty:
        return vazao

    col = f"hc_{mode}"
    if col not in hc_df.columns:
        return vazao

    merged = vazao.merge(hc_df[["month", col]], on="month", how="left")
    merged[f"vazao_hc_{mode}"] = merged["total"] / merged[col].replace(0, np.nan)
    return merged

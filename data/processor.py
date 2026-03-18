"""Processamento e enriquecimento dos dados dos work items."""
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import holidays
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

BR_HOLIDAYS = holidays.Brazil()


def is_business_day(dt: datetime) -> bool:
    d = dt.date() if hasattr(dt, "date") else dt
    return d.weekday() < 5 and d not in BR_HOLIDAYS


def business_hours_between(start: datetime, end: datetime) -> float:
    """Calcula horas úteis entre dois datetimes (8h-18h, excluindo fds e feriados)."""
    if pd.isna(start) or pd.isna(end):
        return 0.0
    if start.tzinfo is not None:
        start = start.tz_localize(None) if start.tzinfo else start
        start = start.replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.replace(tzinfo=None)

    if end <= start:
        return 0.0

    total_hours = 0.0
    current = start

    while current.date() <= end.date():
        if is_business_day(current):
            day_start = datetime.combine(current.date(), time(config.WORK_START_HOUR, 0))
            day_end = datetime.combine(current.date(), time(config.WORK_END_HOUR, 0))

            period_start = max(current, day_start)
            period_end = min(end, day_end)

            if period_end > period_start:
                total_hours += (period_end - period_start).total_seconds() / 3600

        current = datetime.combine(current.date() + timedelta(days=1), time(config.WORK_START_HOUR, 0))

    return min(total_hours, (end.date() - start.date()).days * config.MAX_HOURS_PER_DAY + config.MAX_HOURS_PER_DAY)


def classify_states(states) -> tuple:
    """
    Auto-classifica estados como ativos (touch time) ou espera (wait time)
    com base em palavras-chave, sem depender de nomes hardcoded.
    Retorna (active_states, wait_states).
    """
    active_kw = [
        "in progress", "progress", "em andamento", "desenvolvimento",
        "review", "revisão", "revisao", "qa", "quality", "teste", "testing",
        "releasing", "release", "infra", "dev adjust", "doing", "homolog",
    ]
    wait_kw = [
        "waiting", "wait", "aguardando", "selected", "queue", "fila",
        "blocked", "bloqueado", "pending", "pendente", "to do", "todo",
        "backlog", "new", "novo", "ready",
    ]
    terminal_kw = ["done", "closed", "resolved", "cancelled", "removed",
                   "concluído", "concluido", "cancelado"]

    active, wait = [], []
    for s in states:
        sl = s.lower()
        if any(k in sl for k in terminal_kw):
            continue
        if any(k in sl for k in active_kw):
            active.append(s)
        else:
            wait.append(s)
    return active, wait


def compute_time_in_status(history_df: pd.DataFrame, items_df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada item, calcula o tempo (horas úteis) em cada status.
    Usa todos os estados encontrados no histórico (não apenas os do config).
    Retorna DataFrame: item_id x status = horas
    """
    if history_df.empty:
        return pd.DataFrame()

    # Usa todos os estados reais do histórico
    all_states = [s for s in history_df["to_state"].dropna().unique() if s]
    results = []

    for item_id, group in history_df.groupby("item_id"):
        group = group.sort_values("changed_date").reset_index(drop=True)

        item_row = items_df[items_df["id"] == item_id]
        closed = item_row["closed_date"].iloc[0] if not item_row.empty else None

        status_hours = {s: 0.0 for s in all_states}

        transitions = [{"state": row["to_state"], "start": row["changed_date"]}
                       for _, row in group.iterrows()]

        for i, t in enumerate(transitions):
            next_start = transitions[i + 1]["start"] if i + 1 < len(transitions) else (closed or pd.Timestamp.now(tz="UTC"))
            if t["state"] in status_hours:
                h = business_hours_between(t["start"], next_start)
                status_hours[t["state"]] += h

        row_dict = {"item_id": item_id}
        row_dict.update(status_hours)
        results.append(row_dict)

    return pd.DataFrame(results)


def compute_cycle_and_lead_time(history_df: pd.DataFrame, items_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula Lead Time e Cycle Time em dias corridos para itens entregues.
    - Lead Time: created_date → closed_date
    - Cycle Time: primeira entrada em "In Progress - Tec" → closed_date
    """
    if history_df.empty or items_df.empty:
        return items_df.copy()

    # Detecta o estado de início do Cycle Time:
    # 1) Tenta match exato com CYCLE_TIME_START_STATUS
    # 2) Fallback: qualquer estado que contenha "in progress" (case-insensitive)
    all_states = history_df["to_state"].dropna().unique()
    exact = config.CYCLE_TIME_START_STATUS
    if exact in all_states:
        cycle_start_states = {exact}
    else:
        cycle_start_states = {s for s in all_states if "in progress" in s.lower() or "em andamento" in s.lower()}

    cycle_start_map = {}

    for item_id, group in history_df.groupby("item_id"):
        group = group.sort_values("changed_date")
        in_progress = group[group["to_state"].isin(cycle_start_states)]
        if not in_progress.empty:
            cycle_start_map[item_id] = in_progress.iloc[0]["changed_date"]

    df = items_df.copy()
    # map() retorna NaN (float) para IDs não encontrados — converte para NaT
    df["cycle_start"] = pd.to_datetime(df["id"].map(cycle_start_map), utc=True, errors="coerce")

    # Lead Time (dias corridos)
    lead_delta = df["closed_date"] - df["created_date"]
    df["lead_time"] = lead_delta.dt.total_seconds().div(86400).where(df["closed_date"].notna())

    # Cycle Time (dias corridos)
    cycle_delta = df["closed_date"] - df["cycle_start"]
    df["cycle_time"] = (
        cycle_delta.dt.total_seconds()
        .div(86400)
        .where(df["closed_date"].notna() & df["cycle_start"].notna())
        .clip(lower=0)
    )

    return df


def compute_vazao_qualificada(df: pd.DataFrame) -> pd.DataFrame:
    """Atribui peso de vazão qualificada baseado no tipo e cycle time."""

    def _weight(row):
        ct = row.get("cycle_time", 0) or 0
        tipo = row.get("item_type_general", "")
        if tipo == "Defeito":
            return 0.5
        # História
        if ct <= 1:
            return 0
        elif ct <= 3:
            return 0.5
        elif ct <= 10:
            return 1
        else:
            return 2

    df = df.copy()
    df["vazao_qualificada"] = df.apply(_weight, axis=1)
    return df


def add_delivery_period(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas de mês e semana de entrega."""
    df = df.copy()
    if "closed_date" in df.columns:
        df["delivery_month"] = df["closed_date"].dt.to_period("M")
        df["delivery_week"] = df["closed_date"].dt.isocalendar().week.astype("Int64")
        df["delivery_year"] = df["closed_date"].dt.year.astype("Int64")
        df["delivery_week_num"] = (
            df["closed_date"].dt.to_period("W").apply(lambda x: x.ordinal if not pd.isna(x) else None)
        )
    return df


def enrich_items(items_df: pd.DataFrame, history_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pipeline completo de enriquecimento dos dados."""
    if items_df.empty:
        return items_df, pd.DataFrame()

    # Calcula lead/cycle time
    items_enriched = compute_cycle_and_lead_time(history_df, items_df)

    # Vazão qualificada
    items_enriched = compute_vazao_qualificada(items_enriched)

    # Período de entrega
    items_enriched = add_delivery_period(items_enriched)

    # Tempo por status
    time_by_status = compute_time_in_status(history_df, items_df)

    return items_enriched, time_by_status


def filter_items(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
    teams=None,
    segment=None,
    product=None,
    functional_team=None,
    journey=None,
    project=None,
    feature=None,
    platform=None,
    book_team=None,
    delivered_only: bool = False,
) -> pd.DataFrame:
    """Aplica filtros ao DataFrame de itens."""
    result = df.copy()

    if delivered_only:
        result = result[result["closed_date"].notna()]

    if start_date and "closed_date" in result.columns:
        # Itens sem closed_date (backlog aberto) sempre passam pelo filtro
        closed_naive = result["closed_date"].dt.tz_convert(None)
        result = result[result["closed_date"].isna() | (closed_naive >= pd.Timestamp(start_date))]
    if end_date and "closed_date" in result.columns:
        closed_naive = result["closed_date"].dt.tz_convert(None)
        result = result[result["closed_date"].isna() | (closed_naive <= pd.Timestamp(end_date) + pd.Timedelta(days=1))]

    if teams:
        result = result[result["team"].isin(teams)]
    if segment:
        result = result[result["segment"].isin(segment)]
    if product:
        result = result[result["product"].isin(product)]
    if functional_team:
        result = result[result["functional_team"].isin(functional_team)]
    if journey:
        result = result[result["journey"].isin(journey)]
    if project:
        result = result[result["project"].isin(project)]
    if feature:
        result = result[result["feature"].isin(feature)]
    if platform:
        result = result[result["platform"].isin(platform)]
    if book_team:
        result = result[result["book_team"].isin(book_team)]

    return result

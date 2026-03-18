"""Componentes de filtro da sidebar."""
import streamlit as st
import pandas as pd
from datetime import date


def render_global_filters(df: pd.DataFrame) -> dict:
    """Renderiza filtros globais na sidebar. Retorna dict com filtros selecionados."""
    st.sidebar.header("Filtros")

    # Data de entrega
    col1, col2 = st.sidebar.columns(2)
    min_date = date(2025, 1, 1)
    max_date = date.today()

    if "closed_date" in df.columns and df["closed_date"].notna().any():
        valid_dates = df["closed_date"].dropna()
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()

    with col1:
        start_date = st.date_input("Data início", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("Data fim", value=max_date, min_value=min_date, max_value=max_date)

    # Filtros de dimensão
    def multiselect_filter(label: str, column: str) -> list:
        options = sorted(df[column].dropna().unique().tolist()) if column in df.columns else []
        options = [o for o in options if o != ""]
        return st.sidebar.multiselect(label, options=options)

    filters = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "teams": multiselect_filter("Equipe", "team"),
        "segment": multiselect_filter("Segmento", "segment"),
        "product": multiselect_filter("Produto", "product"),
        "functional_team": multiselect_filter("Time Funcional", "functional_team"),
        "journey": multiselect_filter("Jornada", "journey"),
        "project": multiselect_filter("Projeto", "project"),
        "feature": multiselect_filter("Funcionalidade", "feature"),
        "platform": multiselect_filter("Plataforma", "platform"),
        "book_team": multiselect_filter("Equipe Book de Tech", "book_team"),
    }

    return filters


def render_flow_filters() -> dict:
    """Filtros específicos para visões de Eficiência de Fluxo e Tempo por Status."""
    with st.expander("Filtros Específicos - Eficiência de Fluxo e Tempo por Status"):
        col1, col2, col3 = st.columns(3)
        with col1:
            flow_type = st.selectbox("Tipo Fluxo", ["Downstream", "All"], key="flow_type")
        with col2:
            status_type = st.selectbox("Tipo Status", ["All", "Active", "Wait"], key="status_type")
        with col3:
            status = st.selectbox("Status", ["All"], key="flow_status")

    return {"flow_type": flow_type, "status_type": status_type, "status": status}

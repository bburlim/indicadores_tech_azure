"""Componentes de gráficos reutilizáveis."""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

MONTH_PT = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

LAYOUT_DEFAULTS = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Segoe UI, Arial", size=12),
    margin=dict(l=20, r=20, t=40, b=60),
    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
)


def month_label(ts) -> str:
    if pd.isna(ts):
        return ""
    return MONTH_PT.get(ts.month, str(ts.month))


def kpi_card(label: str, value: str, color: str = "#555555") -> str:
    """Retorna HTML de um KPI card."""
    return f"""
    <div style="background:#f0f0f0;border-radius:10px;padding:16px 20px;text-align:center;margin:4px;">
        <div style="font-size:28px;font-weight:bold;color:{color};">{value}</div>
        <div style="font-size:13px;color:#666;">{label}</div>
    </div>
    """


def bar_chart_monthly(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list,
    labels: dict,
    colors: list,
    title: str,
    stacked: bool = False,
    text_outside: bool = True,
) -> go.Figure:
    """Gráfico de barras mensal."""
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        if col not in df.columns:
            continue
        color = colors[i % len(colors)]
        fig.add_trace(
            go.Bar(
                x=[month_label(m) for m in df[x_col]],
                y=df[col],
                name=labels.get(col, col),
                marker_color=color,
                text=df[col].round(1),
                textposition="outside" if text_outside else "inside",
            )
        )

    barmode = "stack" if stacked else "group"
    fig.update_layout(
        title=title,
        barmode=barmode,
        **LAYOUT_DEFAULTS,
    )
    return fig


def stacked_bar_pct_monthly(
    df: pd.DataFrame,
    x_col: str,
    status_cols: list,
    title: str,
) -> go.Figure:
    """Gráfico de barras empilhadas com percentual por status."""
    import plotly.colors as pc
    palette = pc.qualitative.Plotly + pc.qualitative.D3 + pc.qualitative.Set3
    auto_color_idx = 0

    fig = go.Figure()
    for col in status_cols:
        if col not in df.columns:
            continue
        if col in config.STATUS_COLORS:
            color = config.STATUS_COLORS[col]
        else:
            color = palette[auto_color_idx % len(palette)]
            auto_color_idx += 1
        texts = [f"{v:.1f}%" if v >= 4 else "" for v in df[col]]
        fig.add_trace(
            go.Bar(
                x=[month_label(m) for m in df[x_col]],
                y=df[col],
                name=col,
                marker_color=color,
                text=texts,
                textposition="inside",
                insidetextanchor="middle",
            )
        )

    fig.update_layout(
        title=title,
        barmode="stack",
        **LAYOUT_DEFAULTS,
        yaxis=dict(tickformat=".0f", title="% do Tempo"),
    )
    return fig


def line_chart_monthly(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    bench_value: float = None,
    bench_label: str = None,
    color: str = "#7B7BC8",
    fill: bool = True,
) -> go.Figure:
    """Gráfico de linha com área preenchida, opcional benchmark."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=[month_label(m) for m in df[x_col]],
            y=df[y_col],
            mode="lines+markers+text",
            line=dict(color=color, width=2),
            fill="tozeroy" if fill else None,
            fillcolor=f"rgba(123,123,200,0.3)" if fill else None,
            text=[f"{v:.1f}%" for v in df[y_col]],
            textposition="top center",
            name=y_col,
        )
    )

    if bench_value is not None:
        fig.add_hline(
            y=bench_value,
            line_dash="dash",
            line_color="#00aa00",
            annotation_text=bench_label or f"Bench {bench_value}%",
            annotation_position="right",
        )

    fig.update_layout(title=title, **LAYOUT_DEFAULTS, showlegend=False)
    return fig


def scatter_trend(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    color: str = "#FFA500",
) -> go.Figure:
    """Scatter plot com linha de tendência (regressão linear)."""
    fig = go.Figure()

    vals = df[[x_col, y_col]].dropna()
    if vals.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=vals[x_col],
            y=vals[y_col],
            mode="markers",
            marker=dict(color=color, size=8),
            name="",
        )
    )

    # Linha de tendência
    x_arr = vals[x_col].values
    y_arr = vals[y_col].values
    z = np.polyfit(x_arr, y_arr, 1)
    p = np.poly1d(z)
    fig.add_trace(
        go.Scatter(
            x=x_arr,
            y=p(x_arr),
            mode="lines",
            line=dict(color=color, width=1, dash="dash"),
            name="Tendência",
        )
    )

    fig.update_layout(title=title, **LAYOUT_DEFAULTS, showlegend=False)
    return fig


def dual_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    col1: str,
    col2: str,
    label1: str,
    label2: str,
    color1: str,
    color2: str,
    title: str,
) -> go.Figure:
    """Gráfico de barras duplas lado a lado."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df[x_col], y=df[col1], name=label1, marker_color=color1,
                         text=df[col1].round(1), textposition="outside"))
    fig.add_trace(go.Bar(x=df[x_col], y=df[col2], name=label2, marker_color=color2,
                         text=df[col2].round(1), textposition="outside"))
    fig.update_layout(title=title, barmode="group", **LAYOUT_DEFAULTS)
    return fig


def horizontal_bar(
    df: pd.DataFrame,
    y_col: str,
    x_col: str,
    colors: list,
    title: str,
) -> go.Figure:
    """Gráfico de barras horizontal."""
    fig = go.Figure()
    for i, row in df.iterrows():
        color = config.STATUS_COLORS.get(row[y_col], colors[i % len(colors)])
        fig.add_trace(
            go.Bar(
                y=[row[y_col]],
                x=[row[x_col]],
                orientation="h",
                marker_color=color,
                text=[f"{row[x_col]:.1f}K" if row[x_col] >= 1000 else f"{row[x_col]:.0f}"],
                textposition="outside",
                showlegend=False,
            )
        )
    fig.update_layout(title=title, **LAYOUT_DEFAULTS, barmode="overlay")
    return fig


def dataframe_table(df: pd.DataFrame, title: str = None) -> None:
    """Renderiza DataFrame com estilo."""
    import streamlit as st
    if title:
        st.markdown(f"**{title}**")
    st.dataframe(df, use_container_width=True, hide_index=True)


def team_month_pivot_table(pivot_df: pd.DataFrame, title: str, format_pct: bool = False) -> None:
    """Renderiza tabela pivot de equipe x mês com estilo de cor."""
    import streamlit as st
    if pivot_df.empty:
        return
    if title:
        st.markdown(f"**{title}**")

    styled = pivot_df.style.format(
        {c: "{:.1f}%" if format_pct else "{:.1f}" for c in pivot_df.columns if c != "Equipe"},
        na_rep="--",
    ).set_table_styles([
        {"selector": "thead tr th", "props": [("background-color", "#4472C4"), ("color", "white"), ("font-weight", "bold")]},
        {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#DCE6F1")]},
    ])
    st.dataframe(styled, use_container_width=True, hide_index=True)

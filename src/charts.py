"""Plotly figures for the dashboard. Pure builders from backend outputs; no Streamlit imports, no new formulas.

Identity never relies on colour alone: local and LA peer use different marker shapes and are labelled in the
legend and hover text. Colours are slots 1–2 of the validated reference categorical palette.
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

LOCAL_COLOR = "#2a78d6"
PEER_COLOR = "#eb6834"
NEUTRAL_COLOR = "#8a8984"
FONT = dict(size=13)


def _layout(fig: go.Figure, title: str, *, height: int = 360) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0, xanchor="left", font=dict(size=15)), height=height,
                      margin=dict(l=8, r=8, t=48, b=8), font=FONT, hovermode="closest",
                      legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def price_histogram(bins: pd.DataFrame, median: float | None, title: str) -> go.Figure | None:
    """Equal-width bins from `pricing.histogram_bins` with a median marker. None when there are no prices."""
    if bins.empty:
        return None
    centers = (bins.left + bins.right) / 2
    widths = (bins.right - bins.left).where(lambda w: w > 0, other=max(1.0, abs(float(bins.left.iloc[0])) * 0.02))
    fig = go.Figure(go.Bar(
        x=centers, y=bins["count"], width=widths * 0.96, marker=dict(color=LOCAL_COLOR, cornerradius=4),
        customdata=bins[["left", "right"]].to_numpy(), name="Local listings",
        hovertemplate="$%{customdata[0]:,.2f} – $%{customdata[1]:,.2f}<br>%{y} listings<extra></extra>"))
    if median is not None and not math.isnan(median):
        fig.add_vline(x=median, line=dict(color=NEUTRAL_COLOR, width=2, dash="dash"),
                      annotation=dict(text=f"Median ${median:,.2f}", yanchor="top", font=FONT))
    fig.update_xaxes(title_text="Advertised nightly price (USD)", tickprefix="$", separatethousands=True)
    fig.update_yaxes(title_text="Listings")
    fig.update_layout(bargap=0, showlegend=False)
    return _layout(fig, title)


def comparison_prices(row: dict, labels: tuple[str, str], suffixes: tuple[str, str]) -> go.Figure:
    """Local median with P25–P75 range and the inclusive LA peer median for both snapshots."""
    fig = go.Figure()
    for who, prefix, color, symbol in (("Local (selected neighbourhood)", "", LOCAL_COLOR, "circle"),
                                       ("LA peer (all neighbourhoods, incl. selected)", "peer_", PEER_COLOR,
                                        "diamond")):
        x, y, lo, hi = [], [], [], []
        for label, suffix in zip(labels, suffixes):
            median = row.get(f"{prefix}median_price_usd_{suffix}")
            if median is None or pd.isna(median):
                continue
            x.append(label)
            y.append(median)
            lo.append(median - row[f"{prefix}p25_price_usd_{suffix}"])
            hi.append(row[f"{prefix}p75_price_usd_{suffix}"] - median)
        fig.add_trace(go.Scatter(
            x=x, y=y, name=who, mode="markers", marker=dict(color=color, size=12, symbol=symbol,
                                                           line=dict(width=2, color="white")),
            error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, color=color, thickness=2, width=8),
            hovertemplate=f"{who}<br>%{{x}} median $%{{y:,.2f}}<extra></extra>"))
    fig.update_yaxes(title_text="Advertised price (USD)", tickprefix="$",
                     separatethousands=True, rangemode="tozero")
    fig.update_xaxes(categoryorder="array", categoryarray=list(labels))
    fig.update_layout(scattermode="group", scattergap=0.6)
    return _layout(fig, "Median price (whiskers = P25–P75)", height=400)


def comparison_premiums(row: dict, labels: tuple[str, str], suffixes: tuple[str, str]) -> go.Figure:
    """Premium vs inclusive LA peer per snapshot. Unavailable premiums are labelled, never drawn as zero."""
    x, y, text = [], [], []
    for label, suffix in zip(labels, suffixes):
        value = row.get(f"premium_pct_{suffix}")
        x.append(label)
        if value is None or pd.isna(value):
            y.append(None)
            text.append("Unavailable")
        else:
            y.append(value)
            text.append(f"{value:+.1f}%")
    fig = go.Figure(go.Bar(x=x, y=y, text=text, textposition="outside", cliponaxis=False,
                           marker=dict(color=LOCAL_COLOR, cornerradius=4), width=0.45,
                           hovertemplate="%{x}: %{text}<extra></extra>"))
    for label, value in zip(x, y):
        if value is None:
            fig.add_annotation(x=label, y=0, text="Unavailable", showarrow=False, yshift=14, font=FONT)
    fig.add_hline(y=0, line=dict(color=NEUTRAL_COLOR, width=1))
    fig.update_yaxes(title_text="Premium vs LA peer median (%)", ticksuffix="%")
    fig.update_xaxes(categoryorder="array", categoryarray=list(labels))
    return _layout(fig, "Premium vs inclusive LA peer")

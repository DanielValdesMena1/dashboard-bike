from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.processing.metrics import format_number

from src.visualization.theme import (
    BLUE_RAMP, GRID, METRIC_COLORS, ACCENT, TEXT_MUTED, TEXT_PRIMARY, base_layout,
)

# (columna, título, unidad, suavizado en segundos)
PERFORMANCE_PANELS = [
    ("altitude_m", "Altitud", "m", 0),
    ("speed_kmh", "Velocidad (media 30 s)", "km/h", 30),
    ("power_w", "Potencia (media 30 s)", "W", 30),
    ("heart_rate", "Frecuencia cardíaca", "bpm", 0),
    ("cadence", "Cadencia (media 30 s)", "rpm", 30),
]


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def performance_chart(df: pd.DataFrame) -> go.Figure | None:
    """Small multiples: una métrica por panel, eje X compartido (distancia).
    Evita el gráfico de doble eje mostrando cada escala por separado."""
    panels = [p for p in PERFORMANCE_PANELS if p[0] in df.columns and df[p[0]].notna().any()]
    if not panels or "distance_km" not in df.columns:
        return None

    fig = make_subplots(
        rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.05,
        subplot_titles=[f"{title} · {unit}" for _, title, unit, _ in panels],
    )
    x = df["distance_km"]
    for row, (col, title, unit, smooth) in enumerate(panels, start=1):
        y = df[col].rolling(smooth, min_periods=1).mean() if smooth else df[col]
        color = METRIC_COLORS[col]
        fig.add_trace(
            go.Scatter(
                x=x, y=y, mode="lines", name=title,
                line=dict(color=color, width=1.6),
                fill="tozeroy" if col == "altitude_m" else None,
                fillcolor=_rgba(color, 0.18),
                hovertemplate=f"%{{y:.0f}} {unit}<extra>{title}</extra>",
            ),
            row=row, col=1,
        )
        if col == "altitude_m":
            low, high = df[col].min(), df[col].max()
            pad = (high - low) * 0.1
            fig.update_yaxes(range=[low - pad, high + pad], row=row, col=1)

    fig.update_layout(**base_layout(height=170 * len(panels) + 60, hovermode="x unified"))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, showspikes=True, spikecolor=TEXT_MUTED,
                     spikethickness=1, spikedash="dot", spikemode="across")
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    fig.update_xaxes(title_text="Distancia (km)", row=len(panels), col=1)
    fig.update_annotations(font=dict(size=13, color=TEXT_PRIMARY), x=0, xanchor="left")
    return fig


def zones_chart(zones: pd.DataFrame, ramp: list[str], unit: str) -> go.Figure:
    """Barras horizontales del % de tiempo por zona (Z1 arriba)."""
    colors = ramp[: len(zones)]
    ranges = [
        f"{d:.0f}–{h:.0f} {unit}" if pd.notna(h) else f"> {d:.0f} {unit}"
        for d, h in zip(zones["desde"], zones["hasta"])
    ]
    minutes = zones["segundos"] / 60
    fig = go.Figure(go.Bar(
        x=zones["pct"], y=zones["zona"], orientation="h",
        marker=dict(color=colors, line=dict(width=0), cornerradius=4),
        text=[f"{p:.0f}%" for p in zones["pct"]], textposition="outside",
        textfont=dict(color=TEXT_PRIMARY),
        customdata=list(zip(ranges, minutes)),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{customdata[1]:.0f} min · %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(**base_layout(
        height=60 + 44 * len(zones), bargap=0.25,
        xaxis=dict(visible=False, range=[0, zones["pct"].max() * 1.18 + 1]),
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=10, b=10),
    ))
    return fig


def power_curve_chart(curve: pd.DataFrame, ftp_w: float | None = None) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=curve["duration_s"], y=curve["power_w"], mode="lines+markers",
        line=dict(color=ACCENT, width=2.5, shape="spline"),
        marker=dict(size=9, color=ACCENT, line=dict(color="#14161a", width=2)),
        fill="tozeroy", fillcolor=_rgba(ACCENT, 0.12),
        customdata=curve["duracion"],
        hovertemplate="Mejor %{customdata}: <b>%{y:.0f} W</b><extra></extra>",
    ))
    if ftp_w:
        fig.add_hline(y=ftp_w, line=dict(color=TEXT_MUTED, width=1, dash="dash"),
                      annotation_text=f"FTP {ftp_w:.0f} W", annotation_position="top right",
                      annotation_font_color=TEXT_MUTED)
    fig.update_layout(**base_layout(
        height=400,
        xaxis=dict(type="log", tickvals=curve["duration_s"], ticktext=curve["duracion"],
                   gridcolor=GRID, title="Duración del esfuerzo"),
        yaxis=dict(gridcolor=GRID, title="Potencia media (W)", rangemode="tozero"),
    ))
    return fig


def splits_chart(splits: pd.DataFrame) -> go.Figure:
    """Velocidad media por tramo; el color de la barra indica el desnivel del tramo."""
    gain = splits.get("desnivel_m", pd.Series(0, index=splits.index))
    fig = go.Figure(go.Bar(
        x=splits["tramo"], y=splits["vel_kmh"],
        marker=dict(
            color=gain, colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
            cornerradius=4, line=dict(width=0),
            colorbar=dict(title=dict(text="Desnivel +<br>(m)", font=dict(size=12)), thickness=10, outlinewidth=0),
        ),
        customdata=gain,
        hovertemplate="<b>%{x}</b><br>%{y:.1f} km/h<br>Desnivel +: %{customdata:.0f} m<extra></extra>",
    ))
    fig.update_layout(**base_layout(
        height=360, bargap=0.2,
        yaxis=dict(gridcolor=GRID, title="Velocidad media (km/h)"),
        xaxis=dict(tickangle=-40),
    ))
    return fig


def history_bar(history: pd.DataFrame, column: str, title: str, unit: str, color: str) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=history["etiqueta"], y=history[column],
        marker=dict(color=color, cornerradius=4, line=dict(width=0)),
        text=[format_number(v) for v in history[column]], textposition="outside",
        textfont=dict(color=TEXT_PRIMARY),
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:.1f}} {unit}<extra></extra>",
    ))
    fig.update_layout(**base_layout(
        height=320, title=dict(text=title, font=dict(color=TEXT_PRIMARY, size=15)),
        bargap=0.35, yaxis=dict(gridcolor=GRID, range=[0, history[column].max() * 1.18]),
        xaxis=dict(type="category"),
    ))
    return fig


def history_trend(history: pd.DataFrame, column: str, title: str, decimals: int, color: str) -> go.Figure:
    values = history[column]
    pad = max((values.max() - values.min()) * 0.25, abs(values.max()) * 0.02)
    fig = go.Figure(go.Scatter(
        x=history["etiqueta"], y=values, mode="lines+markers+text",
        line=dict(color=color, width=2),
        marker=dict(size=10, color=color, line=dict(color="#14161a", width=2)),
        text=[format_number(v, decimals) for v in values], textposition="top center",
        textfont=dict(color=TEXT_PRIMARY),
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:.{decimals}f}}<extra></extra>",
    ))
    fig.update_layout(**base_layout(
        height=320, title=dict(text=title, font=dict(color=TEXT_PRIMARY, size=15)),
        yaxis=dict(gridcolor=GRID, range=[values.min() - pad, values.max() + pad]),
        xaxis=dict(gridcolor=GRID, type="category"),
    ))
    return fig

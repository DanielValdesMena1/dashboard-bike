"""Paleta y estilo compartido por todos los gráficos (tema oscuro)."""

SURFACE = "#14161a"
CARD = "#1c1f24"
BORDER = "#2a2e35"
TEXT_PRIMARY = "#f0efec"
TEXT_SECONDARY = "#c3c2b7"
TEXT_MUTED = "#8b8a83"
GRID = "rgba(255, 255, 255, 0.07)"

ACCENT = "#d95926"  # naranja, color de marca del dashboard

# Un color fijo por métrica (la identidad nunca cambia entre gráficos)
METRIC_COLORS = {
    "altitude_m": "#8b8a83",
    "speed_kmh": "#3987e5",
    "power_w": "#d95926",
    "heart_rate": "#e66767",
    "cadence": "#199e70",
}

# Rampa secuencial azul (oscuro -> claro = poca -> mucha intensidad en fondo oscuro)
BLUE_RAMP = ["#184f95", "#1c5cab", "#256abf", "#3987e5", "#5598e7", "#86b6ef", "#b7d3f6"]
# Rampa secuencial naranja para las zonas de potencia
ORANGE_RAMP = ["#6e2a10", "#8f3815", "#b0461b", "#d95926", "#e57a4f", "#ee9d7b", "#f6c3ab"]
# Rampa roja para las zonas de frecuencia cardíaca
RED_RAMP = ["#7a2524", "#a13534", "#c94a49", "#e66767", "#f0a3a2"]

FONT = "Inter, 'Segoe UI', system-ui, sans-serif"


def base_layout(**overrides) -> dict:
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=TEXT_SECONDARY, size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font=dict(color=TEXT_PRIMARY, family=FONT)),
        xaxis=dict(gridcolor=GRID, zeroline=False, linecolor=BORDER),
        yaxis=dict(gridcolor=GRID, zeroline=False, linecolor=BORDER),
        showlegend=False,
        separators=",.",  # decimales con coma, miles con punto
    )
    layout.update(overrides)
    return layout

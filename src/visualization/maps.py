from __future__ import annotations

import branca.colormap as cm
import folium
import pandas as pd

from src.visualization.theme import BLUE_RAMP, ORANGE_RAMP, RED_RAMP

MAX_POINTS = 4000  # Reduce puntos para que el mapa cargue rápido

# Mapas base de Esri (no requieren API key); el primero es el que se muestra por defecto
BASEMAPS = [
    ("Satélite", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
     "Tiles &copy; Esri"),
    ("Oscuro", "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
     "Tiles &copy; Esri"),
    ("Calles", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
     "Tiles &copy; Esri"),
]

COLOR_OPTIONS = {
    "speed_kmh": ("Velocidad (km/h)", BLUE_RAMP),
    "power_w": ("Potencia (W, media 30 s)", ORANGE_RAMP),
    "heart_rate": ("Frecuencia cardíaca (bpm)", RED_RAMP),
    "altitude_m": ("Altitud (m)", BLUE_RAMP),
}


def build_route_map(df: pd.DataFrame, color_by: str | None = None) -> folium.Map | None:
    """Mapa de la ruta. Si `color_by` es una columna, colorea el trazado según ese valor."""
    if "lat" not in df.columns or "lon" not in df.columns:
        return None

    gps = df.copy()
    if color_by == "power_w" and "power_w" in gps:
        gps["power_w"] = gps["power_w"].rolling(30, min_periods=1).mean()
    gps = gps.dropna(subset=["lat", "lon"])
    if gps.empty:
        return None

    if len(gps) > MAX_POINTS:
        step = len(gps) // MAX_POINTS + 1
        gps = gps.iloc[::step]

    route = list(zip(gps["lat"].tolist(), gps["lon"].tolist()))

    m = folium.Map(location=route[0], tiles=None, control_scale=True)
    for i, (name, url, attribution) in enumerate(BASEMAPS):
        folium.TileLayer(url, name=name, attr=attribution, max_zoom=18, show=i == 0).add_to(m)

    if color_by in COLOR_OPTIONS and color_by in gps.columns and gps[color_by].notna().any():
        caption, ramp = COLOR_OPTIONS[color_by]
        values = gps[color_by].ffill().bfill()
        low, high = values.quantile(0.05), values.quantile(0.95)
        # Solo los tonos claros de la rampa: los oscuros no se distinguen sobre el mapa base oscuro
        colormap = cm.LinearColormap(ramp[3:], vmin=low, vmax=high, caption=caption)
        folium.ColorLine(
            positions=route, colors=values.clip(low, high).tolist()[:-1],
            colormap=colormap, weight=5, opacity=0.95,
        ).add_to(m)
        colormap.add_to(m)
    else:
        folium.PolyLine(route, weight=5, color="#d95926", opacity=0.95).add_to(m)

    folium.Marker(route[0], tooltip="Inicio", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker(route[-1], tooltip="Fin", icon=folium.Icon(color="red", icon="flag")).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    m.fit_bounds(route, padding=(30, 30))

    return m

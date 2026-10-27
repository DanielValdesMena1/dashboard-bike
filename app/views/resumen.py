import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.processing.metrics import calculate_metrics, format_duration
from src.processing.performance import performance_summary
from src.ui.components import fmt, format_date, hero, kpi_cards, list_activities, load_from_path, section
from src.visualization.charts import history_bar, history_trend
from src.visualization.theme import METRIC_COLORS


activities = list_activities()
if not activities:
    hero("Historial", "Sin actividades", "Conecta Garmin Connect o coloca tus archivos .fit en data/raw/fit para ver el historial.")
    st.stop()

# Una fila por actividad con sus métricas principales
rows = []
for activity in activities:
    _, records, session = load_from_path(activity["path"])
    summary = activity["summary"]
    ftp = summary["device_ftp_w"] or 250
    perf = performance_summary(records, ftp, summary["duration_s"])
    rows.append({
        "fecha": summary["start_time"],
        "etiqueta": format_date(summary["start_time"]),
        "fuente": activity["source"],
        "distancia_km": summary["distance_km"],
        "duracion_s": summary["duration_s"],
        "vel_kmh": summary["avg_speed_kmh"],
        "desnivel_m": summary["elevation_gain_m"],
        "potencia_w": summary["avg_power_w"],
        "np_w": perf["np_w"],
        "fc_bpm": summary["avg_heart_rate"],
        "tss": perf["tss"],
        "ef": perf["efficiency_factor"],
        "calorias": summary["calories"],
    })

history = pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)
# Dos salidas el mismo día no deben fusionarse en el eje X
repeats = history.groupby("etiqueta").cumcount()
history.loc[repeats > 0, "etiqueta"] += " (" + (repeats[repeats > 0] + 1).astype(str) + ")"

# Volumen semanal (semanas de lunes a domingo)
weekly = (
    history.assign(semana=history["fecha"].dt.to_period("W-SUN").dt.start_time)
    .groupby("semana", as_index=False)
    .agg(distancia_km=("distancia_km", "sum"), tss=("tss", "sum"), salidas=("fecha", "count"))
)
weekly["etiqueta"] = "Sem. " + weekly["semana"].map(format_date)

first, last = history["fecha"].min(), history["fecha"].max()
hero("Historial", f"{len(history)} actividades analizadas", f"Del {format_date(first)} al {format_date(last)}")

kpi_cards([
    {"label": "Distancia total", "value": fmt(history["distancia_km"].sum(), 1), "unit": "km",
     "color": METRIC_COLORS["speed_kmh"]},
    {"label": "Tiempo total", "value": format_duration(history["duracion_s"].sum()), "color": METRIC_COLORS["speed_kmh"]},
    {"label": "Desnivel acumulado", "value": fmt(history["desnivel_m"].sum()), "unit": "m",
     "color": METRIC_COLORS["altitude_m"]},
    {"label": "Carga acumulada", "value": fmt(history["tss"].sum()), "unit": "TSS", "color": METRIC_COLORS["power_w"]},
    {"label": "Calorías", "value": fmt(history["calorias"].sum()), "unit": "kcal", "color": METRIC_COLORS["altitude_m"]},
])

if len(weekly) > 1:
    wcol1, wcol2 = st.columns(2, gap="large")
    with wcol1:
        st.plotly_chart(history_bar(weekly, "distancia_km", "Distancia por semana (km)", "km", METRIC_COLORS["speed_kmh"]),
                        width="stretch")
    with wcol2:
        st.plotly_chart(history_bar(weekly, "tss", "Carga por semana (TSS)", "TSS", METRIC_COLORS["power_w"]),
                        width="stretch")

col1, col2 = st.columns(2, gap="large")
with col1:
    st.plotly_chart(history_bar(history, "distancia_km", "Distancia por salida (km)", "km", METRIC_COLORS["speed_kmh"]),
                    width="stretch")
with col2:
    st.plotly_chart(history_bar(history, "tss", "Carga de entrenamiento por salida (TSS)", "TSS", METRIC_COLORS["power_w"]),
                    width="stretch")

col3, col4 = st.columns(2, gap="large")
with col3:
    st.plotly_chart(history_trend(history, "vel_kmh", "Velocidad media (km/h)", 1, METRIC_COLORS["speed_kmh"]),
                    width="stretch")
with col4:
    if history["ef"].notna().any():
        st.plotly_chart(history_trend(history, "ef", "Factor de eficiencia (NP / FC media)", 2, METRIC_COLORS["cadence"]),
                        width="stretch")
        st.caption("Un factor de eficiencia más alto significa más vatios por cada latido: mejor forma aeróbica.")

section("Detalle por actividad")
st.dataframe(
    history.assign(duracion=history["duracion_s"].map(format_duration)).drop(columns=["duracion_s", "fecha"]),
    hide_index=True, width="stretch",
    column_config={
        "etiqueta": "Fecha",
        "fuente": "Fuente",
        "distancia_km": st.column_config.NumberColumn("Distancia (km)", format="%.1f"),
        "duracion": "Tiempo",
        "vel_kmh": st.column_config.NumberColumn("Vel. media (km/h)", format="%.1f"),
        "desnivel_m": st.column_config.NumberColumn("Desnivel + (m)", format="%.0f"),
        "potencia_w": st.column_config.NumberColumn("Pot. media (W)", format="%.0f"),
        "np_w": st.column_config.NumberColumn("NP (W)", format="%.0f"),
        "fc_bpm": st.column_config.NumberColumn("FC media", format="%.0f"),
        "tss": st.column_config.NumberColumn("TSS", format="%.0f"),
        "ef": st.column_config.NumberColumn("EF", format="%.2f"),
        "calorias": st.column_config.NumberColumn("kcal", format="%.0f"),
    },
)

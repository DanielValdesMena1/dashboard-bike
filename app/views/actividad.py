import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.processing.insights import generate_insights
from src.processing.metrics import calculate_metrics, format_duration
from src.processing.performance import (
    HR_ZONES, POWER_ZONES, performance_summary, power_curve, splits, time_in_zones,
)
from src.ui.components import (
    fmt, format_date, hero, kpi_cards, list_activities,
    load_from_bytes, load_from_path, section,
)
from src.visualization.charts import performance_chart, power_curve_chart, splits_chart, zones_chart
from src.visualization.maps import COLOR_OPTIONS, build_route_map
from src.visualization.theme import METRIC_COLORS, ORANGE_RAMP, RED_RAMP

SPORT_NAMES = {"cycling": "Ciclismo", "running": "Carrera", "walking": "Caminata", "hiking": "Senderismo"}
SOURCE_TAGS = {"Garmin Connect": "Garmin", "Archivo FIT": "FIT"}


# ---------- Barra lateral: selección de actividad y parámetros ----------

with st.sidebar:
    source = st.radio("Origen de datos", ["Mis actividades", "Subir archivo"], horizontal=True)

    raw = records = session = None
    if source == "Subir archivo":
        uploaded = st.file_uploader("Archivo .fit", type=["fit"])
        if uploaded is not None:
            raw, records, session = load_from_bytes(uploaded.getvalue())
    else:
        activities = list_activities()
        if activities:
            # Etiqueta legible -> archivo (la más reciente primero)
            by_label = {}
            for a in activities:
                label = f"{a['label']} · {SOURCE_TAGS.get(a['source'], '')}".rstrip(" ·")
                if label in by_label:
                    label = f"{label} ({a['path'].stem})"
                by_label[label] = a["path"]
            selected = st.selectbox("Actividad", list(by_label))
            raw, records, session = load_from_path(by_label[selected])

if records is None:
    hero("Ride Analytics", "Sin actividades cargadas",
         "Conecta Garmin Connect, sube un archivo .fit desde la barra lateral o colócalo en data/raw/fit.")
    st.stop()

if records.empty:
    st.error("El archivo no contiene registros de actividad válidos.")
    st.stop()

summary = calculate_metrics(session)

with st.sidebar:
    st.divider()
    st.markdown("**Parámetros del ciclista**")
    ftp = st.number_input(
        "FTP (W)", min_value=50, max_value=600, value=int(summary["device_ftp_w"] or 250), step=5,
        help="Potencia umbral funcional. Por defecto se usa la configurada en el dispositivo.",
    )
    hr_max = st.number_input(
        "FC máxima (bpm)", min_value=120, max_value=230,
        value=max(190, int(summary["max_heart_rate"] or 0)), step=1,
        help="Se usa para calcular las zonas de frecuencia cardíaca.",
    )

has_power = "power_w" in records and records["power_w"].notna().any()
has_hr = "heart_rate" in records and records["heart_rate"].notna().any()

perf = performance_summary(records, ftp, summary["duration_s"])
curve = power_curve(records["power_w"]) if has_power else None
power_zones = time_in_zones(records["power_w"], ftp, POWER_ZONES) if has_power else None
hr_zones = time_in_zones(records["heart_rate"], hr_max, HR_ZONES) if has_hr else None

# ---------- Encabezado y KPIs ----------

subtitle = (
    (f"{session['name']} · " if session.get("name") else "")
    + f"{format_date(summary['start_time'], with_time=True)} · "
    f"Tiempo total {format_duration(summary['elapsed_s'])} · {len(records):,} registros".replace(",", ".")
)
sport = SPORT_NAMES.get(summary["sport"], str(summary["sport"] or "Actividad").capitalize())
hero(f"{sport} · {session.get('source', '')}".rstrip(" ·"), f"{fmt(summary['distance_km'], 1)} km de ruta", subtitle)

kpi_cards([
    {"label": "Distancia", "value": fmt(summary["distance_km"], 1), "unit": "km", "color": METRIC_COLORS["speed_kmh"]},
    {"label": "Tiempo en movimiento", "value": summary["duration_hms"], "color": METRIC_COLORS["speed_kmh"]},
    {"label": "Velocidad media", "value": fmt(summary["avg_speed_kmh"], 1), "unit": "km/h",
     "hint": f"Máx. {fmt(summary['max_speed_kmh'], 1)} km/h", "color": METRIC_COLORS["speed_kmh"]},
    {"label": "Desnivel positivo", "value": fmt(summary["elevation_gain_m"]), "unit": "m",
     "hint": f"Bajada {fmt(summary['elevation_loss_m'])} m", "color": METRIC_COLORS["altitude_m"]},
    {"label": "Calorías", "value": fmt(summary["calories"]), "unit": "kcal", "color": METRIC_COLORS["altitude_m"]},
])
kpi_cards([
    {"label": "Potencia media", "value": fmt(summary["avg_power_w"]), "unit": "W",
     "hint": f"Máx. {fmt(summary['max_power_w'])} W", "color": METRIC_COLORS["power_w"]},
    {"label": "Potencia normalizada", "value": fmt(perf["np_w"]), "unit": "W",
     "hint": f"VI {fmt(perf['variability_index'], 2)}", "color": METRIC_COLORS["power_w"]},
    {"label": "Carga (TSS)", "value": fmt(perf["tss"]), "hint": f"IF {fmt(perf['intensity_factor'], 2)}",
     "color": METRIC_COLORS["power_w"]},
    {"label": "FC media", "value": fmt(summary["avg_heart_rate"]), "unit": "bpm",
     "hint": f"Máx. {fmt(summary['max_heart_rate'])} bpm", "color": METRIC_COLORS["heart_rate"]},
    {"label": "Cadencia media", "value": fmt(summary["avg_cadence"]), "unit": "rpm", "color": METRIC_COLORS["cadence"]},
])

insights = generate_insights(summary, perf, records, power_zones, curve, ftp)
if insights:
    with st.container(border=True):
        st.markdown("### 🧠 Lo que dicen los datos")
        st.markdown("\n".join(f"- {text}" for text in insights))

# ---------- Mapa de la ruta ----------

section("🗺️ Ruta", "Trazado coloreado según la métrica elegida. Cambia el mapa base con el control de capas.")
options = [None] + [c for c in COLOR_OPTIONS if c in records and records[c].notna().any()]
color_by = st.segmented_control(
    "Colorear ruta por", options, default="speed_kmh" if "speed_kmh" in options else None,
    format_func=lambda c: "Color único" if c is None else COLOR_OPTIONS[c][0].split(" (")[0],
)
route_map = build_route_map(records, color_by)
if route_map is None:
    st.warning("Esta actividad no tiene datos GPS (por ejemplo, una sesión en rodillo).")
else:
    st_folium(route_map, height=620, use_container_width=True, returned_objects=[])

# ---------- Pestañas de análisis ----------

tab_perf, tab_zones, tab_curve, tab_splits, tab_data = st.tabs(
    ["📈 Rendimiento", "🎯 Zonas", "⚡ Curva de potencia", "📍 Parciales", "🧾 Datos y calidad"]
)

with tab_perf:
    section("Evolución durante la ruta", "Cada métrica en su propio panel, alineadas por distancia. Pasa el cursor para comparar.")
    fig = performance_chart(records)
    if fig is None:
        st.info("El archivo no trae datos de distancia para graficar.")
    else:
        st.plotly_chart(fig, width="stretch")

with tab_zones:
    col_power, col_hr = st.columns(2, gap="large")
    with col_power:
        section("Tiempo por zona de potencia", f"Zonas de Coggan sobre un FTP de {ftp} W. Z1 incluye el tiempo sin pedalear.")
        if power_zones is not None:
            st.plotly_chart(zones_chart(power_zones, ORANGE_RAMP, "W"), width="stretch")
        else:
            st.info("Esta actividad no tiene datos de potencia.")
    with col_hr:
        section("Tiempo por zona de frecuencia cardíaca", f"Porcentajes de una FC máxima de {hr_max} bpm.")
        if hr_zones is not None:
            st.plotly_chart(zones_chart(hr_zones, RED_RAMP, "bpm"), width="stretch")
        else:
            st.info("Esta actividad no tiene datos de frecuencia cardíaca.")

with tab_curve:
    section("Curva de potencia (mejores esfuerzos)",
            "La máxima potencia media que sostuviste durante cada duración. Escala logarítmica en el eje X.")
    if curve is not None and not curve.empty:
        st.plotly_chart(power_curve_chart(curve, ftp), width="stretch")
        table = curve.assign(pct_ftp=curve["power_w"] / ftp * 100)[["duracion", "power_w", "pct_ftp"]]
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "duracion": "Duración",
                "power_w": st.column_config.NumberColumn("Potencia (W)", format="%.0f"),
                "pct_ftp": st.column_config.ProgressColumn("% del FTP", format="%.0f%%", min_value=0, max_value=250),
            },
        )
    else:
        st.info("Esta actividad no tiene datos de potencia.")

with tab_splits:
    split_km = st.segmented_control("Longitud del tramo", [1, 5, 10], default=5, format_func=lambda v: f"{v} km")
    split_table = splits(records, split_km or 5)
    if split_table.empty:
        st.info("No hay datos de distancia para calcular parciales.")
    else:
        section("Velocidad por tramo", "El color de cada barra indica cuánto se subió en ese tramo.")
        st.plotly_chart(splits_chart(split_table), width="stretch")
        st.dataframe(
            split_table.assign(tiempo=split_table["tiempo_s"].map(format_duration)).drop(columns="tiempo_s"),
            hide_index=True, width="stretch",
            column_config={
                "tramo": "Tramo",
                "distancia_km": st.column_config.NumberColumn("Distancia (km)", format="%.2f"),
                "tiempo": "Tiempo",
                "vel_kmh": st.column_config.NumberColumn("Vel. media (km/h)", format="%.1f"),
                "desnivel_m": st.column_config.NumberColumn("Desnivel + (m)", format="%.0f"),
                "potencia_w": st.column_config.NumberColumn("Potencia (W)", format="%.0f"),
                "fc_bpm": st.column_config.NumberColumn("FC (bpm)", format="%.0f"),
            },
        )

with tab_data:
    section("Validación de los cálculos",
            "Las métricas avanzadas se calculan desde los datos segundo a segundo y se comparan con las que calculó el dispositivo.")
    reference = "Dispositivo"
    checks = pd.DataFrame([
        {"Métrica": "Potencia normalizada (W)", "Calculado": perf["np_w"], reference: summary["device_np_w"]},
        {"Métrica": "Intensity Factor", "Calculado": perf["intensity_factor"], reference: summary["device_if"]},
        {"Métrica": "TSS", "Calculado": perf["tss"], reference: summary["device_tss"]},
        {"Métrica": "Potencia media (W)", "Calculado": records["power_w"].mean() if has_power else None,
         reference: summary["avg_power_w"]},
        {"Métrica": "FC media (bpm)", "Calculado": records["heart_rate"].mean() if has_hr else None,
         reference: summary["avg_heart_rate"]},
    ]).dropna()
    checks["Diferencia %"] = (checks["Calculado"] - checks[reference]) / checks[reference] * 100
    st.dataframe(
        checks, hide_index=True, width="stretch",
        column_config={
            "Calculado": st.column_config.NumberColumn(format="%.2f"),
            reference: st.column_config.NumberColumn(format="%.2f"),
            "Diferencia %": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )
    st.caption(
        "El dispositivo muestra la potencia normalizada redondeada hacia arriba "
        "(p. ej. 165,1 W → 166 W); el IF y el TSS del dispositivo usan sus valores internos."
    )
    if summary["device_ftp_w"] and ftp != summary["device_ftp_w"]:
        st.caption(f"⚠️ IF y TSS del dispositivo usan su FTP ({summary['device_ftp_w']:.0f} W); aquí estás usando {ftp} W.")

    section("Calidad de los datos", "Porcentaje de valores faltantes por columna en los registros crudos del archivo.")
    known = raw[[c for c in raw.columns if not c.startswith("unknown_")]]
    quality = pd.DataFrame({
        "Columna": known.columns,
        "Valores": known.notna().sum().values,
        "Faltantes %": (known.isna().mean() * 100).values,
    }).sort_values("Faltantes %", ascending=False)
    st.dataframe(
        quality, hide_index=True, width="stretch",
        column_config={"Faltantes %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)},
    )

    section("Registros procesados", "Datos limpios y en unidades legibles, listos para exportar.")
    st.dataframe(records.head(500), width="stretch", height=320)
    st.download_button(
        "⬇️ Descargar CSV", records.to_csv(index=False).encode("utf-8"),
        file_name="actividad_procesada.csv", mime="text/csv",
    )

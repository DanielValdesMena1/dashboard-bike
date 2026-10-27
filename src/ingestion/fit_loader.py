from __future__ import annotations

from datetime import datetime, timedelta
from typing import BinaryIO

import pandas as pd
from fitparse import FitFile

# Garmin guarda las coordenadas en "semicírculos" (enteros de 32 bits)
SEMICIRCLES_TO_DEGREES = 180 / (2**31)

GPS_CANDIDATES = [
    ("position_lat", "position_long"),
    ("enhanced_position_lat", "enhanced_position_long"),
]


def load_fit(source: str | bytes | BinaryIO) -> tuple[pd.DataFrame, dict]:
    """Carga un archivo FIT y retorna (records crudos, resumen de la sesión).

    `source` puede ser una ruta, bytes o un archivo subido desde Streamlit.
    """
    fitfile = FitFile(source)

    # Records: un registro por segundo (GPS, potencia, FC, cadencia...)
    records = [{field.name: field.value for field in msg} for msg in fitfile.get_messages("record")]
    df = pd.DataFrame(records)

    # Session: resumen calculado por el dispositivo. Se descartan los campos
    # vacíos para que session.get(campo) nunca devuelva None.
    session: dict = {}
    for msg in fitfile.get_messages("session"):
        session = {field.name: field.value for field in msg if field.value is not None}
        break  # Solo la primera sesión

    # Las horas del FIT vienen en UTC; se pasan a hora local del dispositivo
    offset = _utc_offset(fitfile)
    if offset:
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"]) + offset
        for key in ("start_time", "timestamp"):
            if isinstance(session.get(key), datetime):
                session[key] += offset

    return df, session


def _utc_offset(fitfile: FitFile) -> timedelta | None:
    """Diferencia entre hora local y UTC, según el mensaje `activity`."""
    for msg in fitfile.get_messages("activity"):
        local, utc = msg.get_value("local_timestamp"), msg.get_value("timestamp")
        if isinstance(local, datetime) and isinstance(utc, datetime):
            # Redondeo a 15 min (todas las zonas horarias son múltiplo de 15 min)
            minutes = round((local - utc).total_seconds() / 900) * 15
            return timedelta(minutes=minutes)
    return None


def pick_gps_columns(df: pd.DataFrame) -> tuple[str, str] | None:
    """Algunos FIT traen position_lat/long y otros enhanced_position_lat/long."""
    for lat, lon in GPS_CANDIDATES:
        if lat in df.columns and lon in df.columns:
            if df[lat].notna().any() and df[lon].notna().any():
                return lat, lon
    return None


def _first_available(df: pd.DataFrame, *names: str) -> pd.Series | None:
    for name in names:
        if name in df.columns and df[name].notna().any():
            return pd.to_numeric(df[name], errors="coerce")
    return None


def prepare_records(raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los records crudos a columnas estándar y unidades legibles.

    Columnas resultantes (las que el archivo traiga):
    timestamp, elapsed_s, distance_km, speed_kmh, altitude_m, power_w,
    heart_rate, cadence, temperature_c, lat, lon
    """
    if raw.empty or "timestamp" not in raw.columns:
        return pd.DataFrame()

    raw = raw.sort_values("timestamp").reset_index(drop=True)
    df = pd.DataFrame({"timestamp": pd.to_datetime(raw["timestamp"])})
    df["elapsed_s"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

    # destino: (columnas origen en orden de preferencia, factor de conversión)
    conversions = {
        "distance_km": (("distance",), 1 / 1000),
        "speed_kmh": (("enhanced_speed", "speed"), 3.6),
        "altitude_m": (("enhanced_altitude", "altitude"), 1),
        "power_w": (("power",), 1),
        "heart_rate": (("heart_rate",), 1),
        "cadence": (("cadence",), 1),
        "temperature_c": (("temperature",), 1),
    }
    for target, (sources, factor) in conversions.items():
        series = _first_available(raw, *sources)
        if series is not None:
            df[target] = series * factor

    gps_cols = pick_gps_columns(raw)
    if gps_cols is not None:
        lat = pd.to_numeric(raw[gps_cols[0]], errors="coerce") * SEMICIRCLES_TO_DEGREES
        lon = pd.to_numeric(raw[gps_cols[1]], errors="coerce") * SEMICIRCLES_TO_DEGREES
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        df["lat"] = lat.where(valid)
        df["lon"] = lon.where(valid)

    return df

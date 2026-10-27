"""Métricas de rendimiento calculadas a partir de los datos segundo a segundo.

Supuesto: el dispositivo graba a 1 Hz (un registro por segundo), por lo que
cada fila equivale a un segundo de actividad.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Zonas de potencia de Coggan, como fracción del FTP
POWER_ZONES = [
    ("Z1 Recuperación", 0.00, 0.55),
    ("Z2 Resistencia", 0.55, 0.75),
    ("Z3 Tempo", 0.75, 0.90),
    ("Z4 Umbral", 0.90, 1.05),
    ("Z5 VO2máx", 1.05, 1.20),
    ("Z6 Anaeróbico", 1.20, 1.50),
    ("Z7 Neuromuscular", 1.50, math.inf),
]

# Zonas de frecuencia cardíaca, como fracción de la FC máxima
HR_ZONES = [
    ("Z1 Muy suave", 0.00, 0.60),
    ("Z2 Suave", 0.60, 0.70),
    ("Z3 Moderado", 0.70, 0.80),
    ("Z4 Intenso", 0.80, 0.90),
    ("Z5 Máximo", 0.90, math.inf),
]

POWER_CURVE_DURATIONS = [5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600, 5400, 7200]


def duration_label(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    hours = seconds / 3600
    return f"{hours:g} h"


def normalized_power(power: pd.Series) -> float | None:
    """Potencia normalizada (NP): media móvil de 30 s, elevada a la 4ª,
    promediada y con raíz 4ª. Pondera más los esfuerzos intensos.

    Las lecturas perdidas del sensor (NaN) se excluyen: no son 0 W, sino datos
    que faltan. Garmin muestra este mismo valor redondeado hacia arriba.
    """
    power = power.dropna().reset_index(drop=True)
    if len(power) < 30:
        return None
    rolling = power.rolling(30).mean().dropna()
    return float((rolling**4).mean() ** 0.25)


def training_load(np_w: float | None, ftp_w: float, duration_s: float | None) -> dict:
    """Intensity Factor (IF) y Training Stress Score (TSS)."""
    if not np_w or not ftp_w or not duration_s:
        return {"intensity_factor": None, "tss": None}
    intensity = np_w / ftp_w
    tss = (duration_s * np_w * intensity) / (ftp_w * 3600) * 100
    return {"intensity_factor": intensity, "tss": tss}


def power_curve(power: pd.Series, durations: list[int] = POWER_CURVE_DURATIONS) -> pd.DataFrame:
    """Mejor potencia media sostenida para cada duración (mean-max power)."""
    power = power.fillna(0).reset_index(drop=True)
    rows = []
    for d in durations:
        if d > len(power):
            break
        rows.append({
            "duration_s": d,
            "duracion": duration_label(d),
            "power_w": float(power.rolling(d).mean().max()),
        })
    return pd.DataFrame(rows, columns=["duration_s", "duracion", "power_w"])


def time_in_zones(values: pd.Series, reference: float, zones: list[tuple]) -> pd.DataFrame:
    """Segundos y % del tiempo en cada zona (`reference` = FTP o FC máx.)."""
    values = values.dropna()
    names = [z[0] for z in zones]
    edges = [zones[0][1]] + [z[2] for z in zones]
    ratio = values / reference
    bins = pd.cut(ratio, bins=edges, labels=names, right=False, include_lowest=True)
    seconds = bins.value_counts().reindex(names, fill_value=0)

    total = seconds.sum()
    pct = seconds / total * 100 if total else seconds * 0.0
    low = [round(z[1] * reference) for z in zones]
    high = [round(z[2] * reference) if math.isfinite(z[2]) else None for z in zones]
    return pd.DataFrame({
        "zona": names,
        "desde": low,
        "hasta": high,
        "segundos": seconds.values,
        "pct": pct.values,
    })


def splits(df: pd.DataFrame, split_km: float = 5) -> pd.DataFrame:
    """Parciales cada `split_km` kilómetros."""
    if "distance_km" not in df.columns:
        return pd.DataFrame()

    data = df.dropna(subset=["distance_km"]).copy()
    data["tramo"] = (data["distance_km"] // split_km).astype(int)
    # Se calcula antes de agrupar para no perder la subida entre un tramo y el siguiente
    if "altitude_m" in data:
        data["subida_m"] = data["altitude_m"].diff().clip(lower=0).fillna(0)

    rows = []
    for tramo, g in data.groupby("tramo"):
        row = {
            "tramo": f"{tramo * split_km:g}–{tramo * split_km + split_km:g} km",
            "distancia_km": g["distance_km"].max() - g["distance_km"].min(),
            "tiempo_s": len(g),
        }
        row["vel_kmh"] = row["distancia_km"] / (row["tiempo_s"] / 3600) if row["tiempo_s"] else np.nan
        if "subida_m" in g:
            row["desnivel_m"] = float(g["subida_m"].sum())
        if "power_w" in g:
            row["potencia_w"] = g["power_w"].mean()
        if "heart_rate" in g:
            row["fc_bpm"] = g["heart_rate"].mean()
        rows.append(row)

    # El último tramo suele ser incompleto (p. ej. 1,7 km)
    return pd.DataFrame(rows)


def aerobic_decoupling(df: pd.DataFrame) -> float | None:
    """Desacople aeróbico Pw:HR (%): cuánto cae la relación potencia/FC entre
    la primera y la segunda mitad. < 5 % suele indicar buena base aeróbica."""
    if "power_w" not in df or "heart_rate" not in df:
        return None
    data = df[["power_w", "heart_rate"]].dropna()
    data = data[data["heart_rate"] > 0]
    if len(data) < 600:
        return None
    half = len(data) // 2
    first, second = data.iloc[:half], data.iloc[half:]
    ef1 = first["power_w"].mean() / first["heart_rate"].mean()
    ef2 = second["power_w"].mean() / second["heart_rate"].mean()
    return float((ef1 - ef2) / ef1 * 100)


def performance_summary(df: pd.DataFrame, ftp_w: float, duration_s: float | None) -> dict:
    """Agrupa las métricas avanzadas de una actividad."""
    result = {
        "np_w": None, "intensity_factor": None, "tss": None,
        "variability_index": None, "efficiency_factor": None,
        "decoupling_pct": aerobic_decoupling(df),
    }
    if "power_w" in df.columns and df["power_w"].notna().any():
        np_w = normalized_power(df["power_w"])
        avg_w = df["power_w"].mean()  # Sin lecturas perdidas, igual que la NP
        result["np_w"] = np_w
        result.update(training_load(np_w, ftp_w, duration_s or len(df)))
        if np_w and avg_w:
            result["variability_index"] = np_w / avg_w
        if np_w and "heart_rate" in df.columns and df["heart_rate"].mean() > 0:
            result["efficiency_factor"] = np_w / df["heart_rate"].mean()
    return result

"""Convierte las métricas en conclusiones en lenguaje natural."""
from __future__ import annotations

import pandas as pd

from src.processing.metrics import format_number as fmt


def _intensity_label(intensity: float) -> str:
    if intensity < 0.75:
        return "un rodaje de resistencia / recuperación"
    if intensity < 0.85:
        return "una salida a ritmo tempo"
    if intensity < 0.95:
        return "un esfuerzo cercano al umbral"
    return "un esfuerzo de intensidad de carrera"


def generate_insights(
    summary: dict,
    perf: dict,
    records: pd.DataFrame,
    power_zones: pd.DataFrame | None,
    curve: pd.DataFrame | None,
    ftp_w: float,
) -> list[str]:
    insights: list[str] = []

    intensity = perf.get("intensity_factor")
    if intensity:
        insights.append(
            f"Con un IF de **{fmt(intensity, 2)}** y un TSS de **{perf['tss']:.0f}**, "
            f"fue {_intensity_label(intensity)}."
        )

    vi = perf.get("variability_index")
    if vi:
        if vi < 1.06:
            insights.append(f"Índice de variabilidad de **{fmt(vi, 2)}**: ritmo muy constante, típico de llano o rodillo.")
        elif vi < 1.15:
            insights.append(f"Índice de variabilidad de **{fmt(vi, 2)}**: esfuerzo moderadamente variable.")
        else:
            insights.append(
                f"Índice de variabilidad de **{fmt(vi, 2)}**: esfuerzo muy irregular "
                "(subidas, aceleraciones o rodar en grupo). La NP refleja mejor el coste real que la potencia media."
            )

    if "power_w" in records and records["power_w"].notna().any():
        coasting = (records["power_w"].dropna() == 0).mean() * 100
        if coasting >= 10:
            insights.append(f"Pasaste un **{coasting:.0f}%** del tiempo sin pedalear (bajadas, semáforos o rueda).")

    if power_zones is not None and not power_zones.empty:
        active = power_zones.iloc[1:]  # sin Z1, que incluye el tiempo sin pedalear
        top = active.loc[active["pct"].idxmax()]
        high = power_zones.loc[power_zones["zona"].str[:2].isin(["Z4", "Z5", "Z6", "Z7"]), "segundos"].sum()
        insights.append(
            f"Fuera de Z1, la zona más trabajada fue **{top['zona']}** ({top['pct']:.0f}% del tiempo); "
            f"acumulaste **{high / 60:.0f} min** en Z4 o superior."
        )

    if curve is not None and not curve.empty:
        best20 = curve.loc[curve["duration_s"] == 1200, "power_w"]
        if not best20.empty:
            best = best20.iloc[0]
            insights.append(
                f"Tu mejor bloque de 20 min fue **{best:.0f} W** ({best / ftp_w * 100:.0f}% del FTP). "
                f"Si hubiera sido un test a tope, equivaldría a un FTP de ≈ {best * 0.95:.0f} W."
            )

    decoupling = perf.get("decoupling_pct")
    if decoupling is not None:
        if vi and vi >= 1.15:
            insights.append(
                f"Desacople aeróbico de **{fmt(decoupling, 1)}%**, pero con esfuerzos tan variables "
                "este indicador es poco fiable; úsalo en salidas de ritmo constante."
            )
        elif decoupling < 5:
            insights.append(f"Desacople aeróbico de **{fmt(decoupling, 1)}%**: buena resistencia, la FC se mantuvo estable.")
        else:
            insights.append(f"Desacople aeróbico de **{fmt(decoupling, 1)}%**: la FC subió respecto a la potencia en la segunda mitad (fatiga o calor).")

    distance, gain = summary.get("distance_km"), summary.get("elevation_gain_m")
    if distance and gain:
        insights.append(f"Promedio de **{fmt(gain / distance, 1)} m de desnivel por km**.")

    return insights

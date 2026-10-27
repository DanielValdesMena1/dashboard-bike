from __future__ import annotations

from datetime import datetime


def _num(session: dict, *keys: str) -> float | None:
    """Primer valor numérico disponible entre las claves dadas."""
    for key in keys:
        value = session.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def format_number(value: float | None, decimals: int = 0) -> str:
    """Número con formato español (1.234,5), o guion si falta el dato."""
    if value is None or value != value:  # None o NaN
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def calculate_metrics(session: dict) -> dict:
    """Resumen de la actividad a partir del mensaje `session` del FIT.

    Las métricas que el archivo no trae quedan en None (no en 0), para no
    confundir "sin sensor" con "valor cero".
    """
    duration_s = _num(session, "total_timer_time")
    distance_m = _num(session, "total_distance")
    avg_speed = _num(session, "enhanced_avg_speed", "avg_speed")
    max_speed = _num(session, "enhanced_max_speed", "max_speed")

    start_time = session.get("start_time")

    return {
        "start_time": start_time if isinstance(start_time, datetime) else None,
        "sport": session.get("sport"),
        "duration_s": duration_s,
        "duration_hms": format_duration(duration_s),
        "elapsed_s": _num(session, "total_elapsed_time"),
        "distance_km": distance_m / 1000 if distance_m is not None else None,
        "avg_speed_kmh": avg_speed * 3.6 if avg_speed is not None else None,
        "max_speed_kmh": max_speed * 3.6 if max_speed is not None else None,
        "elevation_gain_m": _num(session, "total_ascent"),
        "elevation_loss_m": _num(session, "total_descent"),
        "avg_power_w": _num(session, "avg_power"),
        "max_power_w": _num(session, "max_power"),
        "avg_heart_rate": _num(session, "avg_heart_rate"),
        "max_heart_rate": _num(session, "max_heart_rate"),
        "avg_cadence": _num(session, "avg_cadence"),
        "calories": _num(session, "total_calories"),
        "avg_temperature_c": _num(session, "avg_temperature"),
        # Valores que calcula el propio Garmin (sirven para validar los nuestros)
        "device_ftp_w": _num(session, "threshold_power"),
        "device_np_w": _num(session, "normalized_power"),
        "device_tss": _num(session, "training_stress_score"),
        "device_if": _num(session, "intensity_factor"),
    }

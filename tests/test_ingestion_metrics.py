from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.fit_loader import SEMICIRCLES_TO_DEGREES, load_fit, prepare_records
from src.processing.metrics import calculate_metrics, format_duration, format_number
from src.processing.performance import performance_summary

FIT_FILES = sorted((Path(__file__).resolve().parents[1] / "data" / "raw" / "fit").glob("*.fit"))


def test_semicircles_conversion():
    assert 2**31 * SEMICIRCLES_TO_DEGREES == pytest.approx(180.0)


def test_prepare_records_converts_units():
    raw = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="s"),
        "speed": [10.0, 10.0, 10.0],          # m/s
        "distance": [0.0, 10.0, 20.0],        # m
        "position_lat": [2**30, 2**30, None],  # 90° en semicírculos
        "position_long": [0, 0, None],
    })
    df = prepare_records(raw)
    assert df["speed_kmh"].tolist() == [36.0, 36.0, 36.0]
    assert df["distance_km"].iloc[-1] == pytest.approx(0.02)
    assert df["elapsed_s"].tolist() == [0.0, 1.0, 2.0]
    assert df["lat"].iloc[0] == pytest.approx(90.0)
    assert pd.isna(df["lat"].iloc[-1])


def test_calculate_metrics_handles_missing_sensors():
    metrics = calculate_metrics({"total_timer_time": 3725, "total_distance": 30000})
    assert metrics["duration_hms"] == "1:02:05"
    assert metrics["distance_km"] == 30
    assert metrics["avg_power_w"] is None
    assert metrics["avg_heart_rate"] is None


def test_formatters():
    assert format_number(1234.5, 1) == "1.234,5"
    assert format_number(None) == "—"
    assert format_duration(None) == "—"


@pytest.mark.skipif(not FIT_FILES, reason="No hay archivos FIT de ejemplo")
@pytest.mark.parametrize("path", FIT_FILES, ids=lambda p: p.stem)
def test_normalized_power_matches_garmin(path):
    """La NP calculada desde los datos crudos debe coincidir con la del dispositivo (±1 %)."""
    raw, session = load_fit(str(path))
    summary = calculate_metrics(session)
    if summary["device_np_w"] is None:
        pytest.skip("El archivo no trae NP del dispositivo")
    perf = performance_summary(prepare_records(raw), summary["device_ftp_w"], summary["duration_s"])
    assert perf["np_w"] == pytest.approx(summary["device_np_w"], rel=0.01)
    assert perf["tss"] == pytest.approx(summary["device_tss"], rel=0.01)

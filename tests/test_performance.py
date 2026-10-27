import math

import numpy as np
import pandas as pd
import pytest

from src.processing.performance import (
    POWER_ZONES, aerobic_decoupling, normalized_power, power_curve, splits,
    time_in_zones, training_load,
)


def test_normalized_power_of_constant_effort_equals_that_power():
    assert normalized_power(pd.Series([200.0] * 600)) == pytest.approx(200.0)


def test_normalized_power_rewards_variable_efforts():
    # Misma potencia media (200 W), pero en bloques alternos de 400 W y 0 W
    variable = pd.Series(([400.0] * 60 + [0.0] * 60) * 10)
    assert variable.mean() == pytest.approx(200.0)
    assert normalized_power(variable) > 250


def test_normalized_power_ignores_sensor_dropouts():
    # Un corte del sensor (NaN) no debe contar como 0 W
    power = pd.Series([200.0] * 300 + [np.nan] * 20 + [200.0] * 300)
    assert normalized_power(power) == pytest.approx(200.0)


def test_normalized_power_needs_at_least_30_seconds():
    assert normalized_power(pd.Series([200.0] * 10)) is None


def test_training_load_one_hour_at_ftp_is_100_tss():
    load = training_load(np_w=250, ftp_w=250, duration_s=3600)
    assert load["intensity_factor"] == pytest.approx(1.0)
    assert load["tss"] == pytest.approx(100.0)


def test_power_curve_finds_best_effort_and_is_non_increasing():
    power = pd.Series([150.0] * 300 + [400.0] * 60 + [150.0] * 300)
    curve = power_curve(power, durations=[5, 60, 300])
    assert curve.loc[curve["duration_s"] == 60, "power_w"].iloc[0] == pytest.approx(400.0)
    assert curve["power_w"].is_monotonic_decreasing


def test_time_in_zones_covers_all_samples():
    power = pd.Series(np.linspace(0, 500, 1000))
    zones = time_in_zones(power, reference=250, zones=POWER_ZONES)
    assert zones["segundos"].sum() == 1000
    assert zones["pct"].sum() == pytest.approx(100.0)
    assert math.isnan(zones["hasta"].iloc[-1])  # La última zona no tiene techo


def test_splits_by_kilometre():
    df = pd.DataFrame({
        "distance_km": np.linspace(0, 2.999, 900),
        "altitude_m": np.linspace(100, 130, 900),
    })
    result = splits(df, split_km=1)
    assert len(result) == 3
    assert result["desnivel_m"].sum() == pytest.approx(30.0)


def test_decoupling_is_zero_when_ratio_is_stable():
    df = pd.DataFrame({"power_w": [200.0] * 1200, "heart_rate": [140.0] * 1200})
    assert aerobic_decoupling(df) == pytest.approx(0.0)


def test_decoupling_is_positive_when_heart_rate_drifts():
    hr = [140.0] * 600 + [154.0] * 600  # +10 % de FC con la misma potencia
    df = pd.DataFrame({"power_w": [200.0] * 1200, "heart_rate": hr})
    assert aerobic_decoupling(df) == pytest.approx(9.09, abs=0.01)

import math

from aiot_sim.constants import SENSORS
from aiot_sim.pipeline.aggregator import aggregate
from aiot_sim.pipeline.writer import json_write, read_csv, write_csv


def test_leq_missing_and_energy(tmp_path):
    json_write(tmp_path / "reports/manifest.json", {"config": {"step_minutes": 1}})
    rows = [
        dict(
            timestamp=f"2026-09-01T09:0{i}:00+09:00",
            room_id="X",
            **{s: 1 for s in SENSORS},
        )
        for i in range(5)
    ]
    for i, r in enumerate(rows):
        r["noise_dba"] = 40 if i == 0 else 60
    rows[0]["co2_ppm"] = None
    write_csv(tmp_path / "raw/sensors_1min/sensor_readings_2026-09-01.csv", rows)
    write_csv(
        tmp_path / "raw/energy_usage_1min/energy_usage_2026-09-01.csv",
        [
            {
                "timestamp": r["timestamp"],
                "room_id": "X",
                "total_power_kw": 6,
                "interval_energy_kwh": 0.1,
            }
            for r in rows
        ],
    )
    assert aggregate(tmp_path) == 1
    r = next(read_csv(tmp_path / "derived/sensors_5min/sensor_readings_2026-09-01.csv"))
    assert math.isclose(
        float(r["noise_leq_dba"]), 10 * math.log10((10**4 + 4 * 10**6) / 5)
    )
    assert math.isclose(float(r["co2_ppm_missing_ratio"]), 0.2)

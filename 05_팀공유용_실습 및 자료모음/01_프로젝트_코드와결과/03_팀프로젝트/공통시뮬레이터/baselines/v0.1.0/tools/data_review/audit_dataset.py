"""Read-only streaming audit of dataset characteristics, not real-world calibration."""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from aiot_sim.config import load  # noqa: E402
from aiot_sim.engines.energy import energy  # noqa: E402
from aiot_sim.engines.environment import evolve  # noqa: E402
from aiot_sim.schemas import EnvironmentState, FacilityState  # noqa: E402


def rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def audit(run):
    profiles = {r["room_id"]: r for r in rows(run / "inputs/room_profiles.csv")}
    stats = {
        v: dict(n=0, sum=0.0, min=None, max=None)
        for v in [
            "temperature_c",
            "humidity_pct",
            "co2_ppm",
            "illuminance_lux",
            "noise_dba",
            "occupancy_count",
        ]
    }
    missing = Counter()
    counts = Counter()
    days = []
    energy_sum = 0.0
    demand = defaultdict(lambda: Counter())
    empty_power = 0.0
    for path in sorted((run / "truth/environment_truth_1min").glob("*.csv")):
        day = path.stem[-10:]
        daily = 0
        sensors = rows(run / f"raw/sensors_1min/sensor_readings_{day}.csv")
        energies = rows(run / f"raw/energy_usage_1min/energy_usage_{day}.csv")
        for t, s, e in zip(rows(path), sensors, energies, strict=True):
            key = t["timestamp"], t["room_id"]
            if key != (s["timestamp"], s["room_id"]) or key != (
                e["timestamp"],
                e["room_id"],
            ):
                raise ValueError("Parallel keys mismatch")
            rid = t["room_id"]
            p = profiles[rid]
            n = int(t["true_occupancy_count"])
            ts = datetime.fromisoformat(t["timestamp"])
            opened = p["opening_time"] <= ts.strftime("%H:%M") < p["closing_time"]
            counts["rows"] += 1
            daily += 1
            for v, st in stats.items():
                val = float(t["true_" + v])
                st["n"] += 1
                st["sum"] += val
                st["min"] = val if st["min"] is None else min(st["min"], val)
                st["max"] = val if st["max"] is None else max(st["max"], val)
                if s[v] == "":
                    missing[v] += 1
            if opened:
                counts["operating_room_minutes"] += 1
                counts["occupied_operating_room_minutes"] += n > 0
                bucket = "weekend" if ts.weekday() >= 5 else "weekday"
                demand[bucket]["room_minutes"] += 1
                demand[bucket]["occupied_minutes"] += n > 0
                demand[bucket]["people_minutes"] += n
            else:
                counts["outside_hours_occupied"] += n > 0
            if n:
                counts["occupied_room_minutes"] += 1
                for field, threshold, label in [
                    ("co2_ppm", 1000, "co2_gt_1000"),
                    ("co2_ppm", 1500, "co2_gt_1500"),
                    ("humidity_pct", 80, "rh_gt_80"),
                ]:
                    counts[label + "_occupied"] += float(t["true_" + field]) > threshold
                counts["temperature_outside_config_targets_occupied"] += (
                    not 20 <= float(t["true_temperature_c"]) <= 26
                )
            for field, threshold, label in [
                ("humidity_pct", 80, "rh_gt_80_all"),
                ("co2_ppm", 1000, "co2_gt_1000_all"),
            ]:
                counts[label] += float(t["true_" + field]) > threshold
            energy_sum += float(e["interval_energy_kwh"])
            if not n:
                empty_power += float(e["interval_energy_kwh"])
        days.append(dict(date=day, rows=daily))
        print(day, daily, flush=True)
    for st in stats.values():
        st["mean"] = st.pop("sum") / st["n"]
    design = []
    for rid, p in profiles.items():
        a = float(p["ventilation_on_ach"])
        v = float(p["volume_m3"])
        n = int(p["capacity"])
        design.append(
            dict(
                room_id=rid,
                maximum_ventilation_l_s_person=a * v / 3.6 / n,
                full_capacity_equilibrium_co2_ppm=425 + n * 0.018 * 1e6 / (a * v),
            )
        )
    cfg = load(ROOT)
    p = {**next(iter(profiles.values()))}
    for k in [
        "volume_m3",
        "thermal_response_factor",
        "daylight_exposure_factor",
        "ventilation_off_ach",
        "ventilation_on_ach",
        "noise_baseline_dba",
        "hvac_power_kw",
        "ventilation_power_kw",
        "lighting_power_kw",
        "standby_power_kw",
    ]:
        p[k] = float(p[k])
    out = dict(
        outdoor_temperature_c=28.0,
        outdoor_humidity_pct=60.0,
        outdoor_co2_ppm=425.0,
        daylight_factor=0.5,
        outdoor_noise_dba=50.0,
    )
    f = FacilityState(hvac_mode="cooling", hvac_on=True)
    a = EnvironmentState()
    b = deepcopy(a)
    p2 = dict(p, hvac_power_kw=p["hvac_power_kw"] * 10)
    evolve(a, p, f, out, 4, cfg["rules"]["environment"])
    evolve(b, p2, f, out, 4, cfg["rules"]["environment"])
    experiments = dict(
        hvac_power_sensitivity=dict(
            power_multiplier=10,
            temperature_first_c=a.temperature_c,
            temperature_second_c=b.temperature_c,
            temperature_identical=a.temperature_c == b.temperature_c,
            hvac_kw_first=energy(p, f, cfg["rules"]["facility"])["hvac_power_kw"],
            hvac_kw_second=energy(p2, f, cfg["rules"]["facility"])["hvac_power_kw"],
        )
    )
    reservations = list(rows(run / "events/reservations.csv"))
    faults = list(rows(run / "truth/anomaly_events.csv"))
    return dict(
        scope="synthetic internal consistency and distribution; no empirical calibration",
        run_id=run.name,
        truth_statistics=stats,
        sensor_missing=dict(missing),
        counts=dict(counts),
        demand={k: dict(v) for k, v in demand.items()},
        days=days,
        total_energy_kwh=energy_sum,
        unoccupied_energy_kwh=empty_power,
        design=design,
        counterfactual_experiments=experiments,
        reservation_counts=dict(Counter(r["status"] for r in reservations)),
        no_show_confirmed=sum(
            r["status"] == "confirmed" and r["is_no_show"] == "true"
            for r in reservations
        ),
        fault_counts=dict(Counter(f["anomaly_type"] for f in faults)),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="full-30d")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = audit(ROOT / "data/runs" / args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("saved", args.output)

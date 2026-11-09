"""Independent checks of trace units, analytical temperature and label semantics."""

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from .writer import read_csv


def validate_physics(run, manifest):
    cfg = manifest["config"]
    step = cfg["step_minutes"]
    rules = cfg["rules"]["environment"]["thermal"]
    bounds = cfg["rules"]["anomaly_label"]
    profiles = {p["room_id"]: p for p in read_csv(run / "inputs/room_profiles.csv")}
    errors = []
    counts = Counter()
    last = {}
    total_residual = 0.0
    max_residual = 0.0
    maximum_temperature = -math.inf

    def check(ok, message):
        if not ok and message not in errors:
            errors.append(message)

    for path in sorted((run / "truth/thermal_balance_1min").glob("*.csv")):
        day = path.stem[-10:]
        power_sum = defaultdict(float)
        starts = {}
        energy = iter(read_csv(run / f"raw/energy_usage_1min/energy_usage_{day}.csv"))
        truth = iter(
            read_csv(run / f"truth/environment_truth_1min/environment_truth_{day}.csv")
        )
        for row in read_csv(path):
            rid = row["room_id"]
            stamp = row["timestamp"]
            t = datetime.fromisoformat(stamp)
            minute = t.hour * 60 + t.minute
            values = {
                k: float(v) for k, v in row.items() if k not in {"timestamp", "room_id"}
            }
            check(
                all(math.isfinite(v) for v in values.values()),
                "Nonfinite thermal trace",
            )
            cap = values["effective_heat_capacity_kj_k"]
            start = values["start_temperature_c"]
            end = values["end_temperature_c"]
            ua = values["envelope_ua_kw_k"] + values["ventilation_ua_kw_k"]
            out = values["outdoor_temperature_c"]
            profile = profiles[rid]
            expected_cap = (
                float(profile["area_m2"]) * rules["effective_capacity_kj_m2_k"]
                + float(profile["volume_m3"])
                * rules["air_density_kg_m3"]
                * rules["air_specific_heat_kj_kg_k"]
            )
            check(
                math.isclose(cap, expected_cap, rel_tol=1e-12),
                "Thermal capacity mismatch",
            )
            stored = cap * (end - start) / 3600
            heat = sum(
                values[k]
                for k in [
                    "envelope_heat_kwh",
                    "ventilation_heat_kwh",
                    "people_heat_kwh",
                    "other_heat_kwh",
                    "hvac_heat_kwh",
                ]
            )
            residual = stored - heat
            max_residual = max(max_residual, abs(residual))
            total_residual += residual
            check(
                abs(residual) < 1e-8
                and math.isclose(stored, values["stored_heat_kwh"], abs_tol=1e-10),
                "Thermal energy balance failed",
            )
            check(
                abs(values["balance_residual_kwh"] - residual) < 1e-10,
                "Stored balance residual inconsistent",
            )
            for component in ["people", "other", "hvac"]:
                check(
                    math.isclose(
                        values[component + "_heat_kw"]
                        if component != "hvac"
                        else values["hvac_thermal_power_kw"],
                        values[component + "_heat_kwh"] * 60,
                        abs_tol=1e-9,
                    ),
                    "Thermal kW/kWh conversion failed",
                )
            for component in ["envelope", "ventilation"]:
                expected = (
                    values[component + "_ua_kw_k"]
                    * (out - values["mean_temperature_c"])
                    / 60
                )
                check(
                    math.isclose(
                        expected, values[component + "_heat_kwh"], abs_tol=1e-9
                    ),
                    "Integrated envelope or ventilation heat mismatch",
                )
            fixed = (
                values["people_heat_kw"]
                + values["other_heat_kw"]
                + values["hvac_thermal_power_kw"]
            )
            equilibrium = out + fixed / ua if ua else 0
            expected_end = (
                equilibrium + (start - equilibrium) * math.exp(-ua * 60 / cap)
                if ua
                else start + fixed * 60 / cap
            )
            check(
                math.isclose(end, expected_end, abs_tol=1e-8),
                "Analytical thermal update mismatch",
            )
            electric = values["hvac_electric_power_kw"]
            q = values["hvac_thermal_power_kw"]
            cop = values["cop"]
            check(
                electric >= 0 and math.isclose(abs(q), cop * electric, abs_tol=1e-9),
                "COP power coupling failed",
            )
            check(
                q == 0
                or math.isclose(
                    cop, rules["cooling_cop"] if q < 0 else rules["heating_cop"]
                ),
                "Thermal COP mode mismatch",
            )
            if rid in last:
                previous_t, previous_end = last[rid]
                check(
                    t - previous_t == timedelta(minutes=1),
                    "Thermal minute continuity failed",
                )
                check(
                    math.isclose(start, previous_end, abs_tol=1e-9),
                    "Thermal state continuity failed",
                )
            last[rid] = (t, end)
            maximum_temperature = max(maximum_temperature, start)
            if minute % step == 0:
                observed = next(truth, None)
                check(
                    observed is not None
                    and (observed["timestamp"], observed["room_id"]) == (stamp, rid),
                    "Thermal/truth key mismatch",
                )
                if observed:
                    check(
                        math.isclose(
                            float(observed["true_temperature_c"]), start, abs_tol=1e-9
                        ),
                        "Thermal start does not match truth",
                    )
                starts[rid] = stamp
            power_sum[rid] += electric / 60
            if (minute + 1) % step == 0:
                e = next(energy, None)
                check(
                    e is not None
                    and (e["timestamp"], e["room_id"]) == (starts[rid], rid),
                    "Thermal/energy block key mismatch",
                )
                if e and cfg["enable_energy_model"]:
                    check(
                        math.isclose(
                            power_sum[rid],
                            float(e["hvac_power_kw"]) * step / 60,
                            abs_tol=1e-9,
                        ),
                        "Electrical export differs from thermal input",
                    )
                power_sum[rid] = 0
            counts["thermal_rows"] += 1
        check(
            next(truth, None) is None and next(energy, None) is None,
            "Extra truth/energy samples",
        )
    check(
        counts["thermal_rows"] == cfg["days"] * 1440 * len(manifest["room_ids"]),
        "Thermal row count mismatch",
    )
    labeling = json.loads((run / "reports/labeling.json").read_text(encoding="utf-8"))
    check(labeling["status"] == "complete", "Labels not complete")
    recovery = defaultdict(list)
    causes = {e["event_id"]: e for e in read_csv(run / "truth/anomaly_events.csv")}
    for row in read_csv(run / "truth/recovery_events.csv"):
        cause = causes.get(row["cause_event_id"])
        a = datetime.fromisoformat(row["recovery_start_time"])
        b = datetime.fromisoformat(row["recovery_end_time"])
        check(
            cause is not None and cause["is_sensor_fault"] == "false",
            "Recovery attached to sensor or missing cause",
        )
        check(
            a >= datetime.fromisoformat(row["fault_end_time"]) and b >= a,
            "Recovery chronology invalid",
        )
        check(
            math.isclose((b - a).total_seconds() / 60, float(row["duration_minutes"])),
            "Recovery duration mismatch",
        )
        check(
            row["status"] in {"recovered", "right_censored", "interrupted_by_fault"},
            "Unknown recovery status",
        )
        recovery[row["room_id"]].append(row)
        counts["recovery_events"] += 1
        counts[row["status"]] += 1
    fault_lists = defaultdict(list)
    for cause in causes.values():
        fault_lists[cause["room_id"]].append(cause)
    for events in fault_lists.values():
        events.sort(key=lambda e: e["start_time"])
    fault_positions = defaultdict(int)
    for path in sorted((run / "truth/environment_status_1min").glob("*.csv")):
        day = path.stem[-10:]
        statuses = read_csv(path)
        truths = read_csv(
            run / f"truth/environment_truth_1min/environment_truth_{day}.csv"
        )
        for status, truth in zip(statuses, truths, strict=True):
            stamp = status["timestamp"]
            rid = status["room_id"]
            events = fault_lists[rid]
            idx = fault_positions[rid]
            while idx < len(events) and events[idx]["end_time"] <= stamp:
                idx += 1
            fault_positions[rid] = idx
            active = (
                events[idx]
                if idx < len(events)
                and events[idx]["start_time"] <= stamp < events[idx]["end_time"]
                else None
            )
            sensor_fault = active is not None and active["is_sensor_fault"] == "true"
            occupancy_fault = (
                active is not None and active["anomaly_type"] == "high_occupancy"
            )
            expected_flags = {
                "fault_active": active is not None,
                "sensor_fault_active": sensor_fault,
                "equipment_fault_active": active is not None
                and not sensor_fault
                and not occupancy_fault,
                "occupancy_fault_active": occupancy_fault,
            }
            for key, expected in expected_flags.items():
                check(
                    (status[key] == "true") == expected,
                    "Fault category status mismatch",
                )
            flags = []
            check(
                (stamp, rid) == (truth["timestamp"], truth["room_id"]),
                "Label/truth key mismatch",
            )
            for variable in ["temperature_c", "humidity_pct", "co2_ppm"]:
                val = float(truth["true_" + variable])
                outside = not bounds[variable]["min"] <= val <= bounds[variable]["max"]
                flags.append(outside)
                check(
                    (status[variable.split("_")[0] + "_anomaly_active"] == "true")
                    == outside,
                    "Environmental threshold label mismatch",
                )
            check(
                (status["environment_anomaly_active"] == "true") == any(flags),
                "Environmental union label mismatch",
            )
            check(
                (status["recovery_active"] == "true")
                == any(
                    e["recovery_start_time"] <= stamp < e["recovery_end_time"]
                    for e in recovery[rid]
                ),
                "Recovery status/event mismatch",
            )
            counts["label_rows"] += 1
            counts["environment_anomaly_rows"] += any(flags)
            counts["recovery_rows"] += status["recovery_active"] == "true"
    check(
        counts["label_rows"] == cfg["days"] * 1440 // step * len(manifest["room_ids"]),
        "Label row count mismatch",
    )
    return dict(
        valid=not errors,
        errors=errors,
        max_thermal_balance_residual_kwh=max_residual,
        net_thermal_balance_residual_kwh=total_residual,
        maximum_temperature_c=maximum_temperature,
        **counts,
    )

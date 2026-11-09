import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import pairwise, zip_longest
from zoneinfo import ZoneInfo

from ..catalog import catalog
from ..constants import SENSORS
from .writer import json_write, read_csv


def validate(run):
    manifest = json.loads((run / "reports/manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    errors = []
    warnings = []
    rooms = set(manifest["room_ids"])
    step = cfg["step_minutes"]

    def check(ok, message):
        if not ok and len(errors) < 100:
            errors.append(message)

    master = list(read_csv(run / "inputs/rooms.csv"))
    profiles = list(read_csv(run / "inputs/room_profiles.csv"))
    pmap = {p["room_id"]: p for p in profiles}
    check(
        len(master) == 63
        and {r["room_id"] for r in master} == {r["room_id"] for r in catalog()},
        "Master catalog does not match exact 63 rooms",
    )
    check(
        Counter(r["building_code"] for r in master)
        == {"STU": 38, "LIB": 12, "WON": 9, "HEA": 4},
        "Building counts invalid",
    )
    check(
        len(profiles) == 63 and set(pmap) == {r["room_id"] for r in master},
        "Profile IDs missing or duplicated",
    )
    check(
        Counter(p["room_type"] for p in profiles)
        == {"SMALL": 25, "MEDIUM": 28, "LARGE": 10},
        "Profile type counts invalid",
    )
    for p in profiles:
        check(
            int(p["capacity"]) > 0 and float(p["area_m2"]) > 0,
            "Nonpositive profile dimensions",
        )
        check(
            math.isclose(
                float(p["volume_m3"]),
                float(p["area_m2"]) * float(p["ceiling_height_m"]),
                abs_tol=1e-5,
            ),
            "Volume mismatch",
        )
    anomaly = defaultdict(list)
    for row in read_csv(run / "truth/anomaly_events.csv"):
        check(row["room_id"] in rooms, "Unknown anomaly room")
        check(row["start_time"] < row["end_time"], "Invalid anomaly interval")
        check(
            (row["is_sensor_fault"] == "true")
            == (row["anomaly_type"] in {"missing", "spike", "stuck", "bias"}),
            "Sensor/environment fault label mismatch",
        )
        anomaly[row["room_id"]].append(row)
    occupancy_events = {}
    previous_event = defaultdict(int)
    for row in read_csv(run / "events/occupancy_events.csv"):
        rid = row["room_id"]
        delta = int(row["count_delta"])
        value = int(row["resulting_occupancy"])
        check(
            value == previous_event[rid] + delta, "Occupancy event delta inconsistent"
        )
        check(
            0 <= value <= int(pmap[rid]["capacity"]), "Occupancy event exceeds capacity"
        )
        check(
            (row["timestamp"], rid) not in occupancy_events,
            "Duplicate occupancy event key",
        )
        occupancy_events[(row["timestamp"], rid)] = value
        previous_event[rid] = value
    # Only events are retained; raw datasets stream row-by-row.
    reservations = defaultdict(list)
    for r in read_csv(run / "events/reservations.csv"):
        reservations[r["room_id"]].append(r)
        t = datetime.fromisoformat(r["start_time"])
        end = datetime.fromisoformat(r["end_time"])
        p = pmap[r["room_id"]]
        check(
            r["created_at"] < r["start_time"] < r["end_time"],
            "Reservation chronology invalid",
        )
        check(
            p["opening_time"] <= t.strftime("%H:%M")
            and end.strftime("%H:%M") <= p["closing_time"]
            and t.date() == end.date(),
            "Reservation outside operating hours",
        )
        check(
            1 <= int(r["reserved_count"]) <= int(p["capacity"]),
            "Reservation capacity invalid",
        )
    for rid, rows in reservations.items():
        rows.sort(key=lambda r: r["start_time"])
        check(
            all(a["end_time"] <= b["start_time"] for a, b in pairwise(rows)),
            "Overlapping reservations",
        )
    start = datetime.fromisoformat(str(cfg["start_date"])).replace(
        tzinfo=ZoneInfo("Asia/Seoul")
    )
    last = {}
    occ = defaultdict(int)
    total_energy = 0
    count = 0
    abrupt = 0
    stuck_values = {}
    for path in sorted((run / "raw/sensors_1min").glob("*.csv")):
        date = path.stem[-10:]
        streams = [
            read_csv(path),
            read_csv(
                run / f"truth/environment_truth_1min/environment_truth_{date}.csv"
            ),
            read_csv(run / f"raw/energy_usage_1min/energy_usage_{date}.csv"),
            read_csv(run / f"raw/facility_states_1min/facility_states_{date}.csv"),
        ]
        daily = Counter()
        for bundle in zip_longest(*streams):
            if any(r is None for r in bundle):
                check(False, "Parallel dataset lengths differ")
                break
            s, t, e, _f = bundle
            rid = s["room_id"]
            stamp = s["timestamp"]
            time = datetime.fromisoformat(stamp)
            key = (stamp, rid)
            check(rid in rooms, "Unknown room in sensor data")
            check(
                all((r["timestamp"], r["room_id"]) == key for r in bundle),
                "Parallel dataset keys differ",
            )
            check(
                time.utcoffset() == timedelta(hours=9), "Timestamp missing Seoul offset"
            )
            expected = last[rid] + timedelta(minutes=step) if rid in last else start
            check(time == expected, "Duplicate or missing timestamp")
            if (
                rid in last
                and abs(
                    float(t["true_temperature_c"])
                    - last.get((rid, "temp"), float(t["true_temperature_c"]))
                )
                > 2
            ):
                abrupt += 1
            last[rid] = time
            last[(rid, "temp")] = float(t["true_temperature_c"])
            # Reconstruct all intervening minute events when output sampling is >1.
            for offset in range(step - 1, -1, -1):
                event_key = ((time - timedelta(minutes=offset)).isoformat(), rid)
                if event_key in occupancy_events:
                    occ[rid] = occupancy_events[event_key]
            check(
                occ[rid] == int(t["true_occupancy_count"]),
                "Occupancy events disagree with truth",
            )
            value = int(t["true_occupancy_count"])
            check(
                0 <= value <= int(pmap[rid]["capacity"]), "Truth occupancy out of range"
            )
            if not (
                pmap[rid]["opening_time"]
                <= time.strftime("%H:%M")
                < pmap[rid]["closing_time"]
            ):
                check(value == 0, "Occupied outside operating hours")
            check(
                0 <= float(t["true_humidity_pct"]) <= 100, "Truth humidity out of range"
            )
            check(
                float(t["true_co2_ppm"]) > 0 and float(t["true_illuminance_lux"]) >= 0,
                "Invalid physical truth",
            )
            active_faults = [
                a
                for a in anomaly[rid]
                if a["start_time"] <= stamp < a["end_time"]
                and a["is_sensor_fault"] == "true"
            ]
            for name in SENSORS:
                labelled = next(
                    (a for a in active_faults if a["affected_variable"] == name), None
                )
                if s[name] == "":
                    check(
                        any(
                            a["anomaly_type"] == "missing"
                            and a["affected_variable"] == name
                            and a["start_time"] <= stamp < a["end_time"]
                            for a in anomaly[rid]
                        ),
                        "Unlabelled sensor missingness",
                    )
                else:
                    check(math.isfinite(float(s[name])), "Nonfinite sensor reading")
                    tolerance = (
                        8 * cfg["rules"]["environment"]["sensor_noise"][name]
                        + cfg["rules"]["environment"]["sensor_resolution"][name]
                    )
                    if labelled is None:
                        check(
                            abs(float(s[name]) - float(t["true_" + name])) <= tolerance,
                            "Sensor deviation has no fault label (8 sigma audit)",
                        )
                    elif labelled["anomaly_type"] == "missing":
                        check(False, "Missing fault label has a nonmissing reading")
                    elif labelled["anomaly_type"] == "spike":
                        expected = (
                            float(t["true_" + name]) + cfg["rules"]["fault"]["spike"]
                        )
                        check(
                            abs(float(s[name]) - expected) <= tolerance,
                            "Spike does not match fault label",
                        )
                    elif labelled["anomaly_type"] == "bias":
                        elapsed = (
                            time - datetime.fromisoformat(labelled["start_time"])
                        ).total_seconds() / 60 + 1
                        expected = (
                            float(t["true_" + name])
                            + elapsed * cfg["rules"]["fault"]["bias_per_minute"]
                        )
                        check(
                            abs(float(s[name]) - expected) <= tolerance,
                            "Bias does not match fault label",
                        )
                    elif labelled["anomaly_type"] == "stuck":
                        stuck_key = (rid, labelled["event_id"])
                        if stuck_key not in stuck_values:
                            stuck_values[stuck_key] = float(s[name])
                        check(
                            float(s[name]) == stuck_values[stuck_key],
                            "Stuck sensor changed during fault",
                        )
            parts = sum(
                float(e[k])
                for k in (
                    "hvac_power_kw",
                    "ventilation_power_kw",
                    "lighting_power_kw",
                    "standby_power_kw",
                )
            )
            power = float(e["total_power_kw"])
            energy = float(e["interval_energy_kwh"])
            check(
                power >= 0 and energy >= 0 and math.isclose(parts, power, abs_tol=1e-8),
                "Power sum invalid",
            )
            check(
                math.isclose(energy, power * step / 60, abs_tol=1e-8),
                "Energy interval invalid",
            )
            total_energy += energy
            daily[rid] += 1
            count += 1
        check(
            dict(daily) == {rid: 1440 // step for rid in rooms},
            "Daily row count invalid",
        )
    expected = cfg["days"] * 1440 // step * len(rooms)
    check(count == expected, "Total sensor row count invalid")
    check(manifest["status"] == "complete", "Run is not complete")
    derived_count = 0
    derived_energy = 0
    ap = run / "reports/aggregation.json"
    if ap.exists():
        minutes = json.loads(ap.read_text(encoding="utf-8"))["minutes"]
        for path in (run / "derived/sensors_5min").glob("*.csv"):
            for row in read_csv(path):
                derived_count += 1
                check(
                    int(row["sample_count"]) == minutes // step,
                    "Aggregate sample count invalid",
                )
                check(
                    all(0 <= float(row[s + "_missing_ratio"]) <= 1 for s in SENSORS),
                    "Missing ratio invalid",
                )
        for path in (run / "derived/energy_5min").glob("*.csv"):
            for row in read_csv(path):
                derived_energy += float(row["interval_energy_kwh"])
        check(
            derived_count == cfg["days"] * 1440 // minutes * len(rooms),
            "Aggregate row count invalid",
        )
        check(
            math.isclose(total_energy, derived_energy, rel_tol=1e-9, abs_tol=1e-7),
            "Aggregate energy conservation failed",
        )
    else:
        warnings.append("Aggregation has not been generated")
    if abrupt:
        warnings.append(f"{abrupt} temperature jumps exceeded 2 C per output step")
    physics = None
    if manifest.get("software_version") == "0.2.0":
        from .physics_validator import validate_physics

        physics = validate_physics(run, manifest)
        errors.extend(physics["errors"])
    result = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "sensor_rows": count,
        "expected_sensor_rows": expected,
        "aggregate_rows": derived_count,
        "total_energy_kwh": total_energy,
    }
    if physics is not None:
        result["physics_and_labels"] = physics
    json_write(run / "reports/validation_report.json", result)
    return result

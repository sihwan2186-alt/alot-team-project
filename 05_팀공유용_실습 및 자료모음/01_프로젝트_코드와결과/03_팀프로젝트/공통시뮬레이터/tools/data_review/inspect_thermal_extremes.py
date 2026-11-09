"""Locate actual thermal extremes and decompose the implemented heat terms."""

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from aiot_sim.engines.external_environment import outdoor  # noqa: E402

run = ROOT / "data/runs/full-30d"


def rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


profiles = {p["room_id"]: p for p in rows(run / "inputs/room_profiles.csv")}
manifest = json.loads((run / "reports/manifest.json").read_text())
rules = manifest["config"]["rules"]["environment"]
maximum = None
groups = defaultdict(lambda: dict(occupied=0, outside_20_26=0, max_temperature_c=-999))
for path in sorted((run / "truth/environment_truth_1min").glob("*.csv")):
    for row in rows(path):
        temp = float(row["true_temperature_c"])
        kind = profiles[row["room_id"]]["room_type"]
        g = groups[kind]
        g["max_temperature_c"] = max(g["max_temperature_c"], temp)
        if int(row["true_occupancy_count"]) > 0:
            g["occupied"] += 1
            g["outside_20_26"] += not 20 <= temp <= 26
        if maximum is None or temp > float(maximum["true_temperature_c"]):
            maximum = row
key = maximum["timestamp"], maximum["room_id"]
day = key[0][:10]
profile = profiles[key[1]]
facility = next(
    r
    for r in rows(run / f"raw/facility_states_1min/facility_states_{day}.csv")
    if (r["timestamp"], r["room_id"]) == key
)
ext = outdoor(datetime.fromisoformat(key[0]), manifest["config"]["seed"], rules)
faults = [
    r
    for r in rows(run / "truth/anomaly_events.csv")
    if r["room_id"] == key[1] and r["start_time"] <= key[0] < r["end_time"]
]
when = datetime.fromisoformat(key[0])
context = {}
for folder, stem in [
    ("raw/facility_states_1min", "facility_states"),
    ("truth/environment_truth_1min", "environment_truth"),
]:
    context[folder] = [
        r
        for r in rows(run / f"{folder}/{stem}_{day}.csv")
        if r["room_id"] == key[1]
        and (when - timedelta(minutes=2)).isoformat()
        <= r["timestamp"]
        < (when + timedelta(minutes=2)).isoformat()
    ]
context["recent_faults"] = [
    r
    for r in rows(run / "truth/anomaly_events.csv")
    if r["room_id"] == key[1]
    and r["start_time"] < when.isoformat()
    and r["end_time"] > (when - timedelta(hours=1)).isoformat()
]
net_people = int(maximum["true_occupancy_count"]) * rules["occupant_heat_c_per_minute"]
result = dict(
    maximum_truth=maximum,
    profile=profile,
    facility_at_same_timestamp=facility,
    outdoor=ext,
    active_injected_faults=faults,
    by_type=dict(groups),
    preceding_interval_context=context,
    configured_people_heating_c_min=net_people,
    maximum_cooling_effect_c_min=-rules["hvac_c_per_minute"],
    maximum_occupancy_for_person_heating_not_exceeding_cooling=rules[
        "hvac_c_per_minute"
    ]
    / rules["occupant_heat_c_per_minute"],
    note="Current truth results from previous interval; same timestamp facility is the following interval. Thermostat targets are assumptions, not health limits.",
)
path = ROOT / "deliverables/data_review/thermal_extremes.json"
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))

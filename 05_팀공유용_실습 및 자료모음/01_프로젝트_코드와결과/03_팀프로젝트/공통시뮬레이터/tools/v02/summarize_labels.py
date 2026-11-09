import json
from collections import Counter, defaultdict

from compare_runs import ROOT, rows

run = ROOT / "data/runs/v02-full-30d"
groups = defaultdict(
    lambda: dict(
        rows=0, min_temperature_c=1e9, max_temperature_c=-1e9, sum_temperature_c=0.0
    )
)
flags = Counter()
for p in sorted((run / "truth/environment_status_1min").glob("*.csv")):
    day = p.stem[-10:]
    for status, truth in zip(
        rows(p),
        rows(run / f"truth/environment_truth_1min/environment_truth_{day}.csv"),
        strict=True,
    ):
        for key in (
            "fault_active",
            "sensor_fault_active",
            "equipment_fault_active",
            "occupancy_fault_active",
            "temperature_anomaly_active",
            "humidity_anomaly_active",
            "co2_anomaly_active",
            "environment_anomaly_active",
            "recovery_active",
        ):
            flags[key] += status[key] == "true"
        # Mutually exclusive categories, with recovery taking precedence after fault.
        category = (
            "fault_active"
            if status["fault_active"] == "true"
            else "recovery_without_fault"
            if status["recovery_active"] == "true"
            else "no_fault_or_recovery"
        )
        s = groups[category]
        t = float(truth["true_temperature_c"])
        s["rows"] += 1
        s["min_temperature_c"] = min(s["min_temperature_c"], t)
        s["max_temperature_c"] = max(s["max_temperature_c"], t)
        s["sum_temperature_c"] += t
for s in groups.values():
    s["mean_temperature_c"] = s.pop("sum_temperature_c") / s["rows"]
recovered = sorted(
    float(r["duration_minutes"])
    for r in rows(run / "truth/recovery_events.csv")
    if r["status"] == "recovered"
)
window = json.loads((ROOT / "deliverables/v0.2.0/extreme_window.json").read_text())
extreme = {}
for version, items in window.items():
    selected = {r["timestamp"][11:16]: float(r["true_temperature_c"]) for r in items}
    extreme[version] = dict(
        at_fault_start_c=selected["17:55"],
        at_fault_end_c=selected["18:29"],
        at_19_30_c=selected["19:30"],
        mean_fault_slope_c_min=(selected["18:29"] - selected["17:55"]) / 34,
    )
result = dict(
    flag_room_minutes=dict(flags),
    temperature_by_exclusive_status=dict(groups),
    recovered_duration_minutes=dict(
        n=len(recovered),
        min=min(recovered),
        median=(recovered[(len(recovered) - 1) // 2] + recovered[len(recovered) // 2])
        / 2,
        max=max(recovered),
    ),
    extreme_case=extreme,
    interpretation="No temperature threshold anomalies in this run; no temperature recovery events. Successful recovery durations are CO2 only, include stability confirmation, exclude interrupted events.",
)
(ROOT / "deliverables/v0.2.0/label_summary.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2)
)
print(json.dumps(result, ensure_ascii=False, indent=2))

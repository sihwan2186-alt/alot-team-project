import json

from compare_runs import ROOT, digest, rows

out = ROOT / "deliverables/v0.2.0"
old = (
    ROOT
    / "data/runs/full-30d/truth/environment_truth_1min/environment_truth_2026-09-14.csv"
)
replay = (
    ROOT
    / "data/runs/v01-extreme-replay/truth/environment_truth_1min/environment_truth_2026-09-14.csv"
)
a = [r for r in rows(old) if r["room_id"] == "STU-B131"]
b = list(rows(replay))
assert a == b
peak = max(a, key=lambda r: float(r["true_temperature_c"]))
x, y = [ROOT / "data/runs" / n for n in ("v02-smoke-single", "v02-repro-single")]
checks = {
    str(p.relative_to(x)): digest(p) == digest(y / p.relative_to(x))
    for p in x.rglob("*.csv")
}
assert checks and all(checks.values())
result = dict(
    baseline_extreme_replay=dict(identical_room_day_rows=len(a), peak=peak),
    v02_reproduction=dict(
        scope="one room, one day, same runtime/seed; all CSV outputs including labels/thermal/aggregates",
        identical_csv_files=len(checks),
        all_identical=True,
    ),
)
(out / "replay_verification.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2)
)
print(json.dumps(result, ensure_ascii=False, indent=2))

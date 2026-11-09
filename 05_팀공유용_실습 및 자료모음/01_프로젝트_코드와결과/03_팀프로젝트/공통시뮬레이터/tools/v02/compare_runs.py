"""Streaming before/after verification. No baseline files are modified."""

import csv
import hashlib
import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/v0.2.0"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def preservation():
    base = ROOT / "baselines/v0.1.0"
    m = json.loads((base / "baseline_snapshot.json").read_text())
    failures = []
    for rel, expected in m["snapshot_hashes"].items():
        if digest(base / rel) != expected:
            failures.append("snapshot:" + rel)
    for rel, expected in m["existing_dataset_hashes"].items():
        if digest(ROOT / rel) != expected:
            failures.append(rel)
    if (
        digest(
            ROOT / "deliverables/Smart_Campus_AIoT_Simulator_Technology_Overview.docx"
        )
        != m["white_paper_sha256"]
    ):
        failures.append("original white paper")
    return dict(
        valid=not failures,
        snapshot_files=len(m["snapshot_hashes"]),
        baseline_files=len(m["existing_dataset_hashes"]),
        failures=failures,
    )


def compare(old_name="full-30d", new_name="v02-full-30d"):
    old, new = [ROOT / "data/runs" / n for n in (old_name, new_name)]
    same = {
        rel: digest(old / rel) == digest(new / rel)
        for rel in (
            "inputs/rooms.csv",
            "inputs/room_profiles.csv",
            "events/reservations.csv",
            "events/occupancy_events.csv",
            "truth/anomaly_events.csv",
        )
    }
    stats = [
        {
            v: dict(min=float("inf"), max=-float("inf"), sum=0.0)
            for v in ("temperature_c", "humidity_pct", "co2_ppm")
        }
        for _ in range(2)
    ]
    counts = [Counter(), Counter()]
    peaks = [None, None]
    mismatches = Counter()
    for a in sorted((old / "truth/environment_truth_1min").glob("*.csv")):
        b = new / "truth/environment_truth_1min" / a.name
        for pair in zip_longest(rows(a), rows(b)):
            if None in pair:
                raise ValueError("Unequal truth row counts")
            for field in ("timestamp", "room_id", "true_occupancy_count"):
                if pair[0][field] != pair[1][field]:
                    mismatches[field] += 1
            for i, r in enumerate(pair):
                counts[i]["rows"] += 1
                occupied = int(r["true_occupancy_count"]) > 0
                counts[i]["occupied_rows"] += occupied
                t = float(r["true_temperature_c"])
                counts[i]["occupied_outside_20_26"] += occupied and not 20 <= t <= 26
                counts[i]["outside_18_28"] += not 18 <= t <= 28
                if peaks[i] is None or t > float(peaks[i]["true_temperature_c"]):
                    peaks[i] = r
                for v, s in stats[i].items():
                    x = float(r["true_" + v])
                    s["sum"] += x
                    s["min"], s["max"] = min(s["min"], x), max(s["max"], x)
    results = []
    for i, run in enumerate((old, new)):
        for s in stats[i].values():
            s["mean"] = s.pop("sum") / counts[i]["rows"]
        energy = sum(
            float(r["interval_energy_kwh"])
            for p in sorted((run / "raw/energy_usage_1min").glob("*.csv"))
            for r in rows(p)
        )
        results.append(
            dict(
                run_id=run.name,
                statistics=stats[i],
                counts=dict(counts[i]),
                maximum_temperature_row=peaks[i],
                total_energy_kwh=energy,
            )
        )
    recoveries = list(rows(new / "truth/recovery_events.csv"))
    recovery_summary = Counter(r["status"] for r in recoveries)
    by_variable = Counter((r["variable"], r["status"]) for r in recoveries)
    # Point-for-point replay window around the baseline extreme, with identical cause events.
    window = []
    for run in (old, new):
        window.append(
            [
                r
                for r in rows(
                    run
                    / "truth/environment_truth_1min/environment_truth_2026-09-14.csv"
                )
                if r["room_id"] == "STU-B131"
                and "T17:50" <= r["timestamp"][10:16] <= "T19:30"
            ]
        )
    result = dict(
        input_files_identical=same,
        truth_key_and_occupancy_mismatches=dict(mismatches),
        runs=results,
        recovery_status_counts=dict(recovery_summary),
        recovery_by_variable=[
            dict(variable=v, status=s, count=n)
            for (v, s), n in sorted(by_variable.items())
        ],
        preservation=preservation(),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    (OUT / "extreme_window.json").write_text(
        json.dumps(
            dict(baseline=window[0], v02=window[1]), ensure_ascii=False, indent=2
        )
    )
    assert all(same.values()) and not mismatches and result["preservation"]["valid"]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    compare()

"""Point-in-time, rule-based room candidates. No ML scores or truth features."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEVICES = ("monitor", "projector", "whiteboard", "outlets")
SENSOR_COLUMNS = (
    "temperature_c",
    "humidity_pct",
    "co2_ppm",
    "illuminance_lux",
    "noise_dba",
    "occupancy_count",
)


def read_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def aware_time(value: str) -> datetime:
    time = datetime.fromisoformat(value)
    if time.tzinfo is None or time.utcoffset() is None:
        raise ValueError("Time must contain a timezone offset, e.g. +09:00")
    return time.astimezone(ZoneInfo("Asia/Seoul"))


def candidates(
    run: Path,
    as_of: datetime,
    people: int,
    duration_minutes: int = 60,
    required: tuple[str, ...] = (),
    max_age_minutes: int = 2,
) -> dict:
    """Produce a complete per-room snapshot, with availability reduced before joining.

    Reservations are only visible at/after created_at. Half-open overlap is
    checked over the entire requested interval. Unobserved future readings and
    evaluation fields are never selected as features.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    as_of = as_of.astimezone(ZoneInfo("Asia/Seoul"))
    if people <= 0 or duration_minutes <= 0 or max_age_minutes < 0:
        raise ValueError("people/duration must be positive and max_age nonnegative")
    if set(required) - set(DEVICES):
        raise ValueError("Unknown required device")
    manifest = json.loads((run / "reports/manifest.json").read_text())
    if manifest["status"] != "complete":
        raise ValueError("Run is not complete")
    start = aware_time(str(manifest["config"]["start_date"]) + "T00:00:00+09:00")
    if not start <= as_of < start + timedelta(days=manifest["config"]["days"]):
        raise ValueError("as_of is outside the generated date range")
    end = as_of + timedelta(minutes=duration_minutes)
    # Use the run's snapshots, not master files potentially edited after generation.
    rooms = {r["room_id"]: r for r in read_rows(run / "inputs/rooms.csv")}
    profiles = {r["room_id"]: r for r in read_rows(run / "inputs/room_profiles.csv")}
    selected = set(manifest["room_ids"])
    latest = {}
    path = run / f"raw/sensors_1min/sensor_readings_{as_of.date()}.csv"
    for row in read_rows(path):
        stamp = aware_time(row["timestamp"])
        rid = row["room_id"]
        if (
            rid in selected
            and stamp <= as_of
            and (rid not in latest or stamp > aware_time(latest[rid]["timestamp"]))
        ):
            latest[rid] = row
    conflicts = set()
    visible_count = 0
    for reservation in read_rows(run / "events/reservations.csv"):
        # Do not consult is_no_show or actual future occupancy.
        if aware_time(reservation["created_at"]) > as_of:
            continue
        visible_count += 1
        if (
            reservation["status"] == "confirmed"
            and aware_time(reservation["start_time"]) < end
            and aware_time(reservation["end_time"]) > as_of
        ):
            conflicts.add(reservation["room_id"])
    output = []
    for rid in sorted(selected):
        room = rooms[rid]
        profile = profiles[rid]
        sensor = latest.get(rid)
        reasons = []
        opening = aware_time(f"{as_of.date()}T{profile['opening_time']}:00+09:00")
        closing = aware_time(f"{as_of.date()}T{profile['closing_time']}:00+09:00")
        if not opening <= as_of < end <= closing:
            reasons.append("outside_operating_hours")
        if int(profile["capacity"]) < people:
            reasons.append("insufficient_capacity")
        for device in required:
            if profile["has_" + device].lower() != "true":
                reasons.append("missing_" + device)
        if rid in conflicts:
            reasons.append("known_reservation_overlap")
        if sensor is None:
            reasons.append("no_available_observation")
        elif (
            as_of - aware_time(sensor["timestamp"])
        ).total_seconds() > max_age_minutes * 60:
            reasons.append("stale_observation")
        elif sensor["occupancy_count"] == "":
            reasons.append("unknown_occupancy")
        elif int(sensor["occupancy_count"]) != 0:
            reasons.append("currently_occupied")
        row = dict(
            room_id=rid,
            building_code=room["building_code"],
            building_name=room["building_name"],
            room_number=room["room_number"],
            room_type=profile["room_type"],
            capacity=int(profile["capacity"]),
            area_m2=float(profile["area_m2"]),
            opening_time=profile["opening_time"],
            closing_time=profile["closing_time"],
            profile_source=profile["profile_source"],
            sensor_timestamp=sensor["timestamp"] if sensor else None,
            known_reservation_conflict=rid in conflicts,
            eligible=not reasons,
            exclusion_reasons=reasons,
        )
        row.update(
            {
                f"has_{device}": profile[f"has_{device}"].lower() == "true"
                for device in DEVICES
            }
        )
        for name in SENSOR_COLUMNS:
            value = sensor[name] if sensor else ""
            row[name] = (
                None
                if value == ""
                else int(value)
                if name == "occupancy_count"
                else float(value)
            )
        output.append(row)
    return dict(
        scenario_id="2",
        method="rule_based_candidate_filter_not_ml",
        as_of=as_of.isoformat(),
        requested_end=end.isoformat(),
        people=people,
        required_devices=list(required),
        visible_reservations=visible_count,
        room_count=len(output),
        eligible_count=sum(r["eligible"] for r in output),
        data_warning="Synthetic profiles and sensors; not actual campus availability; eligible is not a booking guarantee.",
        rooms=output,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="full-30d")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--people", type=int, required=True)
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--require", choices=DEVICES, action="append", default=[])
    parser.add_argument("--max-age-minutes", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in {".", ".."}:
        parser.error("Invalid run ID")
    try:
        result = candidates(
            ROOT / "data/runs" / args.run_id,
            aware_time(args.as_of),
            args.people,
            args.duration_minutes,
            tuple(args.require),
            args.max_age_minutes,
        )
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "rooms"},
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in result["rooms"]:
        if row["eligible"]:
            print(
                row["room_id"],
                row["building_name"],
                row["capacity"],
                "명",
                row["sensor_timestamp"],
            )


if __name__ == "__main__":
    main()

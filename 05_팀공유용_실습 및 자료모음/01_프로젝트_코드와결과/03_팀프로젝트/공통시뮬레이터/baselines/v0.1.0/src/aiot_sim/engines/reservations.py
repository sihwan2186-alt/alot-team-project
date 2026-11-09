from dataclasses import asdict
from datetime import timedelta

from ..clock import parse_minutes
from ..random_utils import rng
from ..schemas import Reservation

FIELDS = list(Reservation.__dataclass_fields__)


def generate(profile, midnight, seed, rules):
    rid = profile["room_id"]
    r = rng(seed, rid, midnight.date(), "reservations")
    minute = parse_minutes(profile["opening_time"])
    closing = parse_minutes(profile["closing_time"])
    result = []
    probability = (
        rules["weekday_probability"]
        if midnight.weekday() < 5
        else rules["weekend_probability"]
    )
    while minute + min(rules["durations_minutes"]) <= closing:
        hour = minute // 60
        demand = rules["hourly_demand"].get(str((hour // 3) * 3), 0.8)
        if r.random() > probability * demand:
            minute += 30
            continue
        duration = r.choice(rules["durations_minutes"])
        if minute + duration > closing:
            break
        start = midnight + timedelta(minutes=minute)
        end = start + timedelta(minutes=duration)
        res = Reservation(
            f"R-{rid}-{start:%Y%m%d%H%M}",
            rid,
            (start - timedelta(hours=r.randint(*rules["lead_hours"]))).isoformat(),
            start.isoformat(),
            end.isoformat(),
            r.randint(1, profile["capacity"]),
            "cancelled"
            if r.random() < rules["cancellation_probability"]
            else "confirmed",
            r.random() < rules["no_show_probability"],
        )
        row = asdict(res)
        # Cancellation is decided at creation, never retrospectively rewritten.
        row["arrival_delay_minutes"] = r.randint(*rules["arrival_delay_minutes"])
        row["actual_count"] = max(1, res.reserved_count - r.randint(0, 2))
        result.append(row)
        minute += duration + r.choice([0, 15, 30])
    return result


def visible_reservations(reservations, as_of):
    return [r for r in reservations if r["created_at"] <= as_of.isoformat()]

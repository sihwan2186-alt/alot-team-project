from datetime import datetime, timedelta

from ..clock import minute_of_day, parse_minutes


def update(t, profile, reservations, current, random, rules, high_occupancy=False):
    active = next(
        (
            r
            for r in reservations
            if r["start_time"] <= t.isoformat() < r["end_time"]
            and r["status"] == "confirmed"
        ),
        None,
    )
    opened = (
        parse_minutes(profile["opening_time"])
        <= minute_of_day(t)
        < parse_minutes(profile["closing_time"])
    )
    target = current
    if not opened:
        target = 0
    elif active:
        arrival = datetime.fromisoformat(active["start_time"]) + timedelta(
            minutes=active["arrival_delay_minutes"]
        )
        target = (
            active["actual_count"] if not active["is_no_show"] and t >= arrival else 0
        )
    elif any(datetime.fromisoformat(r["end_time"]) == t for r in reservations):
        target = 0
    elif random.random() < rules["walk_in_probability"]:
        target = current + random.choice([-2, -1, 1, 2])
    if opened and high_occupancy:
        target = profile["capacity"]
    target = max(0, min(profile["capacity"], target))
    return target, active["reservation_id"] if active else ""

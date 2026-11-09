from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def timestamps(start_date, days=1, step_minutes=1, timezone="Asia/Seoul"):
    start = datetime.fromisoformat(str(start_date)).replace(tzinfo=ZoneInfo(timezone))
    for minute in range(0, days * 1440, step_minutes):
        yield start + timedelta(minutes=minute)


def minute_of_day(t):
    return t.hour * 60 + t.minute


def parse_minutes(value):
    h, m = map(int, value.split(":"))
    if not 0 <= h <= 23 or not 0 <= m < 60:
        raise ValueError("Invalid operating time: " + value)
    return h * 60 + m

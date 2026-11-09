from aiot_sim.clock import timestamps
from aiot_sim.engines.occupancy import update
from aiot_sim.engines.reservations import generate
from aiot_sim.random_utils import rng


def test_capacity_and_closed(profile, cfg):
    times = list(timestamps("2026-09-01"))
    rules = cfg["rules"]["occupancy"]
    schedule = generate(profile, times[0], cfg["seed"], rules)
    random = rng(12)
    count = 0
    for t in times:
        count, _ = update(t, profile, schedule, count, random, rules)
        assert 0 <= count <= profile["capacity"]
        if not 9 <= t.hour < 21:
            assert count == 0


def test_no_show_and_cancelled_do_not_enter(profile, cfg):
    from datetime import timedelta

    t = next(timestamps("2026-09-01")) + timedelta(hours=10)
    for status, no_show in [("confirmed", True), ("cancelled", False)]:
        booking = dict(
            reservation_id="R",
            start_time=t.isoformat(),
            end_time=(t + timedelta(hours=1)).isoformat(),
            status=status,
            is_no_show=no_show,
            arrival_delay_minutes=0,
            actual_count=4,
        )
        rules = dict(cfg["rules"]["occupancy"], walk_in_probability=0)
        assert update(t, profile, [booking], 0, rng(1), rules)[0] == 0

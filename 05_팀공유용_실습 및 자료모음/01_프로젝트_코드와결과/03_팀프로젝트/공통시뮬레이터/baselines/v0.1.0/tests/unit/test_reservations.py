import itertools

from aiot_sim.clock import timestamps
from aiot_sim.engines.reservations import generate, visible_reservations


def test_reservations(profile, cfg):
    for t in timestamps("2026-09-01", 30, 1440):
        rows = generate(profile, t, cfg["seed"], cfg["rules"]["occupancy"])
        assert all(
            a["end_time"] <= b["start_time"] for a, b in itertools.pairwise(rows)
        )
        for r in rows:
            assert r["created_at"] < r["start_time"] < r["end_time"]
            assert "09:00" <= r["start_time"][11:16] < r["end_time"][11:16] <= "21:00"
            assert 1 <= r["reserved_count"] <= profile["capacity"]
        assert all(
            r["created_at"] <= t.isoformat() for r in visible_reservations(rows, t)
        )

import math
from collections import Counter

from aiot_sim.catalog import catalog
from aiot_sim.profiles import generate, load


def test_profiles(project, cfg):
    rows = load(project)
    assert {p["room_id"] for p in rows} == {r["room_id"] for r in catalog()}
    assert Counter(p["room_type"] for p in rows) == {
        "SMALL": 25,
        "MEDIUM": 28,
        "LARGE": 10,
    }
    for p in rows:
        bounds = cfg["rules"]["room_profile"]["types"][p["room_type"]]
        assert p["capacity"] in bounds["capacities"]
        assert bounds["area"][0] <= p["area_m2"] <= bounds["area"][1]
        assert math.isclose(
            p["volume_m3"], p["area_m2"] * p["ceiling_height_m"], abs_tol=1e-5
        )
    before = (project / "data/master/room_profiles.csv").read_bytes()
    generate(project, cfg["rules"]["room_profile"])
    assert before == (project / "data/master/room_profiles.csv").read_bytes()


def test_exception(profile):
    assert (
        profile["capacity"],
        profile["area_m2"],
        profile["opening_time"],
        profile["closing_time"],
    ) == (6, 17, "09:00", "21:00")

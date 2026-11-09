from collections import Counter

from aiot_sim.catalog import catalog


def test_exact_catalog():
    rows = catalog()
    assert len(rows) == len({r["room_id"] for r in rows}) == 63
    assert Counter(r["building_code"] for r in rows) == {
        "STU": 38,
        "LIB": 12,
        "WON": 9,
        "HEA": 4,
    }
    assert all(r["floor_verified"] is False for r in rows)

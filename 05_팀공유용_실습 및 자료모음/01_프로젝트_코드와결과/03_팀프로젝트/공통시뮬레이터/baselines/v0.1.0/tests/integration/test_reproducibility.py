from aiot_sim.pipeline.aggregator import aggregate
from aiot_sim.pipeline.simulator import simulate


def test_reproducibility_and_room_order(project, cfg):
    cfg["room_ids"] = ["STU-B102A", "LIB-B101A"]
    a = simulate(project, cfg, "a")
    aggregate(a)
    cfg["room_ids"].reverse()
    b = simulate(project, cfg, "b")
    aggregate(b)
    for path in a.rglob("*.csv"):
        assert path.read_bytes() == (b / path.relative_to(a)).read_bytes(), path

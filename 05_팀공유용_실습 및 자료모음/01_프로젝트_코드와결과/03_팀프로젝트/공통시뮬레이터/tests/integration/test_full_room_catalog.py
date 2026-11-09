from aiot_sim.pipeline.aggregator import aggregate
from aiot_sim.pipeline.simulator import simulate
from aiot_sim.pipeline.validator import validate


def test_all_rooms_one_day(project, cfg):
    cfg["room_ids"] = []
    run = simulate(project, cfg, "all")
    assert aggregate(run) == 18144
    result = validate(run)
    assert result["valid"], result
    assert result["sensor_rows"] == 90720

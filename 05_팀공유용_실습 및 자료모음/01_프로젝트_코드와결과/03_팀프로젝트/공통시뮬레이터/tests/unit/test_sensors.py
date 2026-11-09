from aiot_sim.engines.sensors import observe
from aiot_sim.random_utils import rng
from aiot_sim.schemas import EnvironmentState, SensorFault


def test_fault_observations(cfg):
    state = EnvironmentState()
    rules = dict(cfg["rules"]["environment"], fault_spike=1200, fault_bias=4)
    for kind in ("missing", "stuck", "spike", "bias"):
        fault = SensorFault(kind, "co2_ppm", 0, 10, 500)
        row = observe(state, 3, rng(1), rules, fault, 3)
        if kind == "missing":
            assert row["co2_ppm"] is None
        if kind == "stuck":
            assert row["co2_ppm"] == 500
        if kind == "spike":
            assert row["co2_ppm"] > 1500
        if kind == "bias":
            assert row["co2_ppm"] > 425
        assert state.co2_ppm == 425

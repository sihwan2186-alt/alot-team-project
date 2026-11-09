from aiot_sim.pipeline.simulator import simulate
from aiot_sim.pipeline.writer import read_csv


def test_feedback_changes_physical_state(project, cfg):
    cfg["enable_faults"] = False
    a = simulate(project, cfg, "control")
    cfg["enable_control_feedback"] = False
    b = simulate(project, cfg, "uncontrolled")
    pa = next((a / "truth/environment_truth_1min").glob("*.csv"))
    pb = next((b / "truth/environment_truth_1min").glob("*.csv"))
    controlled = list(read_csv(pa))
    uncontrolled = list(read_csv(pb))
    assert controlled != uncontrolled
    assert any(
        r["true_temperature_c"] != s["true_temperature_c"]
        for r, s in zip(controlled, uncontrolled)
    )
    assert len(list(read_csv(a / "events/control_actions.csv"))) > 0


def test_controller_minimum_duration_and_missing(cfg):
    from aiot_sim.engines.controller import decide
    from aiot_sim.schemas import FacilityState

    state = FacilityState()
    obs = dict(temperature_c=30, co2_ppm=1500, illuminance_lux=0)
    state, changes = decide(obs, 5, state, 0, cfg["rules"]["facility"])
    assert state.hvac_on and state.ventilation_on and state.lighting_on
    blocked, changes = decide(obs, 0, state, 1, cfg["rules"]["facility"])
    assert blocked.hvac_on and changes == []
    missing = dict(temperature_c=None, co2_ppm=None, illuminance_lux=None)
    held, _ = decide(missing, 5, state, 10, cfg["rules"]["facility"])
    assert held.hvac_mode == state.hvac_mode
    stopped, _ = decide(obs, 0, state, 10, cfg["rules"]["facility"])
    assert not stopped.hvac_on

from copy import deepcopy

from aiot_sim.clock import timestamps
from aiot_sim.engines.environment import evolve, saturation_g_m3
from aiot_sim.engines.external_environment import outdoor
from aiot_sim.schemas import EnvironmentState, FacilityState


def test_environment_responses(profile, cfg):
    rules = cfg["rules"]["environment"]
    t = next(timestamps("2026-09-01"))
    out = outdoor(t, 1, rules)
    a = EnvironmentState(co2_ppm=1200)
    b = deepcopy(a)
    off = FacilityState()
    on = FacilityState(ventilation_on=True, ventilation_level=1)
    for _ in range(30):
        evolve(a, profile, off, out, 6, rules, facility_rules=cfg["rules"]["facility"])
        evolve(b, profile, on, out, 6, rules, facility_rules=cfg["rules"]["facility"])
    assert a.co2_ppm > 1200 and b.co2_ppm < a.co2_ppm
    a = EnvironmentState()
    b = deepcopy(a)
    evolve(a, profile, off, out, 0, rules, facility_rules=cfg["rules"]["facility"])
    evolve(
        b,
        profile,
        FacilityState(
            hvac_mode="cooling", hvac_on=True, lighting_on=True, lighting_level=1
        ),
        out,
        0,
        rules,
        facility_rules=cfg["rules"]["facility"],
    )
    assert b.temperature_c < a.temperature_c and b.illuminance_lux > a.illuminance_lux
    assert 0 <= a.humidity_pct <= 100
    assert saturation_g_m3(30) > saturation_g_m3(20)

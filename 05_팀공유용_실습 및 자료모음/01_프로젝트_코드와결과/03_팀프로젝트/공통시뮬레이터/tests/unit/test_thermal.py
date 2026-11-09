import math
from copy import deepcopy

import pytest

from aiot_sim.engines.energy import energy
from aiot_sim.engines.faults import apply_equipment
from aiot_sim.engines.thermal import step
from aiot_sim.schemas import FacilityState, SensorFault


@pytest.mark.parametrize("mode,direction", [("cooling", -1), ("heating", 1)])
def test_electrical_power_changes_thermal_response(profile, cfg, mode, direction):
    f = FacilityState(hvac_mode=mode, hvac_on=True)
    rule = cfg["rules"]["environment"]["thermal"]
    policy = cfg["rules"]["facility"]
    a = step(24, profile, f, 24, 4, rule, policy)
    p = deepcopy(profile)
    p["hvac_power_kw"] *= 2
    b = step(24, p, f, 24, 4, rule, policy)
    assert direction * (b.end_temperature_c - a.end_temperature_c) > 0
    assert math.isclose(b.hvac_thermal_power_kw, 2 * a.hvac_thermal_power_kw)
    assert math.isclose(
        a.hvac_electric_power_kw, energy(profile, f, policy)["hvac_power_kw"]
    )
    assert math.isclose(abs(a.hvac_heat_kwh), a.cop * a.hvac_electric_power_kw / 60)


def test_higher_cop_more_heat_same_electricity(profile, cfg):
    f = FacilityState(hvac_mode="cooling", hvac_on=True)
    rules = cfg["rules"]["environment"]["thermal"]
    a = step(26, profile, f, 30, 4, rules, cfg["rules"]["facility"])
    b = step(
        26,
        profile,
        f,
        30,
        4,
        dict(rules, cooling_cop=rules["cooling_cop"] * 2),
        cfg["rules"]["facility"],
    )
    assert a.hvac_electric_power_kw == b.hvac_electric_power_kw
    assert b.end_temperature_c < a.end_temperature_c


def test_higher_thermal_mass_slower_fault_warming(profile, cfg):
    f = FacilityState()
    r = cfg["rules"]["environment"]["thermal"]
    policy = cfg["rules"]["facility"]
    a = step(24, profile, f, 30, profile["capacity"], r, policy)
    b = step(
        24,
        profile,
        f,
        30,
        profile["capacity"],
        dict(r, effective_capacity_kj_m2_k=r["effective_capacity_kj_m2_k"] * 2),
        policy,
    )
    assert 24 < b.end_temperature_c < a.end_temperature_c


def test_hvac_failure_removes_thermal_and_electrical_output(profile, cfg):
    f = FacilityState(hvac_mode="cooling", hvac_on=True)
    apply_equipment(f, SensorFault("hvac_failure", "hvac", 0, 60))
    b = step(
        25,
        profile,
        f,
        30,
        6,
        cfg["rules"]["environment"]["thermal"],
        cfg["rules"]["facility"],
    )
    assert b.hvac_electric_power_kw == b.hvac_thermal_power_kw == 0
    assert b.end_temperature_c > 25
    assert energy(profile, f, cfg["rules"]["facility"])["hvac_power_kw"] == 0


def test_analytical_semigroup_and_energy_balance(profile, cfg):
    f = FacilityState(hvac_mode="cooling", hvac_on=True)
    r = cfg["rules"]["environment"]["thermal"]
    policy = cfg["rules"]["facility"]
    long = step(26, profile, f, 29, 6, r, policy, dt=20)
    temp = 26
    heat = 0
    for _ in range(20):
        b = step(temp, profile, f, 29, 6, r, policy)
        temp = b.end_temperature_c
        assert abs(b.balance_residual_kwh) < 1e-10
        heat += b.stored_heat_kwh
    assert math.isclose(long.end_temperature_c, temp, abs_tol=1e-10)
    assert math.isclose(long.stored_heat_kwh, heat, abs_tol=1e-10)


def test_zero_exchange_stable_and_no_temperature_clip(profile, cfg):
    p = dict(profile, ventilation_off_ach=0, standby_power_kw=0)
    r = dict(
        cfg["rules"]["environment"]["thermal"], envelope_ua_w_m2_k=0, other_heat_w_m2=0
    )
    b = step(45, p, FacilityState(), 24, 10, r, cfg["rules"]["facility"])
    assert b.end_temperature_c > 45
    assert math.isclose(b.stored_heat_kwh, b.people_heat_kwh, abs_tol=1e-10)


@pytest.mark.parametrize(
    "name", ["effective_capacity_kj_m2_k", "cooling_cop", "heating_cop"]
)
def test_invalid_thermal_configuration(project, name):
    from aiot_sim.config import load

    path = project / "configs/environment_rules.toml"
    text = path.read_text()
    import re

    path.write_text(re.sub(rf"^{name} = .*$", name + " = 0", text, flags=re.M))
    with pytest.raises(ValueError):
        load(project)

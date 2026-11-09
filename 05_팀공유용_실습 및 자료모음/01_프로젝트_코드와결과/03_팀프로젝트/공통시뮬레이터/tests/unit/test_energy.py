import math

from aiot_sim.engines.energy import energy
from aiot_sim.schemas import FacilityState


def test_energy(profile, cfg):
    state = FacilityState(
        hvac_on=True,
        ventilation_on=True,
        ventilation_level=1,
        lighting_on=True,
        lighting_level=1,
    )
    e = energy(profile, state, cfg["rules"]["facility"])
    assert math.isclose(
        e["total_power_kw"],
        sum(
            e[k]
            for k in (
                "hvac_power_kw",
                "ventilation_power_kw",
                "lighting_power_kw",
                "standby_power_kw",
            )
        ),
    )
    assert math.isclose(e["interval_energy_kwh"], e["total_power_kw"] / 60)

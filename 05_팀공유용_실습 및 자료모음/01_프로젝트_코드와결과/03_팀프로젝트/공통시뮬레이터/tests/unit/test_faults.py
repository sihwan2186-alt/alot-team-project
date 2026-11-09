from aiot_sim.engines.faults import SENSOR_KINDS, apply_equipment, maybe_start
from aiot_sim.random_utils import rng
from aiot_sim.schemas import EnvironmentState, FacilityState


def test_all_fault_types(cfg):
    for kind in cfg["rules"]["fault"]["weights"]:
        rules = dict(cfg["rules"]["fault"], probability_per_minute=1, weights={kind: 1})
        fault = maybe_start(rng(1), 0, EnvironmentState(), rules)
        assert fault.kind == kind and fault.end > fault.start
        facility = FacilityState(
            hvac_mode="cooling", hvac_on=True, ventilation_on=True, ventilation_level=1
        )
        apply_equipment(facility, fault)
        assert facility.equipment_fault_active == (
            kind in {"hvac_failure", "ventilation_failure"}
        )
        assert (kind in SENSOR_KINDS) == (fault.variable == "co2_ppm")

from ..schemas import SensorFault

SENSOR_KINDS = {"missing", "spike", "stuck", "bias"}


def maybe_start(random, minute, state, rules, enabled=True):
    if not enabled or random.random() >= rules["probability_per_minute"]:
        return None
    kind = random.choices(
        list(rules["weights"]), weights=list(rules["weights"].values())
    )[0]
    variable = (
        "co2_ppm"
        if kind in SENSOR_KINDS
        else {
            "ventilation_failure": "ventilation",
            "hvac_failure": "hvac",
            "high_occupancy": "occupancy_count",
        }[kind]
    )
    duration = 1 if kind == "spike" else random.randint(*rules["duration_minutes"])
    return SensorFault(
        kind, variable, minute, minute + duration, getattr(state, variable, None)
    )


def apply_equipment(facility, fault):
    facility.equipment_fault_active = bool(
        fault and fault.kind in {"ventilation_failure", "hvac_failure"}
    )
    if fault and fault.kind == "ventilation_failure":
        facility.ventilation_on = False
        facility.ventilation_level = 0.0
    if fault and fault.kind == "hvac_failure":
        facility.hvac_on = False
        facility.hvac_mode = "off"

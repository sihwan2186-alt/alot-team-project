from ..constants import SENSORS


def observe(state, occupancy, random, rules, fault=None, minute=0):
    result = {}
    for name in SENSORS:
        value = occupancy if name == "occupancy_count" else getattr(state, name)
        value += random.gauss(0, rules["sensor_noise"][name])
        resolution = rules["sensor_resolution"][name]
        value = round(round(value / resolution) * resolution, 6)
        if name in {"illuminance_lux", "noise_dba"}:
            value = max(0, value)
        result[name] = int(value) if name == "occupancy_count" else value
    if fault and fault.kind in {"missing", "spike", "stuck", "bias"}:
        name = fault.variable
        if fault.kind == "missing":
            result[name] = None
        elif fault.kind == "stuck":
            result[name] = fault.stuck_value
        elif fault.kind == "spike":
            result[name] += rules["fault_spike"]
        elif fault.kind == "bias":
            result[name] += (minute - fault.start + 1) * rules["fault_bias"]
    return result

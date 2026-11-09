from dataclasses import replace


def decide(observation, occupancy, current, minute, rules):
    """Use observations only; return commands to be applied at the next interval."""
    new = replace(current, last_changes=dict(current.last_changes))
    changes = []
    temp = observation["temperature_c"]
    co2 = observation["co2_ppm"]
    lux = observation["illuminance_lux"]
    mode = current.hvac_mode
    if not occupancy:
        mode = "off"
    elif temp is not None:
        if temp > rules["cooling_on_c"]:
            mode = "cooling"
        elif temp < rules["heating_on_c"]:
            mode = "heating"
        elif (
            mode == "cooling"
            and temp < rules["cooling_off_c"]
            or mode == "heating"
            and temp > rules["heating_off_c"]
        ):
            mode = "off"
    vent = current.ventilation_on
    if not occupancy:
        vent = False
    elif co2 is not None:
        if co2 > rules["ventilation_on_ppm"]:
            vent = True
        elif co2 < rules["ventilation_off_ppm"]:
            vent = False
    light = current.lighting_on
    if not occupancy:
        light = False
    elif lux is not None:
        if lux < rules["lighting_target_lux"]:
            light = True
        elif (
            lux
            > rules["lighting_target_lux"]
            + rules["lighting_hysteresis_lux"]
            + 450 * current.lighting_level
        ):
            light = False
    for device, value, old in [
        ("hvac", mode, current.hvac_mode),
        ("ventilation", vent, current.ventilation_on),
        ("lighting", light, current.lighting_on),
    ]:
        if (
            value != old
            and minute - current.last_changes.get(device, -10000)
            >= rules["minimum_run_minutes"]
        ):
            changes.append((device, old, value))
            new.last_changes[device] = minute
            if device == "hvac":
                new.hvac_mode = value
                new.hvac_on = value != "off"
            elif device == "ventilation":
                new.ventilation_on = value
                new.ventilation_level = float(value)
            else:
                new.lighting_on = value
                new.lighting_level = float(value)
    return new, changes

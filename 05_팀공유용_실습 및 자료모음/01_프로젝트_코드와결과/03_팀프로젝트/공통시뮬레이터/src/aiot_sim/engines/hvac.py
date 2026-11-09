"""A single source of truth for electrical input and signed thermal output."""


def electrical_power_kw(profile, facility, facility_rules):
    if not facility.hvac_on or facility.hvac_mode == "off":
        return 0.0
    return profile["hvac_power_kw"] * facility_rules["hvac_power_fraction"]


def thermal_power_kw(profile, facility, facility_rules, thermal_rules):
    electric = electrical_power_kw(profile, facility, facility_rules)
    if not electric:
        return 0.0, 0.0, 0.0
    if facility.hvac_mode == "cooling":
        cop = thermal_rules["cooling_cop"]
        return electric, -cop * electric, cop
    if facility.hvac_mode == "heating":
        cop = thermal_rules["heating_cop"]
        return electric, cop * electric, cop
    raise ValueError(f"Unknown HVAC mode: {facility.hvac_mode}")

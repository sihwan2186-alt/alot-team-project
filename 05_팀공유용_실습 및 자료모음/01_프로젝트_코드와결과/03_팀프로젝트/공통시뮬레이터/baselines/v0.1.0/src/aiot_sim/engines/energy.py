def energy(profile, facility, rules, dt=1, enabled=True):
    components = {
        "hvac_power_kw": profile["hvac_power_kw"]
        * rules["hvac_power_fraction"]
        * facility.hvac_on,
        "ventilation_power_kw": profile["ventilation_power_kw"]
        * facility.ventilation_level,
        "lighting_power_kw": profile["lighting_power_kw"] * facility.lighting_level,
        "standby_power_kw": profile["standby_power_kw"],
    }
    if not enabled:
        components = {k: 0.0 for k in components}
    total = sum(components.values())
    return dict(**components, total_power_kw=total, interval_energy_kwh=total * dt / 60)

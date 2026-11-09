from .hvac import electrical_power_kw


def energy(profile, facility, rules, dt=1, enabled=True):
    components = {
        "hvac_power_kw": electrical_power_kw(profile, facility, rules),
        "ventilation_power_kw": profile["ventilation_power_kw"]
        * facility.ventilation_level,
        "lighting_power_kw": profile["lighting_power_kw"] * facility.lighting_level,
        "standby_power_kw": profile["standby_power_kw"],
    }
    if not enabled:
        components = {k: 0.0 for k in components}
    total = sum(components.values())
    return dict(**components, total_power_kw=total, interval_energy_kwh=total * dt / 60)

import math

from .hvac import temperature_effect
from .lighting import illuminance
from .noise import noise
from .ventilation import air_changes


def saturation_g_m3(temp):
    return 216.7 * (6.112 * math.exp(17.67 * temp / (temp + 243.5))) / (273.15 + temp)


def evolve(state, profile, facility, outdoor, occupancy, rules, dt=1, activity=1.0):
    ach = air_changes(profile, facility)
    decay = math.exp(-ach * dt / 60)
    source = occupancy * rules["co2_m3_per_person_hour"] * 1e6 / profile["volume_m3"]
    state.co2_ppm = (
        outdoor["outdoor_co2_ppm"]
        + (state.co2_ppm - outdoor["outdoor_co2_ppm"]) * decay
        + source * (-math.expm1(-ach * dt / 60)) / ach
        if ach > 1e-9
        else state.co2_ppm + source * dt / 60
    )
    state.temperature_c += dt * (
        profile["thermal_response_factor"]
        * (outdoor["outdoor_temperature_c"] - state.temperature_c)
        + occupancy * rules["occupant_heat_c_per_minute"]
        + temperature_effect(facility.hvac_mode, rules)
    )
    outdoor_abs = (
        saturation_g_m3(outdoor["outdoor_temperature_c"])
        * outdoor["outdoor_humidity_pct"]
        / 100
    )
    state.absolute_humidity_g_m3 = (
        outdoor_abs
        + (state.absolute_humidity_g_m3 - outdoor_abs) * decay
        + occupancy * rules["moisture_g_per_person_minute"] * dt / profile["volume_m3"]
    )
    if facility.hvac_mode == "cooling":
        state.absolute_humidity_g_m3 *= math.exp(-0.002 * dt)
    state.absolute_humidity_g_m3 = min(
        saturation_g_m3(state.temperature_c), max(0, state.absolute_humidity_g_m3)
    )
    state.humidity_pct = (
        100 * state.absolute_humidity_g_m3 / saturation_g_m3(state.temperature_c)
    )
    state.illuminance_lux = illuminance(profile, outdoor, facility, rules)
    state.noise_dba = noise(
        profile, occupancy, outdoor["outdoor_noise_dba"], facility, activity
    )
    return state

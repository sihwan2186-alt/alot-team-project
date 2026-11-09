"""One-zone, constant-input analytical heat balance; all coefficients are assumptions."""

import math
from dataclasses import asdict, dataclass

from .hvac import thermal_power_kw
from .ventilation import air_changes


@dataclass
class ThermalBalance:
    outdoor_temperature_c: float
    mean_temperature_c: float
    start_temperature_c: float
    end_temperature_c: float
    effective_heat_capacity_kj_k: float
    envelope_ua_kw_k: float
    ventilation_ua_kw_k: float
    people_heat_kw: float
    other_heat_kw: float
    hvac_electric_power_kw: float
    hvac_thermal_power_kw: float
    cop: float
    envelope_heat_kwh: float
    ventilation_heat_kwh: float
    people_heat_kwh: float
    other_heat_kwh: float
    hvac_heat_kwh: float
    stored_heat_kwh: float
    balance_residual_kwh: float

    def as_dict(self):
        return asdict(self)


def step(
    temperature,
    profile,
    facility,
    outdoor_temperature,
    occupancy,
    rules,
    facility_rules,
    dt=1,
):
    """C[kJ/K] dT/ds = UA[kW/K](Tout-T) + Q[kW]. No temperature clipping."""
    if dt <= 0:
        raise ValueError("Thermal timestep must be positive")
    air_capacity = (
        rules["air_density_kg_m3"]
        * profile["volume_m3"]
        * rules["air_specific_heat_kj_kg_k"]
    )
    capacity = profile["area_m2"] * rules["effective_capacity_kj_m2_k"] + air_capacity
    envelope = profile["area_m2"] * rules["envelope_ua_w_m2_k"] / 1000
    ventilation = air_capacity * air_changes(profile, facility) / 3600
    ua = envelope + ventilation
    people = occupancy * rules["people_sensible_heat_w"] / 1000
    electric, hvac, cop = thermal_power_kw(profile, facility, facility_rules, rules)
    other = (
        profile["area_m2"] * rules["other_heat_w_m2"] / 1000
        + profile["lighting_power_kw"]
        * facility.lighting_level
        * rules["lighting_heat_fraction"]
        + profile["standby_power_kw"] * rules["standby_heat_fraction"]
    )
    fixed = people + hvac + other
    seconds = dt * 60
    hours = dt / 60
    if ua > 0:
        x = ua * seconds / capacity
        decay_average = -math.expm1(-x) / x
        # Stable mean temperature for integrating the envelope/ventilation heat flow.
        one_minus_average = (
            1 - decay_average if x > 1e-7 else x / 2 - x * x / 6 + x * x * x / 24
        )
        end = temperature + (outdoor_temperature - temperature + fixed / ua) * (
            -math.expm1(-x)
        )
        mean = (
            outdoor_temperature
            + (temperature - outdoor_temperature) * decay_average
            + fixed / ua * one_minus_average
        )
    else:
        end = temperature + fixed * seconds / capacity
        mean = (temperature + end) / 2
    envelope_energy = envelope * (outdoor_temperature - mean) * hours
    ventilation_energy = ventilation * (outdoor_temperature - mean) * hours
    people_energy = people * hours
    other_energy = other * hours
    hvac_energy = hvac * hours
    stored = capacity * (end - temperature) / 3600
    residual = stored - (
        envelope_energy
        + ventilation_energy
        + people_energy
        + other_energy
        + hvac_energy
    )
    return ThermalBalance(
        outdoor_temperature,
        mean,
        temperature,
        end,
        capacity,
        envelope,
        ventilation,
        people,
        other,
        electric,
        hvac,
        cop,
        envelope_energy,
        ventilation_energy,
        people_energy,
        other_energy,
        hvac_energy,
        stored,
        residual,
    )

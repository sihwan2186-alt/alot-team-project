def illuminance(profile, outdoor, facility, rules):
    return (
        rules["daylight_lux"]
        * outdoor["daylight_factor"]
        * profile["daylight_exposure_factor"]
        + rules["lighting_lux"] * facility.lighting_level
    )

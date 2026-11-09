def air_changes(profile, facility):
    return (
        profile["ventilation_off_ach"]
        + (profile["ventilation_on_ach"] - profile["ventilation_off_ach"])
        * facility.ventilation_level
    )

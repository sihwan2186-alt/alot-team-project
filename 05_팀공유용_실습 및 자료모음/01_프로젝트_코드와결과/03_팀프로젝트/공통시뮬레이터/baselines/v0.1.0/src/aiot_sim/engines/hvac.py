def temperature_effect(mode, rules):
    return {
        "off": 0.0,
        "cooling": -rules["hvac_c_per_minute"],
        "heating": rules["hvac_c_per_minute"],
    }[mode]

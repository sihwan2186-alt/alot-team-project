import math


def combine(levels):
    return 10 * math.log10(sum(10 ** (x / 10) for x in levels))


def noise(profile, occupancy, outdoor_noise, facility, activity=1.0):
    levels = [profile["noise_baseline_dba"], outdoor_noise - 25]
    if occupancy:
        levels.append(36 + 10 * math.log10(occupancy) + activity * 4)
    if facility.ventilation_on:
        levels.append(33)
    if facility.hvac_on:
        levels.append(35)
    return combine(levels)

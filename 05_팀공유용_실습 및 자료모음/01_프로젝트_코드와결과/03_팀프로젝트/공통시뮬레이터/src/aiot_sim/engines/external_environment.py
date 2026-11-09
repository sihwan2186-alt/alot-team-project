import math

from ..random_utils import rng
from .noise import combine


def outdoor(t, seed, rules):
    r = rng(seed, t.date(), "weather")
    day_shift = r.uniform(-2, 2)
    phase = 2 * math.pi * (t.hour + t.minute / 60 - 9) / 24
    daylight = max(0, math.sin(math.pi * (t.hour + t.minute / 60 - 6) / 12))
    return {
        "outdoor_temperature_c": rules["outdoor_mean_c"]
        + day_shift
        + rules["outdoor_amplitude_c"] * math.sin(phase),
        "outdoor_humidity_pct": max(
            10, min(95, rules["outdoor_humidity_pct"] - 12 * math.sin(phase))
        ),
        "outdoor_co2_ppm": rules["outdoor_co2_ppm"],
        "daylight_factor": daylight,
        "outdoor_noise_dba": combine(
            [
                rules["outdoor_noise_dba"] - 10,
                rules["outdoor_noise_dba"] if 8 <= t.hour < 20 else 30,
            ]
        ),
    }

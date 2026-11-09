import tomllib
from datetime import date
from pathlib import Path

from .clock import parse_minutes


def read_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def load(root, overrides=None):
    root = Path(root)
    cfg = read_toml(root / "configs/simulation.toml")
    cfg.update({k: v for k, v in (overrides or {}).items() if v is not None})
    date.fromisoformat(str(cfg["start_date"]))
    if type(cfg["days"]) is not int or cfg["days"] <= 0:
        raise ValueError("days must be a positive integer")
    if (
        type(cfg["step_minutes"]) is not int
        or cfg["step_minutes"] <= 0
        or 1440 % cfg["step_minutes"]
    ):
        raise ValueError("step_minutes must be a positive divisor of 1440")
    if (
        type(cfg["aggregate_minutes"]) is not int
        or cfg["aggregate_minutes"] <= 0
        or 1440 % cfg["aggregate_minutes"]
        or cfg["aggregate_minutes"] % cfg["step_minutes"]
    ):
        raise ValueError(
            "aggregate_minutes must divide 1440 and be a multiple of step_minutes"
        )
    if cfg["timezone"] != "Asia/Seoul":
        raise ValueError("Only Asia/Seoul is supported")
    if not cfg["output_by_day"]:
        raise ValueError("output_by_day must be true")
    cfg["rules"] = {
        name: read_toml(root / f"configs/{name}_rules.toml")
        for name in (
            "room_profile",
            "environment",
            "occupancy",
            "fault",
            "facility",
            "anomaly_label",
        )
    }
    p = cfg["rules"]["room_profile"]
    if sum(t["count"] for t in p["types"].values()) != 63:
        raise ValueError("Room type counts must total 63")
    for name in (
        "weekday_probability",
        "weekend_probability",
        "no_show_probability",
        "cancellation_probability",
        "walk_in_probability",
    ):
        if not 0 <= cfg["rules"]["occupancy"][name] <= 1:
            raise ValueError(f"Invalid probability: {name}")
    for v in [p, *p.get("overrides", {}).values()]:
        opening = v.get("opening_time", p["opening_time"])
        closing = v.get("closing_time", p["closing_time"])
        if parse_minutes(opening) >= parse_minutes(closing):
            raise ValueError("opening_time must precede closing_time")
    if type(cfg["seed"]) is not int:
        raise ValueError("seed must be an integer")
    for name in ("enable_faults", "enable_energy_model", "enable_control_feedback"):
        if type(cfg[name]) is not bool:
            raise ValueError(f"{name} must be boolean")
    fault = cfg["rules"]["fault"]
    if (
        not 0 <= fault["probability_per_minute"] <= 1
        or any(v < 0 for v in fault["weights"].values())
        or sum(fault["weights"].values()) <= 0
    ):
        raise ValueError("Invalid fault probability or weights")
    for name in ("sensor_noise", "sensor_resolution"):
        for variable, value in cfg["rules"]["environment"][name].items():
            if value < 0 or (name == "sensor_resolution" and value == 0):
                raise ValueError(f"Invalid {name}.{variable}")
    for key, value in p.items():
        if isinstance(value, list) and (len(value) != 2 or value[0] > value[1]):
            raise ValueError(f"Invalid profile range: {key}")
    if (
        fault["duration_minutes"][0] < 1
        or fault["duration_minutes"][0] > fault["duration_minutes"][1]
    ):
        raise ValueError("Invalid fault duration")
    if cfg["rules"]["facility"]["minimum_run_minutes"] < 0:
        raise ValueError("Invalid minimum run duration")
    thermal = cfg["rules"]["environment"]["thermal"]
    import math

    for name in (
        "effective_capacity_kj_m2_k",
        "cooling_cop",
        "heating_cop",
        "air_density_kg_m3",
        "air_specific_heat_kj_kg_k",
    ):
        value = thermal[name]
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be finite and positive")
    for name in ("envelope_ua_w_m2_k", "people_sensible_heat_w", "other_heat_w_m2"):
        if not math.isfinite(thermal[name]) or thermal[name] < 0:
            raise ValueError(f"{name} must be nonnegative")
    for name in ("lighting_heat_fraction", "standby_heat_fraction"):
        if not 0 <= thermal[name] <= 1:
            raise ValueError(f"Invalid {name}")
    if not 0 <= cfg["rules"]["facility"]["hvac_power_fraction"] <= 1:
        raise ValueError("Invalid HVAC power fraction")
    labels = cfg["rules"]["anomaly_label"]
    if (
        type(labels["recovery_stable_minutes"]) is not int
        or labels["recovery_stable_minutes"] < 1
    ):
        raise ValueError("Recovery stabilization must be positive")
    for name in ("temperature_c", "humidity_pct", "co2_ppm"):
        if not labels[name]["min"] < labels[name]["max"]:
            raise ValueError(f"Invalid label bounds for {name}")
    return cfg

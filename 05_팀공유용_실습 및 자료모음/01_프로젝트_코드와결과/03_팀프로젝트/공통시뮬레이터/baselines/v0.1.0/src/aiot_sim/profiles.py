from .catalog import catalog
from .pipeline.writer import read_csv, write_csv
from .random_utils import rng

FLOATS = [
    "area_m2",
    "ceiling_height_m",
    "volume_m3",
    "ventilation_off_ach",
    "ventilation_on_ach",
    "hvac_power_kw",
    "ventilation_power_kw",
    "lighting_power_kw",
    "standby_power_kw",
    "noise_baseline_dba",
    "thermal_response_factor",
    "daylight_exposure_factor",
]
BOOLS = ["has_monitor", "has_projector", "has_whiteboard", "has_outlets"]


def generate(root, rules):
    path = root / "data/master/room_profiles.csv"
    if path.exists():
        return load(root)  # Existing profiles are deliberately immutable.
    ids = sorted(r["room_id"] for r in catalog() if r["room_id"] != "STU-B102A")
    random = rng(rules["seed"], "profile-types")
    random.shuffle(ids)
    types = [
        t for t, r in rules["types"].items() for _ in range(r["count"] - (t == "SMALL"))
    ]
    assigned = dict(zip(ids, types))
    assigned["STU-B102A"] = "SMALL"
    rows = []
    for rid in sorted(assigned):
        r = rng(rules["seed"], rid, "profile")
        kind = assigned[rid]
        rule = rules["types"][kind]
        capacity = r.choice(rule["capacities"])
        # Upper capacity gets upper area band; slight room-specific variation.
        rank = rule["capacities"].index(capacity) / (len(rule["capacities"]) - 1)
        lo, hi = rule["area"]
        area = round(lo + (hi - lo) * (0.15 + 0.7 * rank + r.uniform(-0.1, 0.1)), 2)
        if rid == "STU-B102A":
            capacity, area = 6, 17.0
        height = round(r.uniform(*rules["ceiling_height_m"]), 3)
        row = {
            "room_id": rid,
            "room_type": kind,
            "capacity": capacity,
            "area_m2": area,
            "ceiling_height_m": height,
            "volume_m3": round(area * height, 6),
        }
        row.update(
            {
                f"has_{device}": r.random() < rule[f"{device}_probability"]
                for device in ("monitor", "projector", "whiteboard")
            }
        )
        row.update(
            has_outlets=True,
            opening_time=rules["opening_time"],
            closing_time=rules["closing_time"],
        )
        row.update({k: round(r.uniform(*rules[k]), 6) for k in FLOATS[3:]})
        row.update(profile_source="synthetic_assumption", profile_version="v0.1")
        row.update(rules.get("overrides", {}).get(rid, {}))
        if rid == "STU-B102A":
            row.update(
                capacity=6, area_m2=17.0, opening_time="09:00", closing_time="21:00"
            )
        row["volume_m3"] = round(row["area_m2"] * row["ceiling_height_m"], 6)
        rows.append(row)
    write_csv(path, rows)
    return rows


def load(root):
    rows = list(read_csv(root / "data/master/room_profiles.csv"))
    for row in rows:
        row["capacity"] = int(row["capacity"])
        for k in FLOATS:
            row[k] = float(row[k])
        for k in BOOLS:
            row[k] = row[k].lower() == "true"
    return rows

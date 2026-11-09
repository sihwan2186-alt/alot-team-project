"""Controlled one-minute experiment; not a new campus calibration."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aiot_sim.config import load  # noqa: E402
from aiot_sim.engines.energy import energy  # noqa: E402
from aiot_sim.engines.thermal import step  # noqa: E402
from aiot_sim.profiles import load as load_profiles  # noqa: E402
from aiot_sim.schemas import FacilityState  # noqa: E402

root = Path(__file__).resolve().parents[2]
cfg = load(root)
p = next(p for p in load_profiles(root) if p["room_id"] == "STU-B102A")
results = []
for mode in ("cooling", "heating"):
    f = FacilityState(hvac_mode=mode, hvac_on=True)
    for multiplier in (0, 1, 2, 10):
        profile = dict(p, hvac_power_kw=p["hvac_power_kw"] * multiplier)
        b = step(
            24,
            profile,
            f,
            24,
            4,
            cfg["rules"]["environment"]["thermal"],
            cfg["rules"]["facility"],
        )
        electric = energy(profile, f, cfg["rules"]["facility"])["hvac_power_kw"]
        assert electric == b.hvac_electric_power_kw
        results.append(
            dict(
                mode=mode,
                power_multiplier=multiplier,
                hvac_electric_kw=electric,
                hvac_thermal_kw=b.hvac_thermal_power_kw,
                end_temperature_c=b.end_temperature_c,
                balance_residual_kwh=b.balance_residual_kwh,
            )
        )
out = dict(
    scope="STU-B102A, fixed indoor/outdoor 24 C initially, 4 people, one-minute constant inputs; only HVAC rated power changes",
    results=results,
)
(root / "deliverables/v0.2.0/power_experiment.json").write_text(
    json.dumps(out, indent=2)
)
print(json.dumps(out, indent=2))

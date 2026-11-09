"""Run with archived v0.1 modules, never the current root package."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "baselines/v0.1.0"
sys.path.insert(0, str(BASE / "src"))
from aiot_sim.config import load  # noqa: E402
from aiot_sim.pipeline.simulator import simulate  # noqa: E402

cfg = load(
    BASE, {"days": 14, "room_ids": ["STU-B131"], "output_path": str(ROOT / "data/runs")}
)
print(simulate(BASE, cfg, "v01-extreme-replay"))

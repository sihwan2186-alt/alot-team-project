"""Run a fresh single-room smoke dataset; existing runs are never overwritten."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
run_id = sys.argv[1] if len(sys.argv) > 1 else "script-smoke"
for args in (
    ["simulate", "--room-id", "STU-B102A", "--days", "1", "--run-id", run_id],
    ["aggregate", "--run-id", run_id],
    ["validate", "--run-id", run_id],
    ["report", "--run-id", run_id],
):
    subprocess.run([sys.executable, "-m", "aiot_sim", *args], cwd=root, check=True)

"""Print actual per-file counts and sizes without loading a complete dataset."""

import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
args = parser.parse_args()
subprocess.run(
    [sys.executable, "-m", "aiot_sim", "report", "--run-id", args.run_id],
    cwd=Path(__file__).resolve().parents[1],
    check=True,
)

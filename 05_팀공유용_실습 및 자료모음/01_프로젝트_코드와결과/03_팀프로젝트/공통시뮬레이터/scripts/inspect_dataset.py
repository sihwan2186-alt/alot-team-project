"""Print actual per-file counts and sizes without loading a complete dataset."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
environment = os.environ.copy()
environment["PYTHONPATH"] = os.pathsep.join(
    filter(None, (str(root / "src"), environment.get("PYTHONPATH")))
)
subprocess.run(
    [
        sys.executable, "-m", "aiot_sim", "--root", str(root),
        "report", "--run-id", args.run_id,
    ],
    cwd=root,
    env=environment,
    check=True,
)

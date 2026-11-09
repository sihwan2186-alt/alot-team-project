"""Exercise the standalone CSV reproducibility checker from an arbitrary cwd."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_reproducibility.py"


def compare(first, second, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(first), str(second), *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_missing_or_empty_datasets_are_not_identical(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    assert compare(first, second).returncode == 2
    first.mkdir()
    second.mkdir()
    assert compare(first, second).returncode == 2


def test_csv_comparison_and_utf8_output(tmp_path):
    first, second = tmp_path / "첫째", tmp_path / "둘째"
    for dataset in (first, second):
        dataset.mkdir()
        (dataset / "data.csv").write_text("name\n학생회관\n", encoding="utf-8")
    output = tmp_path / "reports/result.json"
    result = compare(first, second, "--output", output)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["identical"] and report["files_compared"] == 1
    assert report["first"] == str(first)
    (second / "data.csv").write_text("name\n도서관\n", encoding="utf-8")
    assert compare(first, second).returncode == 1


def test_run_scripts_without_installed_package(project):
    source = SCRIPT.parents[1]
    shutil.copytree(source / "src", project / "src")
    shutil.copytree(source / "scripts", project / "scripts")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    for script, args in (
        ("smoke_test.py", ["script-smoke"]),
        ("inspect_dataset.py", ["--run-id", "script-smoke"]),
    ):
        result = subprocess.run(
            [sys.executable, str(project / "scripts" / script), *args],
            cwd=project.parent,
            env=environment,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    report = json.loads(
        (project / "data/runs/script-smoke/reports/summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["validation"]["valid"]

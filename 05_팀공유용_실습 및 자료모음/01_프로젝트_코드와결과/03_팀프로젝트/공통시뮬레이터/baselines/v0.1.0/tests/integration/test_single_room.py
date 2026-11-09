from aiot_sim.pipeline.aggregator import aggregate
from aiot_sim.pipeline.simulator import simulate
from aiot_sim.pipeline.validator import validate


def test_single_room(project, cfg):
    run = simulate(project, cfg, "single")
    assert aggregate(run) == 288
    result = validate(run)
    assert result["valid"], result
    assert result["sensor_rows"] == 1440


def test_five_minute_sampling(project, cfg):
    cfg["step_minutes"] = 5
    run = simulate(project, cfg, "sampled")
    assert aggregate(run) == 288
    result = validate(run)
    assert result["valid"], result
    assert result["sensor_rows"] == 288


def test_validator_detects_corruption(project, cfg):
    from aiot_sim.pipeline.writer import read_csv, write_csv

    run = simulate(project, cfg, "corrupt")
    path = next((run / "raw/sensors_1min").glob("*.csv"))
    rows = list(read_csv(path))
    rows[0]["co2_ppm"] = 9000
    write_csv(path, rows)
    result = validate(run)
    assert not result["valid"]
    assert any("no fault label" in message for message in result["errors"])


def test_run_collision_and_incomplete_status(project, cfg):
    import json

    import pytest

    run = simulate(project, cfg, "collision")
    with pytest.raises(FileExistsError):
        simulate(project, cfg, "collision")
    path = run / "reports/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["status"] = "running"
    path.write_text(json.dumps(manifest))
    assert not validate(run)["valid"]


def test_write_failure_marks_run_failed(project, cfg, monkeypatch):
    import json

    import pytest

    from aiot_sim.pipeline import simulator

    def fail(*args, **kwargs):
        raise OSError("injected disk failure")

    monkeypatch.setattr(simulator, "csv_writer", fail)
    with pytest.raises(OSError, match="injected disk failure"):
        simulate(project, cfg, "failed-write")
    manifest = json.loads(
        (project / "data/runs/failed-write/reports/manifest.json").read_text()
    )
    assert manifest["status"] == "failed"

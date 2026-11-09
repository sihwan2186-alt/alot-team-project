import csv
import json

from aiot_sim.pipeline.labeler import label_run
from aiot_sim.pipeline.physics_validator import validate_physics
from aiot_sim.pipeline.simulator import simulate


def test_validator_detects_thermal_and_label_corruption(project, cfg):
    run = simulate(project, cfg, "tamper")
    manifest = json.loads((run / "reports/manifest.json").read_text())
    assert validate_physics(run, manifest)["valid"]
    for folder, field, value in [
        ("thermal_balance_1min", "hvac_thermal_power_kw", "900"),
        ("environment_status_1min", "fault_active", "true"),
    ]:
        path = next((run / "truth" / folder).glob("*.csv"))
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        original = path.read_bytes()
        rows[0][field] = value
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        assert not validate_physics(run, manifest)["valid"]
        path.write_bytes(original)
    # Re-labeling uses the immutable rule snapshot of this run.
    assert label_run(run)["status"] == "complete"

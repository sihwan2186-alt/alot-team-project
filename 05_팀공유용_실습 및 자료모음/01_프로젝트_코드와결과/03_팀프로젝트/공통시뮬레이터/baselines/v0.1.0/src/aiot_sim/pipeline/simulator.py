import copy
import csv
import hashlib
import logging
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from ..clock import timestamps
from ..constants import SENSORS
from ..engines import (
    controller,
    energy,
    environment,
    external_environment,
    faults,
    occupancy,
    reservations,
    sensors,
)
from ..profiles import load
from ..random_utils import rng
from ..schemas import ControlAction, EnvironmentState, FacilityState, SimulationEvent
from .writer import json_write

LOG = logging.getLogger(__name__)


def csv_writer(stack, path, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()

    def emit(row):
        w.writerow(
            {k: str(v).lower() if isinstance(v, bool) else v for k, v in row.items()}
        )

    return emit


def simulate(root, cfg, run_id):
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid run ID")
    run = root / cfg["output_path"] / run_id
    run.mkdir(parents=True, exist_ok=False)
    profiles = load(root)
    requested = cfg.get("room_ids", [])
    if requested:
        unknown = set(requested) - {p["room_id"] for p in profiles}
        if unknown:
            raise ValueError(f"Unknown room IDs: {unknown}")
        profiles = [p for p in profiles if p["room_id"] in requested]
    profiles = sorted(profiles, key=lambda p: p["room_id"])
    seed = cfg["seed"]
    rules = cfg["rules"]
    dt = cfg["step_minutes"]
    manifest = {
        "status": "running",
        "config": cfg,
        "room_ids": [p["room_id"] for p in profiles],
        "sensor_rows": 0,
        "profile_sha256": hashlib.sha256(
            (root / "data/master/room_profiles.csv").read_bytes()
        ).hexdigest(),
    }
    # Capture immutable inputs in every run, so later master edits cannot alter validation.
    import shutil

    for name in ("rooms.csv", "room_profiles.csv"):
        dest = run / "inputs" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / "data/master" / name, dest)
    json_write(run / "reports/manifest.json", manifest)
    state = {
        p["room_id"]: {
            "env": EnvironmentState(),
            "facility": FacilityState(),
            "count": 0,
            "fault": None,
            "sensor_rng": rng(seed, p["room_id"], "sensors"),
            "fault_rng": rng(seed, p["room_id"], "faults"),
            "occupancy_rng": rng(seed, p["room_id"], "occupancy"),
            "activity": rng(seed, p["room_id"], "activity").uniform(0.2, 1.5),
        }
        for p in profiles
    }
    erules = dict(
        rules["environment"],
        fault_spike=rules["fault"]["spike"],
        fault_bias=rules["fault"]["bias_per_minute"],
    )
    try:
        with ExitStack() as events:
            res_write = csv_writer(
                events, run / "events/reservations.csv", reservations.FIELDS
            )
            occ_write = csv_writer(
                events,
                run / "events/occupancy_events.csv",
                list(SimulationEvent.__dataclass_fields__),
            )
            ctrl_write = csv_writer(
                events,
                run / "events/control_actions.csv",
                list(ControlAction.__dataclass_fields__),
            )
            anomaly_write = csv_writer(
                events,
                run / "truth/anomaly_events.csv",
                [
                    "event_id",
                    "room_id",
                    "start_time",
                    "end_time",
                    "anomaly_type",
                    "affected_variable",
                    "severity",
                    "cause",
                    "is_sensor_fault",
                ],
            )
            start = datetime.fromisoformat(str(cfg["start_date"]))
            for day in range(cfg["days"]):
                date = (start + timedelta(days=day)).date()
                times = list(timestamps(str(date), 1, dt))
                schedule = {
                    p["room_id"]: reservations.generate(
                        p, times[0], seed, rules["occupancy"]
                    )
                    for p in profiles
                }
                for daily_reservations in schedule.values():
                    for row in daily_reservations:
                        res_write({k: row[k] for k in reservations.FIELDS})
                with ExitStack() as files:
                    sensor_write = csv_writer(
                        files,
                        run / f"raw/sensors_1min/sensor_readings_{date}.csv",
                        ["timestamp", "room_id", *SENSORS],
                    )
                    truth_write = csv_writer(
                        files,
                        run
                        / f"truth/environment_truth_1min/environment_truth_{date}.csv",
                        ["timestamp", "room_id", *["true_" + s for s in SENSORS]],
                    )
                    facility_write = csv_writer(
                        files,
                        run / f"raw/facility_states_1min/facility_states_{date}.csv",
                        [
                            "timestamp",
                            "room_id",
                            *[
                                k
                                for k in FacilityState.__dataclass_fields__
                                if k != "last_changes"
                            ],
                        ],
                    )
                    energy_write = csv_writer(
                        files,
                        run / f"raw/energy_usage_1min/energy_usage_{date}.csv",
                        [
                            "timestamp",
                            "room_id",
                            "hvac_power_kw",
                            "ventilation_power_kw",
                            "lighting_power_kw",
                            "standby_power_kw",
                            "total_power_kw",
                            "interval_energy_kwh",
                        ],
                    )
                    # Internal integration always uses minute steps; output sampling is configurable.
                    for local, t in enumerate(timestamps(str(date))):
                        minute = day * 1440 + local
                        out = external_environment.outdoor(t, seed, erules)
                        for p in profiles:
                            rid = p["room_id"]
                            s = state[rid]
                            fault = s["fault"]
                            if fault and minute >= fault.end:
                                s["fault"] = fault = None
                            if fault is None:
                                fault = faults.maybe_start(
                                    s["fault_rng"],
                                    minute,
                                    s["env"],
                                    rules["fault"],
                                    cfg["enable_faults"],
                                )
                                s["fault"] = fault
                                if fault:
                                    end = min(cfg["days"] * 1440, fault.end)
                                    anomaly_write(
                                        {
                                            "event_id": f"A-{rid}-{minute}",
                                            "room_id": rid,
                                            "start_time": t.isoformat(),
                                            "end_time": (
                                                t + timedelta(minutes=end - minute)
                                            ).isoformat(),
                                            "anomaly_type": fault.kind,
                                            "affected_variable": fault.variable,
                                            "severity": rules["fault"]["severity"],
                                            "cause": "synthetic_injection",
                                            "is_sensor_fault": fault.kind
                                            in faults.SENSOR_KINDS,
                                        }
                                    )
                            count, resid = occupancy.update(
                                t,
                                p,
                                schedule[rid],
                                s["count"],
                                s["occupancy_rng"],
                                rules["occupancy"],
                                bool(fault and fault.kind == "high_occupancy"),
                            )
                            if count != s["count"]:
                                occ_write(
                                    asdict(
                                        SimulationEvent(
                                            f"O-{rid}-{minute}",
                                            t.isoformat(),
                                            rid,
                                            "entry" if count > s["count"] else "exit",
                                            count - s["count"],
                                            count,
                                            resid,
                                        )
                                    )
                                )
                            s["count"] = count
                            applied = copy.copy(s["facility"])
                            faults.apply_equipment(applied, fault)
                            # State at t is observed first; facilities at t drive [t,t+1).
                            obs = sensors.observe(
                                s["env"], count, s["sensor_rng"], erules, fault, minute
                            )
                            if local % dt == 0:
                                key = {"timestamp": t.isoformat(), "room_id": rid}
                                sensor_write(dict(**key, **obs))
                                truth_write(
                                    dict(
                                        **key,
                                        **{
                                            "true_" + k: count
                                            if k == "occupancy_count"
                                            else getattr(s["env"], k)
                                            for k in SENSORS
                                        },
                                    )
                                )
                                facility_write(
                                    dict(
                                        **key,
                                        **{
                                            k: v
                                            for k, v in asdict(applied).items()
                                            if k != "last_changes"
                                        },
                                    )
                                )
                                # Accumulate actual minute energies for sampled intervals below.
                                s["energy_key"] = key
                                s["energy_sum"] = {
                                    k: 0.0
                                    for k in energy.energy(
                                        p, applied, rules["facility"]
                                    )
                                }
                            power = energy.energy(
                                p,
                                applied,
                                rules["facility"],
                                enabled=cfg["enable_energy_model"],
                            )
                            for k, v in power.items():
                                s["energy_sum"][k] += v
                            if (local + 1) % dt == 0:
                                e = s["energy_sum"]
                                e = {
                                    k: v if k == "interval_energy_kwh" else v / dt
                                    for k, v in e.items()
                                }
                                energy_write(dict(**s["energy_key"], **e))
                            if cfg["enable_control_feedback"]:
                                new, changes = controller.decide(
                                    obs, count, s["facility"], minute, rules["facility"]
                                )
                                for device, previous, requested_state in changes:
                                    blocked = bool(
                                        fault and fault.kind == device + "_failure"
                                    )
                                    ctrl_write(
                                        asdict(
                                            ControlAction(
                                                f"C-{rid}-{minute}-{device}",
                                                t.isoformat(),
                                                rid,
                                                "rule_based",
                                                device,
                                                str(previous),
                                                str(requested_state),
                                                "observation_target_and_occupancy",
                                                not blocked,
                                            )
                                        )
                                    )
                                s["facility"] = new
                            environment.evolve(
                                s["env"],
                                p,
                                applied,
                                out,
                                count,
                                erules,
                                activity=s["activity"],
                            )
                manifest["sensor_rows"] += len(times) * len(profiles)
                LOG.info("%s: %s sensor rows written", date, manifest["sensor_rows"])
        manifest["status"] = "complete"
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        raise
    finally:
        json_write(run / "reports/manifest.json", manifest)
    return run

"""Separate injected causes, threshold exceedance episodes and post-fault recovery.

Recovery is temporal association, not a proof of causation. Thresholds and the
stabilization duration are descriptive synthetic assumptions, evaluated on truth.
"""

import json
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime, timedelta

from .writer import csv_writer, json_write, read_csv

PHYSICAL_VARIABLES = {
    "hvac_failure": ("temperature_c",),
    "ventilation_failure": ("temperature_c", "co2_ppm", "humidity_pct"),
    "high_occupancy": ("temperature_c", "co2_ppm", "humidity_pct"),
}
SENSOR_KINDS = {"missing", "spike", "stuck", "bias"}
VARIABLES = ("temperature_c", "humidity_pct", "co2_ppm")
STATUS_FIELDS = [
    "timestamp",
    "room_id",
    "fault_active",
    "sensor_fault_active",
    "equipment_fault_active",
    "occupancy_fault_active",
    "temperature_anomaly_active",
    "humidity_anomaly_active",
    "co2_anomaly_active",
    "environment_anomaly_active",
    "recovery_active",
    "recovery_variables",
]
RECOVERY_FIELDS = [
    "recovery_id",
    "room_id",
    "cause_event_id",
    "variable",
    "fault_start_time",
    "fault_end_time",
    "recovery_start_time",
    "recovery_end_time",
    "duration_minutes",
    "status",
]
ENV_FIELDS = [
    "event_id",
    "room_id",
    "start_time",
    "end_time",
    "affected_variable",
    "minimum_value",
    "maximum_value",
    "lower_bound",
    "upper_bound",
    "status",
]


class RoomLabels:
    """Per-room state machine. All intervals are left-closed, right-open."""

    def __init__(self, rid, rules, step=1):
        self.rid = rid
        self.rules = rules
        self.step = step
        self.recoveries = {}
        self.episodes = {}
        self.serial = 0

    def outside(self, variable, value):
        bound = self.rules[variable]
        return value < bound["min"] or value > bound["max"]

    def close_recovery(self, variable, t, status):
        item = self.recoveries.pop(variable)
        row = {k: v for k, v in item.items() if k != "stable_since"}
        row.update(
            recovery_end_time=t.isoformat(),
            duration_minutes=(
                t - datetime.fromisoformat(row["recovery_start_time"])
            ).total_seconds()
            / 60,
            status=status,
        )
        return row

    def update(self, t, values, fault, ended_faults=()):
        completed = []
        env_closed = []
        anomalies = {v: self.outside(v, values[v]) for v in VARIABLES}
        current_affected = (
            set(PHYSICAL_VARIABLES.get(fault["anomaly_type"], ())) if fault else set()
        )
        # An active physical cause interrupts recovery for the variables it affects.
        for variable in list(self.recoveries):
            if variable in current_affected:
                completed.append(
                    self.close_recovery(variable, t, "interrupted_by_fault")
                )
        for cause in ended_faults:
            for variable in PHYSICAL_VARIABLES.get(cause["anomaly_type"], ()):
                if (
                    variable in current_affected
                    or not anomalies[variable]
                    or variable in self.recoveries
                ):
                    continue
                self.serial += 1
                self.recoveries[variable] = dict(
                    recovery_id=f"REC-{self.rid}-{self.serial}",
                    room_id=self.rid,
                    cause_event_id=cause["event_id"],
                    variable=variable,
                    fault_start_time=cause["start_time"],
                    fault_end_time=cause["end_time"],
                    recovery_start_time=t.isoformat(),
                    stable_since=None,
                )
        # Stability is the elapsed span of consecutive normal observed samples.
        # With sampled output this does not assert unobserved continuity.
        for variable, item in list(self.recoveries.items()):
            item["stable_since"] = (
                None if anomalies[variable] else (item["stable_since"] or t)
            )
            if (
                item["stable_since"] is not None
                and (t - item["stable_since"]).total_seconds() / 60
                >= self.rules["recovery_stable_minutes"]
            ):
                completed.append(self.close_recovery(variable, t, "recovered"))
        for variable, out in anomalies.items():
            if out:
                if variable not in self.episodes:
                    self.serial += 1
                    b = self.rules[variable]
                    self.episodes[variable] = dict(
                        event_id=f"ENV-{self.rid}-{self.serial}",
                        room_id=self.rid,
                        start_time=t.isoformat(),
                        affected_variable=variable,
                        minimum_value=values[variable],
                        maximum_value=values[variable],
                        lower_bound=b["min"],
                        upper_bound=b["max"],
                    )
                else:
                    item = self.episodes[variable]
                    item["minimum_value"] = min(item["minimum_value"], values[variable])
                    item["maximum_value"] = max(item["maximum_value"], values[variable])
            elif variable in self.episodes:
                item = self.episodes.pop(variable)
                env_closed.append(dict(**item, end_time=t.isoformat(), status="closed"))
        kind = fault["anomaly_type"] if fault else ""
        status = dict(
            timestamp=t.isoformat(),
            room_id=self.rid,
            fault_active=bool(fault),
            sensor_fault_active=kind in SENSOR_KINDS,
            equipment_fault_active=kind in {"hvac_failure", "ventilation_failure"},
            occupancy_fault_active=kind == "high_occupancy",
            **{v.split("_")[0] + "_anomaly_active": anomalies[v] for v in VARIABLES},
            environment_anomaly_active=any(anomalies.values()),
            recovery_active=bool(self.recoveries),
            recovery_variables="|".join(sorted(self.recoveries)),
        )
        return status, completed, env_closed

    def finish(self, t):
        recoveries = [
            self.close_recovery(v, t, "right_censored") for v in list(self.recoveries)
        ]
        episodes = [
            dict(**item, end_time=t.isoformat(), status="right_censored")
            for item in self.episodes.values()
        ]
        return recoveries, episodes


def label_run(run):
    manifest = json.loads((run / "reports/manifest.json").read_text(encoding="utf-8"))
    if manifest.get("software_version") != "0.2.0":
        raise ValueError("Label only a v0.2.0 run; preserve historical outputs")
    cfg = manifest["config"]
    if manifest["status"] != "complete":
        raise ValueError("Generate the complete raw run before labeling")
    rules = cfg["rules"]["anomaly_label"]
    step = cfg["step_minutes"]
    faults = defaultdict(list)
    original_fields = None
    for row in read_csv(run / "truth/anomaly_events.csv"):
        original_fields = list(row)
        faults[row["room_id"]].append(row)
    states = {rid: RoomLabels(rid, rules, step) for rid in manifest["room_ids"]}
    pointers = defaultdict(int)
    counts = defaultdict(int)
    last = None
    json_write(
        run / "reports/labeling.json",
        dict(status="running", label_version=rules["label_version"]),
    )
    try:
        with ExitStack() as stack:
            recover_write = csv_writer(
                stack, run / "truth/recovery_events.csv", RECOVERY_FIELDS
            )
            env_write = csv_writer(
                stack, run / "truth/environment_anomaly_events.csv", ENV_FIELDS
            )
            source_fields = original_fields or [
                "event_id",
                "room_id",
                "start_time",
                "end_time",
                "anomaly_type",
                "affected_variable",
                "severity",
                "cause",
                "is_sensor_fault",
            ]
            fault_write = csv_writer(
                stack,
                run / "truth/fault_events.csv",
                [*source_fields, "fault_category"],
            )
            for rid, events in faults.items():
                for event in events:
                    kind = event["anomaly_type"]
                    category = (
                        "sensor"
                        if kind in SENSOR_KINDS
                        else "occupancy"
                        if kind == "high_occupancy"
                        else "equipment"
                    )
                    fault_write(dict(**event, fault_category=category))
            for path in sorted((run / "truth/environment_truth_1min").glob("*.csv")):
                date = path.stem[-10:]
                with ExitStack() as day:
                    write = csv_writer(
                        day,
                        run
                        / f"truth/environment_status_1min/environment_status_{date}.csv",
                        STATUS_FIELDS,
                    )
                    for row in read_csv(path):
                        t = datetime.fromisoformat(row["timestamp"])
                        rid = row["room_id"]
                        events = faults[rid]
                        idx = pointers[rid]
                        ended = []
                        while (
                            idx < len(events)
                            and events[idx]["end_time"] <= t.isoformat()
                        ):
                            ended.append(events[idx])
                            idx += 1
                        pointers[rid] = idx
                        fault = (
                            events[idx]
                            if idx < len(events)
                            and events[idx]["start_time"]
                            <= t.isoformat()
                            < events[idx]["end_time"]
                            else None
                        )
                        values = {v: float(row["true_" + v]) for v in VARIABLES}
                        status, recovered, episodes = states[rid].update(
                            t, values, fault, ended
                        )
                        write(status)
                        counts["rows"] += 1
                        counts["environment_anomaly_rows"] += status[
                            "environment_anomaly_active"
                        ]
                        counts["recovery_rows"] += status["recovery_active"]
                        for item in recovered:
                            recover_write(item)
                            counts["recovery_events"] += 1
                            counts[item["status"]] += 1
                        for item in episodes:
                            env_write(item)
                            counts["environment_events"] += 1
                        last = t
            end = last + timedelta(minutes=step)
            for state in states.values():
                recovered, episodes = state.finish(end)
                for item in recovered:
                    recover_write(item)
                    counts["recovery_events"] += 1
                    counts[item["status"]] += 1
                for item in episodes:
                    env_write(item)
                    counts["environment_events"] += 1
        result = dict(
            status="complete",
            label_version=rules["label_version"],
            thresholds=rules,
            **counts,
        )
    except BaseException as error:
        json_write(
            run / "reports/labeling.json", dict(status="failed", error=str(error))
        )
        raise
    json_write(run / "reports/labeling.json", result)
    return result

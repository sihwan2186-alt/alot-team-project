import json
import math
from collections import defaultdict
from datetime import datetime, timedelta

from ..constants import SENSORS
from .writer import json_write, read_csv, write_csv


def aggregate(run, minutes=5):
    manifest = json.loads((run / "reports/manifest.json").read_text(encoding="utf-8"))
    step = manifest["config"]["step_minutes"]
    if minutes <= 0 or 1440 % minutes or minutes % step:
        raise ValueError(
            "Aggregation must divide a day and be a multiple of sampling interval"
        )
    count = 0
    for path in sorted((run / "raw/sensors_1min").glob("*.csv")):
        groups = defaultdict(list)
        for row in read_csv(path):
            t = datetime.fromisoformat(row["timestamp"])
            bucket = (
                t.replace(minute=t.minute // minutes * minutes, second=0)
                if 60 % minutes == 0
                else t.replace(hour=0, minute=0)
                + timedelta(minutes=(t.hour * 60 + t.minute) // minutes * minutes)
            )
            groups[(bucket.isoformat(), row["room_id"])].append(row)
        result = []
        for (stamp, rid), rows in sorted(groups.items()):
            out = {"timestamp": stamp, "room_id": rid, "sample_count": len(rows)}
            for name in SENSORS:
                vals = [float(r[name]) for r in rows if r[name] != ""]
                out[name + "_missing_ratio"] = 1 - len(vals) / len(rows)
                if name == "noise_dba":
                    out["noise_leq_dba"] = (
                        10 * math.log10(sum(10 ** (v / 10) for v in vals) / len(vals))
                        if vals
                        else None
                    )
                elif name == "occupancy_count":
                    out["occupancy_count_last"] = (
                        int(rows[-1][name]) if rows[-1][name] else None
                    )
                    out["occupancy_count_max"] = int(max(vals)) if vals else None
                else:
                    out[name + "_mean"] = sum(vals) / len(vals) if vals else None
                if name == "co2_ppm":
                    out["co2_ppm_max"] = max(vals) if vals else None
                    out["co2_ppm_last"] = (
                        float(rows[-1][name]) if rows[-1][name] else None
                    )
            result.append(out)
        write_csv(run / f"derived/sensors_5min/{path.name}", result)
        count += len(result)
    for path in sorted((run / "raw/energy_usage_1min").glob("*.csv")):
        groups = defaultdict(list)
        for row in read_csv(path):
            t = datetime.fromisoformat(row["timestamp"])
            bucket = t.replace(hour=0, minute=0) + timedelta(
                minutes=(t.hour * 60 + t.minute) // minutes * minutes
            )
            groups[(bucket.isoformat(), row["room_id"])].append(row)
        result = []
        for (stamp, rid), rows in sorted(groups.items()):
            result.append(
                {
                    "timestamp": stamp,
                    "room_id": rid,
                    "mean_power_kw": sum(float(r["total_power_kw"]) for r in rows)
                    / len(rows),
                    "interval_energy_kwh": sum(
                        float(r["interval_energy_kwh"]) for r in rows
                    ),
                }
            )
        write_csv(run / f"derived/energy_5min/{path.name}", result)
    json_write(run / "reports/aggregation.json", {"minutes": minutes, "rows": count})
    return count

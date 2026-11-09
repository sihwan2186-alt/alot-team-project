import json

from .writer import json_write, read_csv


def report(run):
    files = []
    for p in sorted(run.rglob("*.csv")):
        files.append(
            {
                "path": str(p.relative_to(run)),
                "bytes": p.stat().st_size,
                "rows": sum(1 for _ in read_csv(p)),
            }
        )
    result = {
        "run_id": run.name,
        "csv_files": files,
        "total_csv_bytes": sum(f["bytes"] for f in files),
        "validation": json.loads((run / "reports/validation_report.json").read_text())
        if (run / "reports/validation_report.json").exists()
        else None,
    }
    json_write(run / "reports/summary.json", result)
    return result

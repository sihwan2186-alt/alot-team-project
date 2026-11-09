import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path


def serialize(v):
    return str(v).lower() if isinstance(v, bool) else v


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = iter(rows)
    first = next(rows, None)
    if first is not None and is_dataclass(first):
        first = asdict(first)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields or list(first or {}))
        writer.writeheader()
        if first is not None:
            writer.writerow({k: serialize(v) for k, v in first.items()})
        for row in rows:
            row = asdict(row) if is_dataclass(row) else row
            writer.writerow({k: serialize(v) for k, v in row.items()})


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


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

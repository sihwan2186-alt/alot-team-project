"""Compare every CSV byte, including truth/events, excluding run metadata."""

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("first", type=Path)
parser.add_argument("second", type=Path)
parser.add_argument("--output", type=Path)
args = parser.parse_args()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


first = {str(p.relative_to(args.first)): digest(p) for p in args.first.rglob("*.csv")}
second = {
    str(p.relative_to(args.second)): digest(p) for p in args.second.rglob("*.csv")
}
result = dict(
    identical=first == second,
    files_compared=len(first),
    first=str(args.first),
    second=str(args.second),
    sha256=first,
)
text = json.dumps(result, ensure_ascii=False, indent=2)
if args.output:
    args.output.write_text(text + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "sha256"}, indent=2))
raise SystemExit(0 if result["identical"] else 1)

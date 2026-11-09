from .constants import SOURCE_URL
from .pipeline.writer import read_csv, write_csv

ROOMS = {
    "STU": (
        "학생회관",
        "B102A B102B B102C B102D B102E B116 B117 B118 B119 B121 B122 B123 B124 B125 B126 B128 B129 B130 B131 201C 201D 201E 201F 201G 201H 201I 213 215 400 401 402 403 404 408 409 410 411 412",
    ),
    "LIB": (
        "도서관",
        "B101A B101B B101C B101D B101E B101F B101G B101H B101I B101J B105A B105B",
    ),
    "WON": ("원화관", "619A 619B 701A 701B 702 703 704 711 712"),
    "HEA": ("보건관", "421 422 423 424"),
}


def catalog():
    return [
        {
            "room_id": f"{code}-{n}",
            "building_code": code,
            "building_name": name,
            "room_number": n,
            "floor": "B1" if n.startswith("B") else n[0],
            "floor_verified": False,
            "source_type": "user_provided_facility_screenshots",
            "source_url": SOURCE_URL,
            "source_checked_date": "2026-11-02",
            "notes": "층수는 호실로 추정; 공식 시설 코드는 미확인",
        }
        for code, (name, numbers) in ROOMS.items()
        for n in numbers.split()
    ]


def generate(root):
    path = root / "data/master/rooms.csv"
    expected = catalog()
    if path.exists():
        actual = list(read_csv(path))
        if {r["room_id"] for r in actual} != {r["room_id"] for r in expected} or len(
            actual
        ) != 63:
            raise ValueError(
                "Existing rooms.csv differs; preserve it and resolve manually"
            )
        return
    write_csv(path, expected)

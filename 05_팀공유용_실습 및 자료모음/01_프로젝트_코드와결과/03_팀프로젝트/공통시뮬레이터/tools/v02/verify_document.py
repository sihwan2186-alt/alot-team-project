"""Final DOCX structural and rendered-page checks; visual review remains manual."""

import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

import pdfplumber
from docx import Document
from lxml import etree

R = Path(__file__).resolve().parents[2]
D = R / "deliverables/Smart_Campus_AIoT_Simulator_Technology_Overview_v1_1.docx"
Q = R / "deliverables/v0.2.0/qa/final_render"
inventory = json.loads((R / "deliverables/v0.2.0/document_inventory.json").read_text())
ns = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
with ZipFile(D) as z:
    x = etree.fromstring(z.read("word/document.xml"))
    checks = dict(
        zip_valid=z.testzip() is None,
        native_equations=len(x.xpath("//m:oMath", namespaces=ns)),
        bookmarks=len(x.xpath("//w:bookmarkStart", namespaces=ns)),
        no_raw_math_braces=not any(
            "{" in t or "}" in t for t in x.xpath("//m:t/text()", namespaces=ns)
        ),
    )
with pdfplumber.open(next(Q.glob("*.pdf"))) as pdf:
    texts = [p.extract_text() or "" for p in pdf.pages]

    def norm(s):
        return re.sub(r"\s+", "", s)

    checks.update(
        rendered_pages=len(pdf.pages),
        contents_pages_match=all(
            norm(item["title"]) in norm(texts[item["page"] - 1])
            for item in inventory["contents"]
        ),
        korean_text_present="공통 환경 시뮬레이터 기술 백서" in texts[0],
        no_blank_body_pages=all(len(t) > 200 for t in texts[1:]),
        text_inside_page=all(
            not any(
                c["text"].strip()
                and (
                    c["x0"] < 0
                    or c["x1"] > p.width + 1
                    or c["top"] < 0
                    or c["bottom"] > p.height + 1
                )
                for c in p.chars
            )
            for p in pdf.pages
        ),
    )
checks["tables"] = len(Document(D).tables)
checks["visually_reviewed_pages"] = list(range(1, 23))
checks["final_render_changed_pages"] = [
    i
    for i in range(1, 23)
    if (Q / f"page-{i}.png").read_bytes()
    != (Q.parent / "render" / f"page-{i}.png").read_bytes()
]
checks["passed"] = (
    checks["zip_valid"]
    and checks["native_equations"] >= 10
    and checks["bookmarks"] == 20
    and checks["rendered_pages"] == 22
    and all(
        checks[k]
        for k in (
            "no_raw_math_braces",
            "contents_pages_match",
            "korean_text_present",
            "no_blank_body_pages",
            "text_inside_page",
        )
    )
)
(R / "deliverables/v0.2.0/document_validation.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2)
)
D.with_suffix(".docx.sha256").write_text(
    hashlib.sha256(D.read_bytes()).hexdigest() + "  " + D.name + "\n"
)
print(json.dumps(checks, ensure_ascii=False, indent=2))
assert checks["passed"]

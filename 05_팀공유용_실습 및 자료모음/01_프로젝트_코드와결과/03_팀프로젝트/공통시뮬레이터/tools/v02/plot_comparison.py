import json
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.colors import HexColor

R = Path(__file__).resolve().parents[2]
A = R / "deliverables/v0.2.0/assets"
A.mkdir(parents=True, exist_ok=True)
w = json.loads((R / "deliverables/v0.2.0/extreme_window.json").read_text())
d = Drawing(720, 285)
lp = LinePlot()
lp.x = 60
lp.y = 40
lp.width = 630
lp.height = 200
series = []
for label in ("baseline", "v02"):
    series.append(
        [
            (
                int(r["timestamp"][11:13]) * 60 + int(r["timestamp"][14:16]),
                float(r["true_temperature_c"]),
            )
            for r in w[label]
        ]
    )
lp.data = series
lp.xValueAxis.valueMin = 1070
lp.xValueAxis.valueMax = 1170
lp.xValueAxis.valueSteps = [1080, 1110, 1140, 1170]
lp.xValueAxis.labelTextFormat = lambda x: f"{int(x) // 60:02}:{int(x) % 60:02}"
lp.yValueAxis.valueMin = 20
lp.yValueAxis.valueMax = 45
lp.yValueAxis.valueSteps = [20, 25, 30, 35, 40, 45]
lp.yValueAxis.visibleGrid = True
lp.yValueAxis.gridStrokeColor = HexColor("#eeeeee")
for j, color in enumerate(("#111111", "#888888")):
    lp.lines[j].strokeColor = HexColor(color)
    lp.lines[j].strokeWidth = 1.6
lp.lines[1].strokeDashArray = [5, 3]
d.add(lp)
d.add(
    String(
        60,
        263,
        "STU-B131   2026-09-14   Temperature (deg C)",
        fontName="Helvetica",
        fontSize=13,
    )
)
d.add(
    String(
        60,
        11,
        "KST   Black: v0.1.0   Gray dashed: v0.2.0   Fault: 17:55 to 18:29",
        fontName="Helvetica",
        fontSize=10,
    )
)
renderSVG.drawToFile(d, str(A / "extreme_comparison.svg"))

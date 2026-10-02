"""Build a visual inspection checklist from actual exported schematic images."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

CIRCUITS = [
    ("common_emitter_amplifier", "Common Emitter Amplifier"),
    ("rc_low_pass_filter", "RC Low-pass Filter"),
    ("rc_high_pass_filter", "RC High-pass Filter"),
    ("voltage_divider", "Voltage Divider"),
    ("bridge_rectifier", "Bridge Rectifier"),
    ("555_astable_multivibrator", "NE555 Astable Multivibrator"),
    ("led_blinker", "LED Blinker"),
]
PAGE_BG = colors.HexColor("#f5f5f4")
TEXT_PRIMARY = colors.HexColor("#191917")
ACCENT = colors.HexColor("#2888a8")


def build_report(export_root: Path, output: Path, native_root: Path | None = None) -> list[dict]:
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("Inspection", str(fonts / "segoeui.ttf")))
    pdfmetrics.registerFont(TTFont("InspectionBold", str(fonts / "segoeuib.ttf")))
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = landscape(A3)
    pdf = canvas.Canvas(str(output), pagesize=(width, height))
    pdf.setTitle("LTspice Schematic Visual Verification")
    pdf.setAuthor("Spice Craft")
    pdf.setCreator("Spice Craft inspection tooling")
    pdf.setSubject("Seven exported schematics: visual layout and independently verified electrical partitions")
    manifest = []
    for page, (stem, title) in enumerate(CIRCUITS, 1):
        png = export_root / f"{stem}.png"
        native = native_root / stem / f"{stem}_ltspice.png" if native_root else None
        if native and native.is_file():
            png = native
            method = "Native LTspice application screenshot of the exported ASC"
        else:
            method = "Inspection rendering of exported ASC with installed LTspice ASY geometry (not an application screenshot)"
        record = json.loads((export_root / f"{stem}_routing.json").read_text(encoding="utf-8"))
        pdf.setFillColor(PAGE_BG)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor(TEXT_PRIMARY)
        pdf.setFont("InspectionBold", 26)
        pdf.drawString(36, height - 44, title)
        pdf.setFont("Inspection", 12)
        pdf.drawString(36, height - 66, method)
        with Image.open(png) as image:
            image_width, image_height = image.size
        available_width, available_height = width - 72, height - 176
        scale = min(available_width / image_width, available_height / image_height)
        shown_width, shown_height = image_width * scale, image_height * scale
        pdf.drawImage(str(png), (width - shown_width) / 2, 114 + (available_height - shown_height) / 2,
                      width=shown_width, height=shown_height, mask="auto")
        pdf.setFillColor(TEXT_PRIMARY)
        pdf.setFont("InspectionBold", 13)
        pdf.drawString(36, 104, "Visual acceptance: BLOCKED - image-capable review unavailable; no visual pass claimed.")
        pdf.setFillColor(ACCENT)
        pdf.setFont("InspectionBold", 13)
        verdict = record["netlist_verification"]
        electrical = "PASS" if verdict.get("ok") else "FAIL"
        pdf.drawString(36, 84, f"Real LTspice electrical partition: {electrical} | {len(record['actual_pin_nodes'])} pins | "
                       f"{len(record['expected_nets'])} groups | {record['metrics']['segments']} wire segments | "
                       f"{record['metrics']['crossings']} nonconductive crossings")
        pdf.setFillColor(TEXT_PRIMARY)
        pdf.setFont("Inspection", 12)
        pdf.drawString(36, 62, "Visual checks: exact pin ends; orthogonal wires; body clearance; bends and detours; junctions; labels and spacing.")
        pdf.drawString(36, 42, "Electrical connectivity is checked independently by netlisting; visual review must still assess presentation quality.")
        pdf.drawRightString(width - 36, 22, f"{page} / {len(CIRCUITS)}")
        pdf.showPage()
        manifest.append({"page": page, "circuit": title, "stem": stem, "image": str(png.resolve()), "method": method})
    pdf.save()
    output.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    import fitz
    document = fitz.open(output)
    rendered = output.parent / f"{output.stem}_pages"
    rendered.mkdir(parents=True, exist_ok=True)
    for index, page in enumerate(document, 1):
        page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False).save(rendered / f"page_{index:02}.png")
    document.close()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--native", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_report(args.exports, args.output, args.native), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

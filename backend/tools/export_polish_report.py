"""Measurement-only Phase 8 evidence from existing ASC and actual .net files.

python -B backend/tools/export_polish_report.py --output REPORT_DIRECTORY
    [--before DIRECTORY] [--after DIRECTORY] [--circuit SOURCE_JSON ...]

Never writes ASC, invokes LTspice, renders images, or changes routing. The source
exporter's returned geometry is used in memory ONLY as an exact net-ownership
reference: either raw or cleaned segments work, provided their coverage agrees.
Actual before/after records supply all reported serialized routing measurements.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import NetGeometry, PinPoint, WireSegment, validate_net_geometry
from app.services.connectivity import build_connectivity
from app.services.ltspice_exporter import generate_asc_with_routing
from app.services.pin_maps import COMPONENT_LIBRARY
from app.services.routing.geometry import intersection, on_segment
from app.services.routing.metrics import measure_routing
from app.services.routing.models import SafeCrossing
from tools.verify_ltspice import compare_partitions, parse_netlist, read_ltspice_text

PHASE_ROOT = BACKEND_ROOT / "tests/artifacts/phase_8"
DEFINITIONS = {
    "scope": "Measurement only; no optimization, native rendering, PDF, or visual acceptance claim.",
    "components": "Number of actual ASC SYMBOL blocks; identities, positions, orientations and SYMATTR values are compared independently of block order. WINDOW changes are presentation-only.",
    "segments": "One segment per serialized WIRE record, including duplicates and zero-length records. Endpoints are not snapped; nonzero diagonals are rejected.",
    "wire_length": "routing.total_length is the sum of serialized Manhattan lengths in LTspice coordinate units. Duplicates/overlaps count as recorded. wire_coverage_length instead measures their collinear union once.",
    "net_assignment": "Every nonzero ASC WIRE must fit wholly within exactly one source-routed net's collinear coverage union. Exact coverage must match per net. This permits reversal, sorting, merging and splitting, not relocation. No geometry is read from *_routing.json.",
    "bends_junctions": "routing.bend_count counts degree-two orthogonal turns; junction_count counts degree >= 3 contacts in measure_routing's private per-net graphs. Collinear subdivisions are not bends. Unsplit interior Xs do not conduct. Physical pins/flags make contacts; labels do not shortcut remote islands.",
    "crossings": "Distinct proper interior cross-net Xs from the serialized segments using routing.geometry.intersection; contact/short validation is separate. No crossings are assumed from a stale routing summary.",
    "pin_pairs": "measure_routing evaluates all unordered pin pairs per net. Detour ratio is mean shortest routed/Manhattan distance for reachable noncoincident pairs; detours require ratio > 1.5 and excess >= 64. Disconnected pairs and coincident pairs are explicit. Efficiency is summed per-net pin HPWL / recorded length, or null for disconnected pairs.",
    "routing_bbox": "routing.bounding_box encloses recorded wire endpoints and all installed ASY pins, including unwired singleton pins; no text, flags or symbol bodies. Area is envelope width times height.",
    "circuit_bbox": "circuit_bbox encloses serialized wire endpoints plus transformed installed ASY body strokes and pins, excluding FLAG glyphs, text, windows and ASC decorative primitives. Curves use the existing renderer tessellation; no sheet margin is added.",
    "full_presentation_bbox": "Renderer estimate at scale 1.0 from the existing _build_scene/_layout helpers, with ALL descriptions included, installed ASY default windows plus ASC overrides, flags, primitives, pin labels and text. Includes the renderer's 4-unit geometry padding and host font measurements. Text stays upright and renderer default/alignment behavior may differ from LTspice; this is NOT a native ink/crop bound. Hidden windows and unsupported defaults follow the existing renderer unchanged.",
    "labels": "Counts distinguish FLAG records, ground/non-ground flags, ASC TEXT comments/directives, leading descriptions, WINDOW overrides, and renderer-visible label objects. Counts are records/objects, not unique strings or wrapped lines.",
    "sheet": "Exact SHEET [number, width, height] declaration. Independent of occupied geometry and presentation bounds; not a clipping or page-fit assertion.",
    "topology": "Existing adjacent .net files are parsed by verify_ltspice.parse_netlist and compared to source canonical pin partitions (including singleton unwired pins), then to each other. Node-token renaming is allowed. No netlist is generated here; provenance/freshness of supplied .net files is the caller's responsibility. SHA-256 identifies the exact inputs measured.",
    "invariants": "Fail on exact per-net coverage, SYMBOL identity/attribute/position/orientation, pin, FLAG, IOPIN, conductive geometry, or actual netlist partition drift. Wire record count/length, windows, descriptions and sheet size may change. Electrical TEXT directives must remain equal ignoring position/order.",
    "delta": "Numeric deltas are after minus before; negative means a smaller measured quantity, not automatically a quality improvement. All lengths are source-coordinate units and all areas squared units; file_bytes is the on-disk byte count.",
}


class EvidenceError(ValueError):
    """Missing ownership or an invariant violation: never a successful report."""


def default_sources() -> list[Path]:
    """The five bundled circuits and the divider/bridge routing fixtures."""
    return sorted((BACKEND_ROOT / "circuits").glob("*.json")) + [
        BACKEND_ROOT / "tests/fixtures/routing/voltage_divider.json",
        BACKEND_ROOT / "tests/fixtures/routing/bridge_rectifier.json",
    ]


def _line_interval(start: tuple, end: tuple) -> tuple[str, int, int, int]:
    segment = WireSegment("measurement", start, end)
    axis = segment.orientation  # Reject diagonals and degenerate intervals.
    if axis == "horizontal":
        return "h", start[1], min(start[0], end[0]), max(start[0], end[0])
    return "v", start[0], min(start[1], end[1]), max(start[1], end[1])


def canonical_coverage(wires: Iterable[tuple[tuple, tuple]]) -> list[list]:
    """Exact interval-union fingerprint, NOT a replacement route or contact graph.

    Ignore endpoint direction, duplicate ink and collinear subdivisions. Never
    merge across an axis/coordinate or a positive gap. Zero records carry no ink.
    Electrical contacts are verified separately, since equal ink is insufficient.
    """
    rows: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
    for start, end in wires:
        if start != end:
            axis, coordinate, lo, hi = _line_interval(start, end)
            rows[axis, coordinate].append((lo, hi))
    result = []
    for (axis, coordinate), intervals in sorted(rows.items()):
        merged: list[list[int]] = []
        for lo, hi in sorted(intervals):
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        result.extend([axis, coordinate, lo, hi] for lo, hi in merged)
    return result


def assign_serialized_wires(
    wires: Iterable[tuple[tuple, tuple]], reference_nets: Iterable[NetGeometry],
) -> list[NetGeometry]:
    """Copy reference terminals and assign actual records by exact net coverage.

    Both a subdivided baseline and a merged after-ASC can be assigned against
    either reference form. Fail closed on unknown/ambiguous ink or missing ink.
    No inputs are mutated and no records are normalized for measurement.
    """
    reference_nets = list(reference_nets)
    if len({net.name for net in reference_nets}) != len(reference_nets):
        raise EvidenceError("Duplicate reference net names")
    coverage = {net.name: canonical_coverage((s.start, s.end) for s in net.segments)
                for net in reference_nets}
    assigned = {net.name: NetGeometry(net.name, list(net.pins), list(net.flags))
                for net in reference_nets}
    for start, end in wires:
        if start == end:
            owners = [net.name for net in reference_nets
                      if any(on_segment(start, s.start, s.end) for s in net.segments)
                      or start in net.flags or any(pin.point == start for pin in net.pins)]
        else:
            axis, coordinate, lo, hi = _line_interval(start, end)
            owners = [name for name, intervals in coverage.items()
                      if any(a == axis and c == coordinate and l <= lo and hi <= h
                             for a, c, l, h in intervals)]
        if len(owners) != 1:
            raise EvidenceError(f"WIRE {start} -> {end}: expected one coverage owner, got {owners}")
        name = owners[0]
        assigned[name].segments.append(WireSegment(name, start, end))
    for name, net in assigned.items():
        actual = canonical_coverage((s.start, s.end) for s in net.segments)
        if actual != coverage[name]:
            raise EvidenceError(f"Serialized wire coverage drift for net {name}: "
                                f"expected {coverage[name]}, got {actual}")
    return [assigned[name] for name in sorted(assigned)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bbox(points: Iterable[tuple]) -> dict[str, Any]:
    points = list(points)
    if not points:
        return {"bounds": None, "width": 0, "height": 0, "area": 0}
    xs, ys = zip(*points)
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    return {"bounds": bounds, "width": width, "height": height, "area": width * height}


def _symbol_evidence(schematic, symbols) -> tuple[list[dict], dict[str, PinPoint]]:
    definitions = {definition.symbol.replace("\\", "/").casefold(): definition
                   for definition in COMPONENT_LIBRARY.values()}
    identities, pins = [], {}
    seen = set()
    for instance in schematic.instances:
        reference = instance.attributes.get("InstName", "")
        if not reference or reference.casefold() in seen:
            raise EvidenceError(f"Missing/duplicate SYMBOL InstName {reference!r}")
        seen.add(reference.casefold())
        name = instance.name.replace("\\", "/").casefold()
        definition = definitions.get(name)
        if definition is None:
            raise EvidenceError(f"No canonical pin identities for SYMBOL {instance.name}")
        symbol = symbols[instance.name]
        installed_pins = {(pin.x, pin.y): pin for pin in symbol.pins}
        canonical_pins = {(pin.x, pin.y): pin for pin in definition.pins}
        if len(installed_pins) != len(symbol.pins) or set(installed_pins) != set(canonical_pins):
            raise EvidenceError(f"Installed ASY pin coordinates differ from canonical {name}")
        for point, canonical in canonical_pins.items():
            pins[f"{reference}.{canonical.id}"] = PinPoint(reference, canonical.id,
                                                          instance.transform(*point))
        identities.append({"reference": reference, "symbol": name,
                           "position": [instance.x, instance.y], "orientation": instance.orientation,
                           "attributes": dict(sorted(instance.attributes.items()))})
    return sorted(identities, key=lambda item: item["reference"]), pins


def _geometry_diagnostics(nets: list[NetGeometry]) -> list[dict]:
    # Reuse validator contact/short rules. Interior attached pins and zero records
    # are measurable, even though the production exporter demands endpoint pins
    # and no zero records. All other errors (and NET_SHORT warnings) remain fatal.
    result = []
    for diagnostic in validate_net_geometry(nets):
        if diagnostic.code == "ZERO_LENGTH_WIRE":
            continue
        if diagnostic.code == "PIN_NOT_CONNECTED":
            net = next(net for net in nets if net.name == diagnostic.net)
            if any(on_segment(diagnostic.expected, s.start, s.end)
                   for s in net.segments if s.start != s.end):
                continue
        if diagnostic.severity == "error" or diagnostic.code == "NET_SHORT":
            result.append(asdict(diagnostic))
    return result


def measure_asc(
    asc_path: str | Path, reference_nets: Iterable[NetGeometry], *,
    expected_groups: Mapping[str, Iterable[str]] | None = None,
    symbol_root: str | Path | None = None,
) -> dict[str, Any]:
    """Measure one existing ASC; no .net required until compare_asc_pair.

    reference_nets supplies net names/coverage/pin and flag invariants only. All
    measured pins come from this ASC's installed ASY symbols. Return JSON-safe
    metrics, input hashes, signatures and explicit geometry diagnostics.
    """
    # Pillow is an optional report dependency, not a core metrics dependency.
    from tools import render_asc as renderer

    path = Path(asc_path).resolve()
    schematic = renderer.parse_asc(path)
    root = renderer.detect_symbol_root(symbol_root)
    symbols = {name: renderer.load_symbol(renderer._symbol_path(root, name))
               for name in sorted({instance.name for instance in schematic.instances})}
    identities, pins = _symbol_evidence(schematic, symbols)
    nets = assign_serialized_wires(schematic.wires, reference_nets)
    reference_flags = sorted((point, net.name) for net in nets for point in net.flags)
    if sorted(schematic.flags) != reference_flags:
        raise EvidenceError(f"{path.name}: physical FLAG name/coordinate drift")
    recorded = set()
    for net in nets:
        for pin in net.pins:
            key = f"{pin.component}.{pin.pin}"
            if key in recorded or pins.get(key) != pin:
                raise EvidenceError(f"{path.name}: reference pin missing, moved or repeated: {key}")
            recorded.add(key)
        net.pins = [pins[f"{pin.component}.{pin.pin}"] for pin in net.pins]
    for key in sorted(set(pins) - recorded):
        nets.append(NetGeometry(f"unconnected:{key}", pins=[pins[key]]))
    if expected_groups is not None:
        actual_owner = {f"{pin.component}.{pin.pin}": net.name for net in nets for pin in net.pins}
        source_check = compare_partitions(expected_groups, actual_owner)
        if not source_check.ok:
            raise EvidenceError(f"{path.name}: reference/source pin partition drift: {source_check.to_dict()}")

    crossings = set()
    for index, left in enumerate(nets):
        for right in nets[index + 1:]:
            for a in left.segments:
                for b in right.segments:
                    if a.start != a.end and b.start != b.end:
                        kind, point = intersection(a, b)
                        if kind == "cross":
                            crossings.add(SafeCrossing(tuple(sorted((left.name, right.name))), point))
    routing = measure_routing(nets, crossings=sorted(crossings, key=lambda c: (c.nets, c.point)))
    circuit_scene, _ = renderer._build_scene(
        replace(schematic, flags=[], texts=[], primitives=[]), symbols, True)
    circuit_bbox = _bbox([point for stroke in circuit_scene.strokes for point in stroke.points]
                         + circuit_scene.pins)
    scene, omitted = renderer._build_scene(schematic, symbols, True)
    fonts = renderer._Fonts()
    presentation, _ = renderer._layout(scene, 1.0, fonts)
    full_bbox = _bbox([(presentation[0], presentation[1]), (presentation[2], presentation[3])])
    text = renderer._read_text(path)
    sheets, iopins = [], []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "SHEET":
            if len(fields) != 4:
                raise EvidenceError(f"{path.name}: malformed SHEET")
            sheets.append(list(map(int, fields[1:])))
        if fields and fields[0] == "IOPIN":
            iopins.append(" ".join(fields))
    if len(sheets) != 1 or any(value <= 0 for value in sheets[0]):
        raise EvidenceError(f"{path.name}: expected one positive SHEET declaration")
    coverage = {net.name: canonical_coverage((s.start, s.end) for s in net.segments)
                for net in sorted(nets, key=lambda n: n.name)}
    labels = {
        "flags": len(schematic.flags),
        "ground_flags": sum(name == "0" for _, name in schematic.flags),
        "non_ground_flags": sum(name != "0" for _, name in schematic.flags),
        "text_records": len(schematic.texts),
        "comments": sum(t.value.startswith(";") for t in schematic.texts),
        "directives": sum(t.value.startswith("!") for t in schematic.texts),
        "header_descriptions": sum(t.description for t in schematic.texts),
        "symbol_window_overrides": sum(len(i.windows) for i in schematic.instances),
        "renderer_visible_labels": len(scene.labels),
        "omitted_descriptions": omitted,
    }
    return {
        "asc": str(path), "asc_sha256": _sha256(path), "file_bytes": path.stat().st_size,
        "components": len(schematic.instances), "wires": len(schematic.wires),
        "sheet": sheets[0], "routing": routing, "circuit_bbox": circuit_bbox,
        "full_presentation_bbox": full_bbox, "labels": labels,
        "wire_coverage_length": sum(hi - lo for intervals in coverage.values()
                                    for _, _, lo, hi in intervals),
        "wire_coverage": coverage, "symbols": identities,
        "pins": {key: list(pin.point) for key, pin in sorted(pins.items())},
        "flags": [[list(point), name] for point, name in sorted(schematic.flags)],
        "iopins": sorted(iopins),
        "electrical_directives": sorted(t.value for t in schematic.texts if t.value.startswith("!")),
        "geometry_diagnostics": _geometry_diagnostics(nets),
        "symbol_root": str(root),
        "symbols_used": [{"path": str(symbol.path), "sha256": _sha256(symbol.path)}
                         for _, symbol in sorted(symbols.items())],
        "presentation_estimator": {"tool": "tools.render_asc", "scale": 1.0,
                                   "font": fonts.path, "include_description": True,
                                   "native_ltspice_bounds": False},
    }


def _verify_existing_netlist(asc: Path, expected, root: Path) -> tuple[dict, dict]:
    netlist = asc.with_suffix(".net")
    if not netlist.is_file() or not netlist.stat().st_size:
        raise EvidenceError(f"Missing/empty actual LTspice netlist: {netlist}")
    actual = parse_netlist(read_ltspice_text(asc), read_ltspice_text(netlist), symbol_roots=[root])
    verification = compare_partitions(expected, actual).to_dict()
    return {"file": str(netlist), "sha256": _sha256(netlist),
            "verification": verification, "actual_pin_nodes": actual}, actual


def _numeric_deltas(before: dict, after: dict) -> dict:
    result = {}
    for key in sorted(before.keys() & after.keys()):
        left, right = before[key], after[key]
        if isinstance(left, dict) and isinstance(right, dict):
            child = _numeric_deltas(left, right)
            if child:
                result[key] = child
        elif type(left) in (int, float) and type(right) in (int, float):
            result[key] = right - left
    return result


def compare_asc_pair(
    before: str | Path, after: str | Path, source: Mapping[str, Any], *,
    symbol_root: str | Path | None = None,
) -> dict[str, Any]:
    """Measure a pair and gate coverage, physical/electrical identity and topology.

    Raises EvidenceError when ownership cannot be established. Successfully
    measured pairs return ok=False with individual failed checks on drift.
    Source export runs once in memory; its ASC text/metrics are NOT evidence.
    """
    from tools import render_asc as renderer

    model = build_connectivity(dict(source))
    if model.has_errors:
        raise EvidenceError("Invalid source connectivity")
    expected = {group.name: [pin.key for pin in group.pins]
                for group in model.source_groups if group.pins}
    expected.update({f"unconnected:{pin.key}": [pin.key] for pin in model.unconnected_pins()})
    _, diagnostics, routed = generate_asc_with_routing(dict(source), strict=True)
    if routed is None or any(d.severity == "error" for d in diagnostics):
        raise EvidenceError("Cannot obtain source-routed ownership: " + "; ".join(
            d.format() for d in diagnostics if d.severity == "error"))
    root = renderer.detect_symbol_root(symbol_root)
    before, after = Path(before).resolve(), Path(after).resolve()
    left = measure_asc(before, routed.net_geometries, expected_groups=expected, symbol_root=root)
    right = measure_asc(after, routed.net_geometries, expected_groups=expected, symbol_root=root)
    left["netlist"], actual_before = _verify_existing_netlist(before, expected, root)
    right["netlist"], actual_after = _verify_existing_netlist(after, expected, root)
    baseline_groups = defaultdict(list)
    for pin, node in actual_before.items():
        baseline_groups[node.casefold()].append(pin)
    topology = compare_partitions(baseline_groups, actual_after).to_dict()
    checks = {f"{key}_unchanged": left[key] == right[key] for key in (
        "symbols", "pins", "flags", "iopins", "electrical_directives", "wire_coverage")}
    checks.update({
        "before_geometry_valid": not left["geometry_diagnostics"],
        "after_geometry_valid": not right["geometry_diagnostics"],
        "before_topology_matches_source": left["netlist"]["verification"]["ok"],
        "after_topology_matches_source": right["netlist"]["verification"]["ok"],
        "topology_unchanged": topology["ok"],
    })
    metric_keys = ("components", "wires", "file_bytes", "routing", "circuit_bbox",
                   "full_presentation_bbox", "labels", "wire_coverage_length")
    return {"ok": all(checks.values()), "checks": checks, "expected_nets": expected,
            "before": left, "after": right, "topology_comparison": topology,
            "delta": _numeric_deltas({key: left[key] for key in metric_keys},
                                     {key: right[key] for key in metric_keys})}


def report_markdown(report: dict) -> str:
    """Human-readable measurements and definitions, not a visual sign-off."""
    lines = ["# Phase 8 measurement evidence", "",
             f"Invariant checks: **{'PASS' if report['ok'] else 'FAIL'}**", "",
             "No PDF, native-rendering, or visual acceptance claim is made.", "",
             "Values are before -> after. Full presentation bounds are renderer estimates.", "",
             "| Circuit | Components | WIRE records | Length | Bends | Junctions | Bytes | Checks |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for record in report["circuits"]:
        name = record["source_file"].replace("|", "\\|")
        if "before" not in record:
            lines.append(f"| {name} | - | - | - | - | - | - | FAIL |")
            continue
        a, b = record["before"], record["after"]
        pairs = [(a["components"], b["components"]), (a["wires"], b["wires"])]
        pairs += [(a["routing"][key], b["routing"][key])
                  for key in ("total_length", "bend_count", "junction_count")]
        pairs += [(a["file_bytes"], b["file_bytes"])]
        cells = " | ".join(f"{x} -> {y}" for x, y in pairs)
        lines.append(f"| {name} | {cells} | {'PASS' if record['ok'] else 'FAIL'} |")
    for record in report["circuits"]:
        lines += ["", f"## {record['source_file']}", ""]
        if "error" in record:
            lines.append(f"Failed evidence collection: {record['error']}")
            continue
        a, b = record["before"], record["after"]
        for title, key in (("Circuit", "circuit_bbox"), ("Full presentation estimate", "full_presentation_bbox")):
            lines.append(f"- {title} bbox: `{a[key]['bounds']}` -> `{b[key]['bounds']}`; "
                         f"area {a[key]['area']} -> {b[key]['area']}.")
        lines.append(f"- SHEET: `{a['sheet']}` -> `{b['sheet']}`.")
        lines.append(f"- Coverage length: {a['wire_coverage_length']} -> {b['wire_coverage_length']}.")
        lines.append(f"- Label counts: `{json.dumps(a['labels'], sort_keys=True)}` -> "
                     f"`{json.dumps(b['labels'], sort_keys=True)}`.")
        lines.append("- Failed checks: " + (", ".join(k for k, ok in record["checks"].items() if not ok) or "none") + ".")
        lines.append("- Native .net source/partition verification and exact input hashes are in the JSON report.")
    lines += ["", "## Definitions and limitations", ""]
    lines.extend(f"- **{key}**: {value}" for key, value in report["definitions"].items())
    return "\n".join(lines) + "\n"


def export_report(
    before: str | Path, after: str | Path, output: str | Path, *,
    sources: Iterable[str | Path] | None = None, symbol_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write polish_report.json/.md only to output; return report (check ok).

    Missing after files/netlists or drift produce failed records, not fabricated
    comparisons or skipped passes. Input ASC/net/source files are never written.
    """
    before, after, output = (Path(path).resolve() for path in (before, after, output))
    if output.is_relative_to(before) or output.is_relative_to(after):
        raise EvidenceError("Report output must be outside before/after input directories")
    paths = [Path(path).resolve() for path in (default_sources() if sources is None else sources)]
    if not paths or len({path.stem for path in paths}) != len(paths):
        raise EvidenceError("Need nonempty source mapping with unique file stems")
    records = []
    for path in paths:
        record = {"source_file": path.name, "source_path": str(path)}
        try:
            record["source_sha256"] = _sha256(path)
            source = json.loads(path.read_text(encoding="utf-8-sig"))
            record["circuit"] = source.get("name", path.stem)
            record.update(compare_asc_pair(before / f"{path.stem}.asc", after / f"{path.stem}.asc",
                                           source, symbol_root=symbol_root))
        except (OSError, ValueError, RuntimeError) as error:
            record.update(ok=False, error=str(error))
        records.append(record)
    report = {"schema_version": 1, "phase": 8, "measurement_only": True,
              "ok": all(record["ok"] for record in records),
              "before_directory": str(before), "after_directory": str(after),
              "definitions": DEFINITIONS, "circuits": records}
    output.mkdir(parents=True, exist_ok=True)
    (output / "polish_report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "polish_report.md").write_text(report_markdown(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, default=PHASE_ROOT / "before")
    parser.add_argument("--after", type=Path, default=PHASE_ROOT / "after")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--circuit", type=Path, action="append")
    parser.add_argument("--symbol-root", type=Path)
    args = parser.parse_args(argv)
    try:
        report = export_report(args.before, args.after, args.output,
                               sources=args.circuit, symbol_root=args.symbol_root)
    except (OSError, ValueError) as error:
        parser.exit(2, f"export_polish_report: {error}\n")
    for record in report["circuits"]:
        failures = record.get("error") or ", ".join(key for key, ok in record["checks"].items() if not ok)
        print(f"{record['source_file']}: {'PASS' if record['ok'] else 'FAIL'}" +
              (f" — {failures}" if failures else ""))
    print(f"Measurement artifacts: {args.output.resolve()}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

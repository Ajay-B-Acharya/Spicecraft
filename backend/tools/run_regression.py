"""Semantic circuit regression and compiler-to-export validation; never simulate.

Golden data references existing circuit files, not duplicate circuit definitions.
Outputs are written only into a new/empty directory. Missing native verification
is REVIEW unless --require-ltspice is requested; image differences never fail.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
# Existing independent stock-ASY oracle; not a second production pin resolver.
sys.path.insert(0, str(BACKEND / "tests"))

from app.services.asc_validation import ERROR
from app.services.connectivity import build_connectivity, validate_connectivity
from app.services.ltspice_exporter import generate_asc_with_routing, place_components
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, resolve_component_kind
from app.services.regression_validation import (
    canonical_topology, compare_metrics, compare_topology, parse_asc_semantics, validate_routing,
)
from app.services.routing.metrics import measure_routing
from test_pin_geometry import parse_asc, pin_world_positions
from test_routing_fixtures import asc_pin_nodes
from tools.verify_ltspice import (
    compare_partitions, discover_ltspice_executable, parse_netlist,
    read_ltspice_text, run_ltspice_netlist,
)

GOLDEN = BACKEND / "tests/fixtures/regression/golden.json"
CATEGORIES = ("compiler", "electrical", "routing", "export", "ltspice", "visual")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def status(values):
    values = list(values)
    return "FAIL" if "FAIL" in values else ("REVIEW" if not values or "REVIEW" in values else "PASS")


def diagnostic(code, error, circuit="", **context):
    return {"code": code, "error": error, "severity": "error", "circuit": circuit, **context}


def source_groups(model):
    groups = {net.name: sorted(pin.key for pin in net.pins) for net in model.nets}
    groups.update({f"unwired:{pin.key}": [pin.key] for pin in model.unconnected_pins()})
    return groups


def node_groups(nodes):
    result = defaultdict(list)
    for pin, node in nodes.items():
        result[str(node)].append(pin)
    return dict(result)


def load_dataset(path=GOLDEN):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    expected_paths = {item["source"] for item in data["circuits"]}
    found = {p.relative_to(ROOT).as_posix() for directory in
             (BACKEND / "circuits", BACKEND / "tests/fixtures/routing") for p in directory.glob("*.json")}
    if expected_paths != found:
        raise ValueError(f"Regression inventory mismatch; uncovered={sorted(found-expected_paths)}, missing={sorted(expected_paths-found)}")
    return data


def library_diagnostics(dataset):
    actual = {kind: {"symbol": definition.symbol, "pins": [
        {"id": pin.id, "name": pin.name, "coordinate": [pin.x, pin.y], "orientation": pin.orientation.value}
        for pin in definition.pins]} for kind, definition in COMPONENT_LIBRARY.items()}
    if actual == dataset["library"]:
        return []
    return [diagnostic("LIBRARY_CONTRACT_DRIFT", "Canonical pin names, IDs, counts, coordinates, orientation or symbol changed; review the controlled library contract", expected=dataset["library"], actual=actual)]


def compile_fixtures(entries):
    request = {"circuits": [{"key": entry["key"], "input": json.loads((ROOT / entry["source"]).read_text(encoding="utf-8"))}
                             for entry in entries]}
    result = subprocess.run(["node", str(ROOT / "frontend/tools/compile-regression.cjs")],
                            input=json.dumps(request), text=True, encoding="utf-8", capture_output=True,
                            cwd=ROOT, timeout=120)
    if result.returncode:
        raise ValueError(f"Compiler bridge failed ({result.returncode}): {result.stderr or result.stdout}")
    parsed = json.loads(result.stdout)
    return {item["key"]: item for item in parsed["circuits"]}, parsed.get("coverage", {})


def _component_contract(source):
    return {str(c.get("reference") or c.get("id")): {
        "kind": resolve_component_kind(c), "symbol": COMPONENT_LIBRARY[resolve_component_kind(c)].symbol,
        "value": str(c["value"]) if c.get("value") is not None else None,
    } for c in source["components"]}


def _serialized_contract(semantic):
    return {c["reference"]: {"kind": c["kind"], "symbol": c["symbol"], "value": c["value"]}
            for c in semantic["components"]}


def validate_case(entry, dataset, output, compiled=None, *, samples=3, require_ltspice=False, executable=None):
    name = entry["name"]
    result = {"key": entry["key"], "circuit": name, "source": entry["source"],
              "categories": {key: "REVIEW" for key in CATEGORIES}, "diagnostics": [], "reviews": []}
    issues = result["diagnostics"]
    source = json.loads((ROOT / entry["source"]).read_text(encoding="utf-8"))
    snapshot = json.dumps(source, sort_keys=True)
    result["source_sha256"] = digest(ROOT / entry["source"])
    if result["source_sha256"] != entry["source_sha256"]:
        result["reviews"].append({"code": "SOURCE_REVISION", "error": "Source file changed; semantic checks still apply, review controlled reference provenance", "severity": "review"})
    if compiled is not None:
        result["compiler"] = compiled
        if not compiled.get("valid") or compiled.get("backend") is None:
            issues.extend(compiled.get("diagnostics", []))
            result["categories"]["compiler"] = "FAIL"
            result["overall"] = "FAIL"
            return result
        backend_source = compiled["backend"]
        result["categories"]["compiler"] = "PASS"
    else:
        backend_source = source
        result["compiler"] = {"status": "REVIEW", "reason": "Explicit export-only mode; compiler chain not exercised"}
    backend_snapshot = json.dumps(backend_source, sort_keys=True)
    model = build_connectivity(backend_source)
    issues.extend(asdict(d) for d in validate_connectivity(model) if d.severity == ERROR)
    expected = entry["topology"]
    produced = source_groups(model)
    issues.extend(compare_topology(expected, produced, circuit=name))
    labels = {net.name: sorted(net.labels) for net in model.nets if net.labels}
    issues.extend(compare_topology(expected, produced, preserve_labels=True,
                                   expected_labels=entry["labels"], actual_labels=labels, circuit=name))
    components = _component_contract(backend_source)
    if components != entry["components"]:
        issues.append(diagnostic("COMPONENT_CONTRACT_DRIFT", "Compiler/backend component identity, kind, symbol or value differs from source contract", name, expected=entry["components"], actual=components))
    result["connectivity"] = {"groups": produced, "canonical_topology": canonical_topology(produced),
                              "labels": labels, "components": components,
                              "required_pins": entry["required_pins"], "optional_unwired_pins": entry["optional_unwired_pins"]}
    if compiled is not None:
        frontend_groups = {net["id"]: net["pins"] for net in compiled["topology"]}
        connected = {pin for pins in frontend_groups.values() for pin in pins}
        mapping = {item["compiled_id"]: item["backend_id"] for item in compiled["identity_mapping"]}
        for component in compiled["components"]:
            reference = mapping[component["id"]]
            expected_ids = {p["id"] for p in dataset["library"][components[reference]["kind"]]["pins"]}
            actual_ids = [p["id"] for p in component["pins"]]
            if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
                issues.append(diagnostic("COMPILER_PIN_MISMATCH", "Compiler and backend canonical pin IDs/count differ", name,
                                         component=reference, expected=sorted(expected_ids), actual=actual_ids))
            for pin in actual_ids:
                key = f"{reference}.{pin}"
                if key not in connected:
                    frontend_groups[f"unwired:{key}"] = [key]
        issues.extend(compare_topology(expected, frontend_groups, preserve_labels=True,
                                       expected_labels=entry["labels"],
                                       actual_labels={net["id"]: net["labels"] for net in compiled["topology"]}, circuit=name))
        result["connectivity"]["compiler_groups"] = frontend_groups
    result["categories"]["electrical"] = "FAIL" if issues else "PASS"
    if issues:
        result["overall"] = "FAIL"
        return result
    timings = []
    first_asc = None
    first_route = None
    for _ in range(samples):
        started = time.perf_counter()
        asc, export_diagnostics, routed = generate_asc_with_routing(backend_source, strict=True)
        timings.append((time.perf_counter() - started) * 1000)
        failures = [asdict(d) for d in export_diagnostics if d.severity == ERROR]
        if failures or not asc or routed is None:
            issues.extend(failures or [diagnostic("EMPTY_EXPORT", "Exporter did not return usable ASC and geometry", name)])
            result["categories"]["export"] = "FAIL"
            result["overall"] = "FAIL"
            return result
        route_signature = [(n.name, sorted((s.start, s.end) for s in n.segments), sorted(n.flags)) for n in routed.net_geometries]
        if first_asc is not None and (asc != first_asc or route_signature != first_route):
            issues.append(diagnostic("NONDETERMINISTIC_EXPORT", "Repeated identical inputs differ in routing or ASC", name))
        first_asc, first_route = asc, route_signature
    result["performance"] = {"samples_ms": timings, "min_ms": min(timings), "median_ms": statistics.median(timings),
                             "max_ms": max(timings), "components": len(components),
                             "size_class": "small" if len(components) <= 2 else "available-multi-component",
                             "scope": "Backend connectivity/layout/routing/cleanup/export; compiler duration reported separately"}
    semantic = parse_asc_semantics(asc, name)
    issues.extend(semantic["diagnostics"])
    if _serialized_contract(semantic) != entry["components"]:
        issues.append(diagnostic("SERIALIZED_COMPONENT_DRIFT", "ASC symbols, references or values differ from controlled source contract", name,
                                 expected=entry["components"], actual=_serialized_contract(semantic)))
    layouts = place_components(backend_source["components"], model)
    symbols, wires, flags = parse_asc(asc)
    expected_wires = Counter(tuple(sorted((segment.start, segment.end)))
                             for net in routed.net_geometries for segment in net.segments)
    if Counter(tuple(sorted(wire)) for wire in wires) != expected_wires:
        issues.append(diagnostic("SERIALIZED_WIRE_MISMATCH", "ASC wires disagree with validated routing geometry", name))
    expected_flags = Counter((flag.point, flag.name) for flag in routed.flags)
    if Counter(flags) != expected_flags:
        issues.append(diagnostic("SERIALIZED_LABEL_MISMATCH", "ASC electrical label names or anchors differ from validated net metadata", name,
                                 expected=list(expected_flags), actual=flags))
    independently_resolved = pin_world_positions(symbols)
    parser_pins = {f"{comp['reference']}.{pin}": point for comp in semantic["components"] for pin, point in comp["pins"].items()}
    expected_pins = {pin for pins in expected.values() for pin in pins}
    if set(parser_pins) != expected_pins:
        issues.append(diagnostic("PIN_SET_MISMATCH", "ASC canonical pins differ from expected definition pins", name,
                                 expected=sorted(expected_pins), actual=sorted(parser_pins)))
    pin_report = {}
    for reference, contract in entry["components"].items():
        definition = COMPONENT_LIBRARY[contract["kind"]]
        layout = layouts[reference]
        for pin in definition.pins:
            resolved = PinResolver.resolve_pin_geometry(definition, pin.id, layout["_ltspice_anchor"], layout["_ltspice_rotation"], layout["_ltspice_mirror"])
            key = f"{reference}.{pin.id}"
            expected_coordinate = independently_resolved.get((reference, pin.id))
            actual_coordinate = parser_pins.get(key)
            pin_report[key] = {"name": pin.name, "local": [pin.x, pin.y], "absolute": list(resolved.absolute), "orientation": resolved.facing.value,
                               "net": next((net for net, pins in produced.items() if key in pins), None)}
            if actual_coordinate != list(resolved.absolute) or expected_coordinate != resolved.absolute:
                issues.append(diagnostic("PIN_COORDINATE_MISMATCH", "Library/resolver/layout/ASC and independent ASY coordinates disagree", name,
                                         component=reference, pin=pin.id, expected=expected_coordinate, actual=actual_coordinate))
    actual_nodes = asc_pin_nodes(symbols, wires, flags)
    partition = compare_partitions(expected, actual_nodes)
    result["portable_electrical"] = partition.to_dict()
    if not partition.ok:
        issues.extend(compare_topology(expected, node_groups(actual_nodes), circuit=name))
        result["categories"]["electrical"] = "FAIL"
    result["pins"] = pin_report
    route_issues = validate_routing(model, layouts, routed, circuit=name)
    issues.extend(route_issues)
    result["categories"]["routing"] = "FAIL" if route_issues else "PASS"
    metrics = measure_routing(routed.net_geometries, layouts, routed.crossings)
    result["metrics"] = metrics
    result["reviews"].extend(compare_metrics(entry["routing_metrics"], metrics, thresholds=dataset["metric_thresholds"], circuit=name))
    result["metrics_baseline"] = entry["routing_metrics"]
    result["categories"]["export"] = "FAIL" if issues else "PASS"
    if json.dumps(source, sort_keys=True) != snapshot or json.dumps(backend_source, sort_keys=True) != backend_snapshot:
        issues.append(diagnostic("SOURCE_MUTATED", "Pipeline modified original fixture or compiler-derived export input", name))
    result["counts"] = {"components": len(components), "pins": len(parser_pins), "electrical_groups": len(produced), "wired_nets": len(model.nets), "flags": len(flags)}
    result["deterministic"] = not any(d["code"] == "NONDETERMINISTIC_EXPORT" for d in issues)
    if issues:
        result["overall"] = "FAIL"
        return result
    asc_path = output / f"{entry['key']}.asc"
    asc_path.write_text(asc, encoding="utf-8", newline="\n")
    result["asc"] = str(asc_path)
    result["asc_sha256"] = digest(asc_path)
    if executable is not None:
        try:
            net = run_ltspice_netlist(asc_path, output, executable=executable)
            native_pins = parse_netlist(asc, read_ltspice_text(net))
            native = compare_partitions(expected, native_pins)
            result["ltspice"] = {"status": "PASS" if native.ok else "FAIL", "netlist": str(net), "sha256": digest(net),
                                 "pin_nodes": native_pins, "comparison": native.to_dict(), "simulation": False}
            result["categories"]["ltspice"] = result["ltspice"]["status"]
            if not native.ok:
                issues.extend(compare_topology(expected, node_groups(native_pins), circuit=name))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            result["categories"]["ltspice"] = "FAIL"
            issues.append(diagnostic("LTSPICE_VALIDATION_FAILED", str(exc), name))
    else:
        result["categories"]["ltspice"] = "FAIL" if require_ltspice else "REVIEW"
        result["ltspice"] = {"status": result["categories"]["ltspice"], "reason": "LTspice executable unavailable; not counted as a validation pass"}
    result["overall"] = "FAIL" if issues else status(result["categories"].values())
    return result


def visual_evidence(records, entries, output, *, render=False, native=False, executable=None):
    comparisons = []
    for record, entry in zip(records, entries):
        if not record.get("asc"):
            continue
        item = {"key": record["key"], "status": "REVIEW", "baseline": str(ROOT / entry["visual_reference"]),
                "baseline_sha256": entry["visual_sha256"], "asc_sha256": record["asc_sha256"],
                "reason": "Requires human inspection; image differences are not a failure criterion"}
        try:
            if digest(item["baseline"]) != item["baseline_sha256"]:
                raise ValueError("Controlled visual reference hash changed; review the reference dataset")
            if render:
                from tools.render_asc import render_asc
                image = output / f"{record['key']}.png"
                rendered = render_asc(record["asc"], image, heading=f"Phase 9 — {record['circuit']}", include_description=True)
                item["render"] = str(image)
                item["render_dimensions"] = [rendered.width, rendered.height]
            if native:
                if executable is None or os.name != "nt":
                    item["reason"] = "Native LTspice capture unavailable on this host; visual review remains pending"
                else:
                    from tools.capture_ltspice import capture_one
                    capture = capture_one(Path(record["asc"]), executable, output / "native")
                    if capture["status"] != "captured_not_visually_reviewed" or not capture.get("inspection_copy_unchanged"):
                        raise ValueError(f"Native open/capture failed: {capture.get('error', capture['status'])}")
                    item["native"] = capture["screenshot"]
                    item["native_sha256"] = digest(capture["screenshot"])
                    record["native_open"] = "PASS"
                    from PIL import Image, ImageDraw
                    before, after = Image.open(item["baseline"]).convert("RGB"), Image.open(item["native"]).convert("RGB")
                    canvas = Image.new("RGB", (max(before.width, after.width), before.height + after.height + 64), "white")
                    draw = ImageDraw.Draw(canvas)
                    draw.text((12, 8), "Phase 8 reference (top) / Phase 9 current (bottom) — REVIEW", fill="black")
                    canvas.paste(before, (0, 32))
                    canvas.paste(after, (0, before.height + 64))
                    comparison = output / f"{record['key']}_comparison.png"
                    canvas.save(comparison)
                    item["comparison"] = str(comparison)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            item.update(status="FAIL", reason=str(exc))
            record["categories"]["visual"] = "FAIL"
            record["diagnostics"].append(diagnostic("VISUAL_EVIDENCE_FAILED", str(exc), record["circuit"]))
        record["visual"] = item
        comparisons.append(item)
    return comparisons


def write_report(report, output):
    (output / "regression_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# SpiceCraft circuit regression report", "", f"Overall: **{report['overall']}**", "",
             "| Circuit | Components | Pins | Groups | Electrical | Routing | Export | LTspice | Visual |",
             "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |"]
    for record in report["circuits"]:
        counts = record.get("counts", {})
        categories = record["categories"]
        values = [record["circuit"], *[str(counts.get(k, "—")) for k in ("components", "pins", "electrical_groups")],
                  *[categories[k] for k in ("electrical", "routing", "export", "ltspice", "visual")]]
        lines.append("| " + " | ".join(values) + " |")
    for record in report["circuits"]:
        lines += ["", f"## {record['circuit']}", ""]
        if "metrics" in record:
            metrics, timing = record["metrics"], record["performance"]
            lines.append(f"Wire length **{metrics['total_length']}**, segments **{metrics['segment_count']}**, bends **{metrics['bend_count']}**, junctions **{metrics['junction_count']}**, crossings **{metrics['crossing_count']}**.")
            lines.append(f"Bounding box: `{metrics['bounding_box']}`; routing efficiency: **{metrics['routing_efficiency']:.4f}**.")
            lines.append(f"Generation time (min / median / max): **{timing['min_ms']:.3f} / {timing['median_ms']:.3f} / {timing['max_ms']:.3f} ms**, {len(timing['samples_ms'])} samples. Raw measurements and complete connectivity are in the JSON report.")
        for diagnostic_record in record["diagnostics"] + record.get("reviews", []):
            lines.append("- `" + json.dumps(diagnostic_record, ensure_ascii=False) + "`")
        if record.get("visual", {}).get("comparison"):
            lines.append(f"[Visual comparison]({Path(record['visual']['comparison']).name}) — {record['categories']['visual']}.")
    lines += ["", "## Coverage and limitations", "",
              "Backend component kinds covered: " + ", ".join(report["coverage"]["covered_backend_kinds"]) + ".",
              "Special connections: " + ", ".join(report["coverage"]["specials"]) + ".",
              "Unsupported backend features (not counted as passing component coverage): " + ", ".join(report["coverage"]["unsupported_backend"]) + ".", "",
              "No simulation or live AI network request is performed. Fixture input invokes the real frontend compiler through a test-only export-contract adapter. Golden comparison is semantic, not ASC byte equality. Repeated identical input must still be deterministic.",
              "", "Only 2–6-component source fixtures are available; large-circuit scalability is unverified. Metric growth requires review, not automatic failure. Visual acceptance requires explicit review bound to current export/image hashes."]
    (output / "regression_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def fresh_output(export_only=False):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    family = "export-validation" if export_only else "regression"
    return BACKEND / "tests/artifacts" / family / f"{stamp}-{os.getpid()}"


def run_suite(output=None, *, samples=3, require_ltspice=False, render=False, native=False, export_only=False, golden=GOLDEN):
    requested = Path(output) if output is not None else fresh_output(export_only)
    if any(part.is_symlink() for part in (requested.absolute(), *requested.absolute().parents)):
        raise ValueError("Output must not traverse a symbolic link")
    output = requested.resolve()
    if not 1 <= samples <= 20:
        raise ValueError("samples must be between 1 and 20")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be new or empty; stale evidence is never reused")
    dataset = load_dataset(golden)
    output.mkdir(parents=True, exist_ok=True)
    entries = dataset["circuits"]
    library_errors = library_diagnostics(dataset)
    compiled, coverage = {}, {}
    compile_error = None
    if not export_only:
        try:
            compiled, coverage = compile_fixtures(entries)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            compile_error = str(exc)
    executable = discover_ltspice_executable()
    records = []
    for entry in entries:
        try:
            if compile_error or (not export_only and entry["key"] not in compiled):
                raise ValueError(compile_error or f"Compiler response missing {entry['key']}")
            record = validate_case(entry, dataset, output, compiled.get(entry["key"]), samples=samples,
                                   require_ltspice=require_ltspice, executable=executable)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            record = {"key": entry["key"], "circuit": entry["name"], "categories": {key: "FAIL" for key in CATEGORIES},
                      "diagnostics": [diagnostic("PIPELINE_EXCEPTION", f"{type(exc).__name__}: {exc}", entry["name"])], "reviews": [], "overall": "FAIL"}
        records.append(record)
    visuals = visual_evidence(records, entries, output, render=render, native=native, executable=executable)
    for record in records:
        record["overall"] = "FAIL" if record["diagnostics"] else status(record["categories"].values())
        if record["reviews"] and record["overall"] == "PASS":
            record["overall"] = "REVIEW"
    categories = {key: status(record["categories"][key] for record in records) for key in CATEGORIES}
    coverage.update({"backend_kinds": sorted(COMPONENT_LIBRARY), "covered_backend_kinds": sorted({c["kind"] for entry in entries for c in entry["components"].values()}),
                     "specials": ["ground FLAG 0", "VCC power labels", "VIN/VOUT and custom net labels"],
                     "unsupported_backend": ["voltage source", "current source", "AC/pulse source", "inductor", "potentiometer", "PNP", "MOSFET", "ground component"],
                     "fixture_count": len(entries), "fixture_component_range": [min(len(e["components"]) for e in entries), max(len(e["components"]) for e in entries)],
                     "large_fixture_available": False})
    report = {"schema_version": 1, "overall": "FAIL" if library_errors else status(categories.values()), "categories": categories,
              "library_diagnostics": library_errors, "coverage": coverage, "circuits": records, "visual_comparisons": visuals,
              "golden_sha256": digest(golden), "environment": {"python": sys.version, "platform": platform.platform(), "ltspice": str(executable) if executable else None},
              "performance": {r["key"]: r["performance"] for r in records if "performance" in r},
              "test_categories": {"unit": "test_regression_validation / test_verification_command", "integration": "test_pipeline_regression", "end_to_end": "compiler bridge -> backend -> serialized electrical check -> real LTspice", "export": "semantic ASC checks", "electrical": "controlled pin partitions", "routing": "geometry/collision/metrics", "visual": "native captures and non-gating image comparisons"}}
    if any(r["reviews"] for r in records) and report["overall"] == "PASS":
        report["overall"] = "REVIEW"
    write_report(report, output)
    return report


def accept_visual_review(output, verdicts, reviewer):
    """Record explicit per-circuit reviews bound to current ASC/native image bytes."""
    output = Path(output)
    report = json.loads((output / "regression_report.json").read_text(encoding="utf-8"))
    if set(verdicts) != {r["key"] for r in report["circuits"]}:
        raise ValueError("Review must cover every circuit")
    review = {"reviewer": reviewer, "circuits": []}
    for record in report["circuits"]:
        visual = record.get("visual", {})
        verdict = verdicts[record["key"]]
        if verdict["status"] not in {"PASS", "REVIEW", "FAIL"} or not verdict.get("evidence"):
            raise ValueError("Each review needs a status and evidence")
        if not visual.get("native") or digest(visual["native"]) != visual["native_sha256"] or digest(record["asc"]) != record["asc_sha256"]:
            raise ValueError("Review evidence is missing or stale")
        record["categories"]["visual"] = verdict["status"]
        record["visual"].update(review=verdict, status=verdict["status"])
        review["circuits"].append({"key": record["key"], **verdict, "asc_sha256": record["asc_sha256"], "native_sha256": visual["native_sha256"]})
        record["overall"] = status(record["categories"].values())
    report["categories"]["visual"] = status(v["status"] for v in verdicts.values())
    report["overall"] = "FAIL" if report["library_diagnostics"] else status(report["categories"].values())
    if any(r["reviews"] for r in report["circuits"]) and report["overall"] == "PASS":
        report["overall"] = "REVIEW"
    (output / "visual_review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    write_report(report, output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new/empty directory; default: fresh timestamped artifacts")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--require-ltspice", action="store_true")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args(argv)
    args.output = args.output or fresh_output(args.export_only)
    try:
        report = run_suite(args.output, samples=args.samples, require_ltspice=args.require_ltspice,
                           render=args.render, native=args.native, export_only=args.export_only)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"regression: {exc}\n")
    for record in report["circuits"]:
        print(f"{record['circuit']}: {record['overall']} {record['categories']}")
        for item in record["diagnostics"]:
            print(json.dumps(item, ensure_ascii=False))
    print(f"Overall: {report['overall']}; reports: {args.output.resolve()}")
    return 1 if report["overall"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

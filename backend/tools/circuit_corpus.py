"""Collect repository circuits and run isolated compiler/export scalability checks.

No source edits, native LTspice, simulation, or live API calls. New/empty output
folders are required. Invalid cases and incomplete stages remain in the report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time
import platform

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests/corpus")]
from fixture_generator import SIZES, python_definitions, scale_circuit
from tools.corpus_catalog import enrich_catalog, enrich_report, write_category_indexes

SCHEMA_VERSION = 1
STAGES = ("compile", "bridge", "connectivity", "route", "export", "serialized_validation")
DEPENDENCIES = {"node_modules", "venv", ".venv", ".git", "__pycache__", ".next", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".cjs", ".mjs", ".json", ".md", ".sql", ".yaml", ".yml"}
CANDIDATE = re.compile(r"\b(?:components|nodes|wires|circuit|template|example)\b", re.I)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def fresh_directory(path, purpose):
    path = Path(path) if path else BACKEND / "tests/corpus/runs" / (purpose + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"Output must be a new/empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def memory_reader(process):
    """Read OS resident memory without optional dependencies or heap tracing."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        query = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        class ProcessEntry(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                        ("szExeFile", wintypes.WCHAR * 260)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        snapshot = kernel.CreateToolhelp32Snapshot
        snapshot.argtypes, snapshot.restype = [wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE
        first, following = kernel.Process32FirstW, kernel.Process32NextW
        for function in (first, following):
            function.argtypes, function.restype = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL
        open_process = kernel.OpenProcess
        open_process.argtypes, open_process.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
        def read():
            handle = snapshot(2, 0)
            if handle == ctypes.c_void_p(-1).value:
                return None
            parents = {}
            try:
                entry = ProcessEntry()
                entry.dwSize = ctypes.sizeof(entry)
                ok = first(handle, ctypes.byref(entry))
                while ok:
                    parents[entry.th32ProcessID] = entry.th32ParentProcessID
                    ok = following(handle, ctypes.byref(entry))
            finally:
                close(handle)
            pids = {process.pid}
            while True:
                children = {pid for pid, parent in parents.items() if parent in pids}
                if children <= pids:
                    break
                pids.update(children)
            total, observed = 0, False
            for pid in pids:
                handle = open_process(0x410, False, pid)
                if not handle:
                    continue
                try:
                    counters = Counters()
                    counters.cb = ctypes.sizeof(counters)
                    if query(handle, ctypes.byref(counters), counters.cb):
                        total += counters.WorkingSetSize
                        observed = True
                finally:
                    close(handle)
            return total if observed else None
        return read, "Windows sampled sum of child-tree WorkingSetSize every 20ms; includes venv launcher descendants"
    if sys.platform.startswith("linux"):
        def read():
            try:
                text = Path(f"/proc/{process.pid}/status").read_text()
                match = re.search(r"^VmHWM:\s+(\d+) kB", text, re.M)
                return int(match[1]) * 1024 if match else None
            except OSError:
                return None
        return read, "Linux VmHWM sampled every 20ms; child only"
    return lambda: None, "unavailable on this platform"


def implementation_snapshot():
    paths = []
    for directory in (BACKEND / "app/services", ROOT / "frontend/lib/circuit", ROOT / "frontend/tools", BACKEND / "tests/corpus"):
        paths.extend(path for path in directory.rglob("*") if path.suffix in {".py", ".ts", ".cjs"} and "runs" not in path.parts)
    paths.extend(BACKEND / path for path in ("tools/circuit_corpus.py", "tools/corpus_catalog.py", "tools/verify_ltspice.py", "tests/test_pin_geometry.py", "tests/test_routing_fixtures.py"))
    sources = {path.relative_to(ROOT).as_posix(): sha(path.read_bytes()) for path in sorted(set(paths))}
    return {"sha256": sha(canonical(sources).encode()), "sources": sources}


def run_process(command, *, timeout, cwd=ROOT, input_text=None, env=None):
    """Kill descendants on timeout; the compiler and export never share a process."""
    started = time.perf_counter()
    kwargs = {"start_new_session": True} if os.name != "nt" else {}
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", **kwargs)
    expired = False
    read_memory, memory_method = memory_reader(process)
    measurements = []
    stopped = threading.Event()
    def measure():
        while not stopped.is_set():
            value = read_memory()
            if value is not None:
                measurements.append(value)
            stopped.wait(0.02)
    sampler = threading.Thread(target=measure, daemon=True)
    sampler.start()
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        expired = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
        process.kill()
        stdout, stderr = process.communicate()
    finally:
        stopped.set()
        sampler.join(timeout=1)
    return {"returncode": process.returncode, "timeout": expired, "stdout": stdout, "stderr": stderr,
            "memory": {"peak_rss_bytes": max(measurements) if measurements else None,
                       "method": memory_method, "observations": len(measurements)},
            "wall_ms": (time.perf_counter() - started) * 1000}


def circuit_body(value):
    if not isinstance(value, dict):
        return {}
    if isinstance(value.get("circuit"), dict):
        return value["circuit"]
    if isinstance(value.get("data"), dict) and isinstance(value["data"].get("circuit"), dict):
        return value["data"]["circuit"]
    return value


def input_counts(value):
    body = circuit_body(value)
    def count(*keys):
        for key in keys:
            if key in body:
                return len(body[key]) if isinstance(body[key], list) else None
        return 0
    return {"components": count("components", "nodes"), "connections": count("wires", "connections", "edges"),
            "pins": None, "nets": None}


def json_circuits(value, pointer="$"):
    if isinstance(value, dict):
        body = circuit_body(value)
        if any(key in body for key in ("components", "nodes")) and (isinstance(body.get("components", body.get("nodes")), list)
                                                                          or any(key in body for key in ("wires", "edges"))):
            yield pointer, value
            return
        for key in sorted(value):
            yield from json_circuits(value[key], f"{pointer}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from json_circuits(item, f"{pointer}[{index}]")


def inventory(root=ROOT, excluded=()):
    """Enumerate source and evidence first; dependencies are pruned, not circuits."""
    root = Path(root).resolve()
    excluded = {Path(path).resolve() for path in excluded}
    evidence = []
    for directory, dirs, files in os.walk(root):
        directory = Path(directory)
        for name in sorted(dirs):
            path = directory / name
            if name in DEPENDENCIES or path.resolve() in excluded or path.is_symlink() or path == root / "backend/tests/corpus/runs":
                evidence.append({"source": path.relative_to(root).as_posix(), "kind": "excluded_directory",
                                 "reason": "dependency/cache/output/symlink; not a source circuit"})
        dirs[:] = sorted(name for name in dirs if name not in DEPENDENCIES and (directory / name).resolve() not in excluded
                         and not (directory / name).is_symlink() and directory / name != root / "backend/tests/corpus/runs")
        for name in sorted(files):
            path = directory / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                continue
            artifact = "/artifacts/" in relative or path.suffix in {".asc", ".net", ".log", ".png", ".pdf", ".pyc", ".tsbuildinfo"}
            own = relative.startswith("backend/tests/corpus/") or relative in {
                "backend/tools/circuit_corpus.py", "backend/tools/corpus_catalog.py",
                "backend/tests/test_circuit_corpus.py", "backend/tests/test_corpus_catalog.py"}
            if artifact or own:
                record = {"source": relative, "kind": "generated_evidence" if artifact else "corpus_tooling",
                          "reason": "not an original source circuit"}
                if path.suffix == ".json":
                    raw = path.read_bytes()
                    record["sha256"] = sha(raw)
                    try:
                        record["circuit_shaped_pointers"] = [pointer for pointer, _ in json_circuits(json.loads(raw))]
                    except (ValueError, UnicodeError):
                        record["json_status"] = "invalid_json"
                evidence.append(record)
                continue
            if path.suffix not in TEXT_SUFFIXES:
                continue
            raw = path.read_bytes()
            item = {"source": relative, "sha256": sha(raw), "kind": "source", "candidate_lines": []}
            try:
                text = raw.decode("utf-8-sig")
                item["candidate_lines"] = [index for index, line in enumerate(text.splitlines(), 1) if CANDIDATE.search(line)]
            except UnicodeError:
                item["kind"] = "unreadable_source"
            evidence.append(item)
    return sorted(evidence, key=lambda item: item["source"])


def collect_circuits(output=None, *, root=ROOT, include_synthetic=True, timeout=30):
    root = Path(root).resolve()
    output = fresh_directory(output, "collection")
    evidence = inventory(root, (output,))
    # Freeze the repository inventory before adding scale fixtures.
    write_json(output / "inventory.json", {"schema_version": SCHEMA_VERSION, "sources": evidence})
    cases, extraction = {}, []
    fixtures = {}
    for item in evidence:
        source = item["source"]
        if item["kind"] == "source" and source.endswith(".json") and (source.startswith("backend/circuits/") or source.startswith("backend/tests/fixtures/routing/")):
            try:
                fixtures[Path(source).name] = json.loads((root / source).read_text(encoding="utf-8-sig"))
            except ValueError:
                pass

    def add(value, source, locator, kind):
        digest = sha(canonical(value).encode())
        key = "circuit-" + digest[:20]
        origin = {"source": source, "locator": locator, "kind": kind,
                  "source_sha256": next((item.get("sha256") for item in evidence if item["source"] == source), None)}
        if key not in cases:
            body = circuit_body(value)
            cases[key] = {"id": key, "name": str(body.get("name") or f"{Path(source).name}:{locator}"),
                          "sha256": digest, "input": f"inputs/{key}.json", "origins": [],
                          "counts": input_counts(value), "support": "not_tested", "validation": "not_tested",
                          "synthetic": kind == "synthetic"}
            write_json(output / cases[key]["input"], value)
        if origin not in cases[key]["origins"]:
            cases[key]["origins"].append(origin)

    for item in evidence:
        if item["kind"] != "source":
            continue
        source = item["source"]
        path = root / source
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix == ".json":
            try:
                value = json.loads(text)
                captured = 0
                for pointer, circuit in json_circuits(value):
                    if source == "backend/tests/fixtures/regression/golden.json":
                        continue
                    add(circuit, source, pointer, "json")
                    captured += 1
                extraction.append({"source": source, "method": "json", "status": "complete", "captured": captured,
                                   "reason": "controlled golden contract, not source input" if source.endswith("regression/golden.json") else None})
            except (ValueError, TypeError) as exc:
                extraction.append({"source": source, "status": "invalid_json", "error": str(exc)})
        elif path.suffix == ".py" and item["candidate_lines"]:
            try:
                values, unresolved = python_definitions(text, fixtures)
                for value in values:
                    add(value["input"], source, f"line:{value['line']}", "python_data_expression")
                extraction.append({"source": source, "status": "partial" if unresolved else "complete",
                                   "captured": len(values), "unresolved": unresolved})
            except (SyntaxError, ValueError) as exc:
                extraction.append({"source": source, "status": "extraction_failed", "error": str(exc)})
        elif path.suffix == ".md":
            for match in re.finditer(r"```(?:json|javascript|js)?\s*\n([\s\S]*?)```", text):
                try:
                    for pointer, value in json_circuits(json.loads(match[1])):
                        add(value, source, f"line:{text[:match.start()].count(chr(10))+1}:{pointer}", "documentation")
                except ValueError:
                    pass

    frontend_sources = [{"source": item["source"], "text": (root / item["source"]).read_text(encoding="utf-8-sig")}
                        for item in evidence if item["kind"] == "source" and item["source"].startswith("frontend/")
                        and Path(item["source"]).suffix in {".ts", ".tsx", ".js", ".cjs", ".mjs"}]
    if frontend_sources:
        static = run_process(["node", str(BACKEND / "tests/corpus/capture_frontend.cjs"), "--static"],
                             input_text=json.dumps(frontend_sources), timeout=timeout, cwd=root)
        if static["timeout"] or static["returncode"]:
            extraction.append({"source": "frontend/*", "method": "typescript_ast", "status": "extraction_failed",
                               "error": static["stderr"], "timeout": static["timeout"]})
        else:
            for item in json.loads(static["stdout"]):
                for value in item["found"]:
                    add(value["input"], item["source"], f"line:{value['line']}", "frontend_data_expression")
                extraction.append({"source": item["source"], "method": "typescript_ast",
                                   "status": "partial" if item["unresolved"] else "complete",
                                   "captured": len(item["found"]), "unresolved": item["unresolved"]})

    for item in evidence:
        source = item["source"]
        if item["kind"] != "source" or not source.startswith("frontend/tests/") or not source.endswith((".test.cjs", ".test.js", ".test.ts")):
            continue
        capture = output / "extraction" / (Path(source).name + ".jsonl")
        capture.parent.mkdir(exist_ok=True)
        env = dict(os.environ, CIRCUIT_CORPUS_CAPTURE=str(capture), CIRCUIT_CORPUS_SOURCE=Path(source).name)
        result = run_process(["node", "--require", str(BACKEND / "tests/corpus/capture_frontend.cjs"), "--test", str(root / source)],
                             timeout=timeout, cwd=root, env=env)
        captured, errors = 0, []
        if capture.exists():
            for line in capture.read_text(encoding="utf-8").splitlines():
                value = json.loads(line)
                if "input" in value:
                    add(value["input"], source, f"line:{value['line']}", "frontend_runtime")
                    captured += 1
                else:
                    errors.append(value)
        # Logs are evidence, not part of the deterministic catalog.
        (capture.with_suffix(".log")).write_text(result["stdout"] + result["stderr"], encoding="utf-8")
        extraction.append({"source": source, "status": "timeout" if result["timeout"] else "complete" if result["returncode"] == 0 else "tests_failed",
                           "captured": captured, "capture_errors": errors, "returncode": result["returncode"]})
    real_count = len(cases)
    if include_synthetic:
        for family in ("resistor", "filter"):
            for size in SIZES:
                value = scale_circuit(size, family)
                add(value, "backend/tests/corpus/fixture_generator.py", f"{family}:{size}", "synthetic")
                case = cases["circuit-" + sha(canonical(value).encode())[:20]]
                case["family"], case["target_components"] = family, size
    for case in cases.values():
        case["origins"].sort(key=canonical)
    catalog = {"schema_version": SCHEMA_VERSION, "inventory": "inventory.json", "inventory_sha256": sha(canonical(evidence).encode()),
               "cases": sorted(cases.values(), key=lambda case: (case["synthetic"], case.get("target_components", 0), case["id"])),
               "extraction": extraction, "summary": {"repository_cases": real_count, "synthetic_cases": len(cases) - real_count,
                                                        "total_cases": len(cases), "evidence_sources": len(evidence)},
               "limitations": ["All repository source paths are inventoried; unresolved Python expressions are retained, not claimed as runnable circuits.",
                               "Frontend test inputs are observed at the real compiler boundary; post-compile mutation tests are evidence, not additional source circuits.",
                               "Counts of pins/nets and support/validation are unknown until the actual compiler runs.",
                               "Content-identical inputs are deduplicated without removing provenance; artifacts/dependencies are never promoted to circuits."]}
    catalog["summary"].update({
        "origins": sum(len(case["origins"]) for case in cases.values()),
        "origins_by_kind": dict(sorted(Counter(origin["kind"] for case in cases.values() for origin in case["origins"]).items())),
        "source_files_with_collected_cases": len({origin["source"] for case in cases.values() for origin in case["origins"] if origin["kind"] != "synthetic"}),
        "extraction_status": dict(sorted(Counter(item["status"] for item in extraction).items())),
        "unresolved_expressions": sum(len(item.get("unresolved", [])) for item in extraction),
        "runtime_capture_errors": sum(len(item.get("capture_errors", [])) for item in extraction),
    })
    catalog["limitations"].append("Static expressions are conservative snapshots, not proof that a test branch executes; dynamic/non-JSON/accessor/cyclic inputs remain unresolved evidence.")
    catalog = enrich_catalog(catalog, output)
    write_json(output / "catalog.json", catalog)
    write_category_indexes(catalog, output, output / "indexes")
    return output, catalog


def empty_result(case):
    return {"id": case["id"], "name": case["name"], "synthetic": case.get("synthetic", False),
            "stages": {stage: "NOT_RUN" for stage in STAGES}, "timings_ms": {}, "memory": {}, "diagnostics": [],
            "counts": {"input": case["counts"], "compiled": None, "routed": None, "exported": None},
            "support": "unknown", "overall": "NOT_RUN"}


def diagnostic(code, error, stage):
    return {"code": code, "error": str(error), "stage": stage, "severity": "error"}


def backend_worker(compiled_path, result_path, asc_path):
    from app.services import ltspice_exporter as exporter
    from app.services.connectivity import build_connectivity, validate_connectivity
    from app.services.regression_validation import compare_topology, parse_asc_semantics, validate_routing
    from app.services.pin_maps import COMPONENT_LIBRARY, resolve_component_kind
    sys.path.insert(0, str(BACKEND / "tests"))
    from test_pin_geometry import parse_asc
    from test_routing_fixtures import asc_pin_nodes
    from tools.verify_ltspice import compare_partitions

    compiled = json.loads(Path(compiled_path).read_text(encoding="utf-8"))
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))
    source = compiled["backend"]
    before = canonical(source)
    stage = "connectivity"
    started = time.perf_counter()

    def checkpoint():
        write_json(result_path, result)

    def begin(name):
        nonlocal stage
        stage = name
        result["stages"][name] = "RUNNING"
        checkpoint()
        return time.perf_counter()

    def finish(name, since, issues=()):
        result["timings_ms"][name + "_wall"] = (time.perf_counter() - since) * 1000
        result["stages"][name] = "FAIL" if any(item.get("severity") == "error" for item in issues) else "PASS"
        result["diagnostics"].extend(dict(item, pipeline_stage=item.get("stage"), stage=name) for item in issues)
        checkpoint()

    try:
        tick = begin("connectivity")
        model = build_connectivity(source)
        issues = [asdict(item) for item in validate_connectivity(model)]
        expected = {net.name: sorted(pin.key for pin in net.pins) for net in model.nets}
        expected.update({f"unwired:{pin.key}": [pin.key] for pin in model.unconnected_pins()})
        frontend = {net["id"]: net["pins"] for net in compiled["topology"]}
        connected = {pin for pins in frontend.values() for pin in pins}
        mapping = {item["compiled_id"]: item["backend_id"] for item in compiled["identity_mapping"]}
        for component in compiled["components"]:
            for pin in component["pins"]:
                key = f"{mapping[component['id']]}.{pin['id']}"
                if key not in connected:
                    frontend[f"unwired:{key}"] = [key]
        issues.extend(compare_topology(expected, frontend, circuit=result["name"]))
        finish("connectivity", tick, issues)
        if result["stages"]["connectivity"] == "FAIL":
            return
        route_original = exporter.route_nets
        def measured_route(*args, **kwargs):
            nonlocal stage
            tick = begin("route")
            try:
                routed = route_original(*args, **kwargs)
            except Exception as exc:
                issues = [asdict(item) for item in getattr(exc, "diagnostics", ())]
                finish("route", tick, issues)
                result["stages"]["route"] = "TIMEOUT" if any(item.get("code") == "PIPELINE_TIMEOUT" for item in issues) else "FAIL"
                checkpoint()
                raise
            result["counts"]["routed"] = {"nets": len(routed.net_geometries),
                                            "segments": sum(len(net.segments) for net in routed.net_geometries),
                                            "pins": len({(pin.component, pin.pin) for net in routed.net_geometries for pin in net.pins}),
                                            "flags": len(routed.flags)}
            result["routing_metrics"] = routed.metrics
            finish("route", tick, [asdict(item) for item in routed.diagnostics])
            stage = "export"
            return routed
        exporter.route_nets = measured_route
        tick = begin("export")
        pipeline_metrics = {}
        asc, export_issues, routed = exporter.generate_asc_with_routing(source, strict=True, metrics=pipeline_metrics)
        result["pipeline_metrics"] = pipeline_metrics
        # Export time includes routing; do not sum these overlapping measurements.
        if result["stages"]["route"] == "NOT_RUN" and routed is not None and not model.nets:
            result["stages"]["route"] = "NOT_REQUIRED"
        issues = [asdict(item) for item in export_issues]
        if not asc and not any(item["severity"] == "error" for item in issues):
            issues.append(diagnostic("EMPTY_EXPORT", "Exporter returned no ASC", "export"))
        finish("export", tick, issues)
        if routed is not None:
            result["routing_metrics"] = routed.metrics
            if hasattr(routed, "pipeline_metrics"):
                result["pipeline_metrics"] = routed.pipeline_metrics
        if not asc:
            return
        Path(asc_path).write_text(asc, encoding="utf-8", newline="\n")
        result["asc_sha256"] = sha(asc.encode())
        result["asc"] = Path(asc_path).name
        tick = begin("serialized_validation")
        semantic = parse_asc_semantics(asc, result["name"])
        issues = list(semantic["diagnostics"])
        result["counts"]["exported"] = {"components": len(semantic["components"]),
                                          "pins": sum(len(component["pins"]) for component in semantic["components"]),
                                          "wires": len(semantic["wires"]), "flags": len(semantic["flags"])}
        actual = {component["reference"]: (component["kind"], component["symbol"], component["value"]) for component in semantic["components"]}
        contract = {str(component.get("reference") or component.get("id")):
                    (resolve_component_kind(component), COMPONENT_LIBRARY[resolve_component_kind(component)].symbol,
                     str(component["value"]) if component.get("value") is not None else None) for component in source["components"]}
        if contract != actual or len(actual) != len(source["components"]):
            issues.append(diagnostic("SERIALIZED_COMPONENT_DRIFT", "ASC kind/symbol/identity/value contract changed", stage))
        symbols, wires, flags = parse_asc(asc)
        partition = compare_partitions(expected, asc_pin_nodes(symbols, wires, flags))
        result["portable_electrical"] = partition.to_dict()
        if not partition.ok:
            issues.append(diagnostic("SERIALIZED_TOPOLOGY_DRIFT", partition.to_dict(), stage))
        if routed is not None:
            expected_wires = Counter(tuple(sorted((segment.start, segment.end))) for net in routed.net_geometries for segment in net.segments)
            if expected_wires != Counter(tuple(sorted(wire)) for wire in wires):
                issues.append(diagnostic("SERIALIZED_WIRE_MISMATCH", "ASC wires differ from routed geometry", stage))
            if Counter((flag.point, flag.name) for flag in routed.flags) != Counter(flags):
                issues.append(diagnostic("SERIALIZED_LABEL_MISMATCH", "ASC flags differ from routed metadata", stage))
            issues.extend(validate_routing(model, exporter.place_components(source["components"], model), routed, circuit=result["name"]))
        if before != canonical(source):
            issues.append(diagnostic("SOURCE_MUTATED", "Pipeline changed the compiler-derived source", stage))
        finish("serialized_validation", tick, issues)
    except Exception as exc:
        result["stages"][stage] = "FAIL"
        issues = getattr(exc, "diagnostics", ())
        if issues:
            result["diagnostics"].extend(dict(asdict(item), pipeline_stage=getattr(item, "stage", None), stage=stage) for item in issues)
        else:
            result["diagnostics"].append(diagnostic("BACKEND_EXCEPTION", f"{type(exc).__name__}: {exc}", stage))
        for pending in STAGES:
            if result["stages"][pending] == "RUNNING":
                result["stages"][pending] = "INCOMPLETE"
    finally:
        result["timings_ms"]["backend_worker_wall"] = (time.perf_counter() - started) * 1000
        checkpoint()


def unsupported_diagnostic(item):
    code = item.get("code", "")
    return code.startswith("UNSUPPORTED_") or (
        code == "COMPILER_ERROR" and re.fullmatch(
            r"Unknown component type '.+' on component .+\.", str(item.get("message", ""))) is not None
    )


def classify_rejection(result):
    failures = [item for item in result["diagnostics"] if item.get("severity") == "error"]
    if any(unsupported_diagnostic(item) for item in failures):
        result["support"] = "unsupported"
        return "UNSUPPORTED"
    if failures and all(item.get("pipeline_stage") in {"input_validation", "net_building", "validation"}
                        and item.get("code") not in {"PIPELINE_TIMEOUT", "RESOURCE_LIMIT"}
                        for item in failures):
        return "INVALID"
    return result["overall"]


def settle_stages(result):
    """Close stages interrupted by errors that the exporter returned normally."""
    for stage, status in result["stages"].items():
        if status != "RUNNING":
            continue
        names = {stage, "routing" if stage == "route" else stage}
        failed = any(item.get("severity") == "error" and
                     (item.get("stage") in names or item.get("pipeline_stage") in names)
                     for item in result["diagnostics"])
        result["stages"][stage] = "FAIL" if failed else "INCOMPLETE"


def run_case(case, collection, output, *, timeout=30, hash_seed=0):
    before = implementation_snapshot()
    result = _run_case(case, collection, output, timeout=timeout, hash_seed=hash_seed)
    settle_stages(result)
    after = implementation_snapshot()
    result["implementation_sha256"] = before["sha256"]
    result["implementation_stable"] = before == after
    result["hash_seed"] = hash_seed
    if before != after:
        result["implementation_changed_sources"] = sorted(path for path in before["sources"].keys() | after["sources"].keys()
                                                           if before["sources"].get(path) != after["sources"].get(path))
    failures = [dict(item) for item in result["diagnostics"] if item.get("severity") == "error"]
    result["failures"] = failures
    result["failure_stage"] = next((stage for stage in STAGES if result["stages"][stage] in {"FAIL", "TIMEOUT"}),
                                   failures[0].get("stage") if failures else None)
    result["validation"] = result["stages"]["serialized_validation"]
    result["overall"] = classify_rejection(result)
    return result


def _run_case(case, collection, output, *, timeout=30, hash_seed=0):
    output.mkdir(parents=True, exist_ok=True)
    result = empty_result(case)
    value = json.loads((collection / case["input"]).read_text(encoding="utf-8"))
    if sha(canonical(value).encode()) != case["sha256"]:
        result["diagnostics"].append(diagnostic("INPUT_DIGEST_MISMATCH", "Collected input changed", "input"))
        result["overall"] = "FAIL"
        return result
    result["stages"]["compile"] = "RUNNING"
    try:
        process = run_process(["node", str(ROOT / "frontend/tools/compile-regression.cjs")], timeout=timeout,
                              input_text=json.dumps({"circuits": [{"key": case["id"], "input": value}]}))
        result["timings_ms"]["compiler_process_wall"] = process["wall_ms"]
        result["memory"]["compiler"] = process.get("memory")
        (output / "compiler.stderr.log").write_text(process["stderr"], encoding="utf-8")
        if process["timeout"] or process["returncode"]:
            result["stages"]["compile"] = "TIMEOUT" if process["timeout"] else "FAIL"
            result["diagnostics"].append(diagnostic("COMPILER_TIMEOUT" if process["timeout"] else "COMPILER_PROCESS_FAILED", process["stderr"] or process["stdout"], "compile"))
            result["overall"] = "FAIL"
            return result
        compiled = json.loads(process["stdout"])["circuits"][0]
        write_json(output / "compiled.json", compiled)
        result["compiled_sha256"] = sha(canonical({key: value for key, value in compiled.items() if key != "duration_ms"}).encode())
        result["counts"]["compiled"] = compiled["counts"]
        result["timings_ms"]["compiler_reported"] = compiled["duration_ms"]
        result["diagnostics"].extend(compiled["diagnostics"])
        result["stages"]["compile"] = "PASS" if compiled["compiler_valid"] else "FAIL"
        result["stages"]["bridge"] = "PASS" if compiled["valid"] else "FAIL"
        unsupported = any(unsupported_diagnostic(item) for item in compiled["diagnostics"])
        result["support"] = "unsupported" if unsupported else "supported" if compiled["valid"] else "invalid_or_unknown"
        if not compiled["valid"]:
            result["overall"] = "UNSUPPORTED" if unsupported else "INVALID"
            return result
        result_path = output / "worker_result.json"
        write_json(result_path, result)
        process = run_process([sys.executable, str(Path(__file__).resolve()), "_worker", "--compiled", str(output / "compiled.json"),
                               "--result", str(result_path), "--asc", str(output / "circuit.asc")], timeout=timeout,
                              env=dict(os.environ, PYTHONHASHSEED=str(hash_seed)))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["timings_ms"]["backend_process_wall"] = process["wall_ms"]
        result["memory"]["backend"] = process.get("memory")
        (output / "backend.stderr.log").write_text(process["stderr"], encoding="utf-8")
        if process["timeout"] or process["returncode"]:
            active = [stage for stage in STAGES if result["stages"][stage] == "RUNNING"]
            stage = "route" if "route" in active else active[-1] if active else "connectivity"
            result["stages"][stage] = "TIMEOUT" if process["timeout"] else "FAIL"
            for pending in active:
                if pending != stage:
                    result["stages"][pending] = "INCOMPLETE"
            result["diagnostics"].append(diagnostic("BACKEND_TIMEOUT" if process["timeout"] else "BACKEND_PROCESS_FAILED", process["stderr"] or f"Deadline {timeout}s exceeded", stage))
        result["overall"] = "PASS" if all(status in {"PASS", "NOT_REQUIRED"} for status in result["stages"].values()) else "FAIL"
    except Exception as exc:
        active = next((stage for stage in STAGES if result["stages"][stage] == "RUNNING"), "compile")
        result["stages"][active] = "FAIL"
        result["diagnostics"].append(diagnostic("HARNESS_EXCEPTION", f"{type(exc).__name__}: {exc}", active))
        result["overall"] = "FAIL"
    return result


def summarize(results):
    attempts = [sample for case in results for sample in case["samples"]]
    return {"cases": len(results), "attempts": len(attempts),
            "failure_stages": dict(sorted(Counter(sample.get("failure_stage") for sample in attempts if sample.get("failure_stage")).items())),
            "failure_codes": dict(sorted(Counter(item["code"] for sample in attempts for item in sample.get("failures", [])).items())),
            "determinism_status": dict(sorted(Counter(case.get("determinism_status", "NOT_MEASURED") for case in results).items())),
            "case_status": dict(sorted(Counter(case["overall"] for case in results).items())),
            "attempt_status": dict(sorted(Counter(sample["overall"] for sample in attempts).items())),
            "successful_attempts_by_stage": {stage: sum(sample["stages"][stage] == "PASS" for sample in attempts) for stage in STAGES},
            "successful_cases_by_stage": {stage: sum(all(sample["stages"][stage] == "PASS" for sample in case["samples"]) for case in results) for stage in STAGES}}


def execution_catalog(catalog, report):
    result = json.loads(canonical(catalog))
    tested = {case["id"]: case for case in report["cases"]}
    result["execution_report"] = "corpus_report.json"
    result["execution_summary"] = report["summary"]
    for case in result["cases"]:
        if case["id"] not in tested:
            continue
        entry = tested[case["id"]]
        compiled = [sample["counts"]["compiled"] for sample in entry["samples"]]
        case["compiled_counts"] = compiled[0] if compiled and all(value == compiled[0] for value in compiled) else None
        case["counts_basis"] = "Components/connections describe input; pins/nets are actual compiler counts, including rejected partial compilations."
        for key in ("pins", "nets"):
            case["counts"][key] = case["compiled_counts"].get(key) if case["compiled_counts"] else None
        case["support"] = sorted({sample["support"] for sample in entry["samples"]})
        case["validation"] = sorted({sample["stages"]["serialized_validation"] for sample in entry["samples"]})
        case["overall"] = entry["overall"]
        case["failure_stages"] = sorted({sample["failure_stage"] for sample in entry["samples"] if sample.get("failure_stage")})
        case["deterministic_asc"] = entry.get("deterministic_asc")
    return result


def test_corpus(catalog_path, output=None, *, samples=1, timeout=30, ids=()):
    if samples < 1 or timeout <= 0:
        raise ValueError("Samples and timeout must be positive")
    catalog_path = Path(catalog_path).resolve()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported catalog schema")
    output = fresh_directory(output, "test")
    selected = [case for case in catalog["cases"] if not ids or case["id"] in ids]
    if ids and set(ids) - {case["id"] for case in selected}:
        raise ValueError("Unknown selected circuit IDs")
    implementation = implementation_snapshot()
    write_json(output / "implementation.json", implementation)
    report = {"schema_version": SCHEMA_VERSION, "catalog_sha256": sha(catalog_path.read_bytes()), "samples_per_case": samples,
              "environment": {"python": sys.version, "platform": platform.platform(), "implementation": "implementation.json",
                              "implementation_sha256": implementation["sha256"],
                              "pipeline_environment": {key: value for key, value in os.environ.items() if key.startswith("SPICECRAFT_")}},
              "timeout_seconds_per_stage_process": timeout, "cases": [], "catalog_summary": catalog["summary"],
              "limitations": catalog["limitations"] + ["Timeout applies separately to compiler and backend processes; each attempt is isolated.",
                  "Export wall time includes routing; stage measurements overlap and must not be summed.",
                  "Native LTspice, simulation and browser rendering are not measured.",
                  "Memory is the maximum observed OS resident memory: Windows child-tree working set (including venv launchers), Linux child VmHWM; 20ms sampling can miss short-lived peaks and excludes the harness.",
                  "Each repeated backend sample uses a distinct PYTHONHASHSEED; implementation changes invalidate determinism comparisons.",
                  "A successful frontend compile is not a successful shared bridge, route, export or serialized validation."]}
    for case in selected:
        entry = {key: case[key] for key in ("id", "name", "origins", "synthetic", "counts")}
        entry.update({key: case[key] for key in ("family", "target_components") if key in case})
        entry["samples"] = []
        for sample_index in range(samples):
            run_output = output / case["id"] / f"sample-{sample_index + 1}"
            sample = run_case(case, catalog_path.parent, run_output, timeout=timeout, hash_seed=sample_index)
            sample["evidence_directory"] = run_output.relative_to(output).as_posix()
            entry["samples"].append(sample)
            write_json(run_output / "result.json", sample)
        statuses = {sample["overall"] for sample in entry["samples"]}
        entry["overall"] = next(iter(statuses)) if len(statuses) == 1 else "FAIL"
        stable = all(sample["implementation_stable"] for sample in entry["samples"]) and len({sample["implementation_sha256"] for sample in entry["samples"]}) == 1
        entry["implementation_stable"] = stable
        entry["deterministic_outcome"] = len(statuses) == 1 if samples > 1 and stable else None
        for field, key in (("deterministic_asc", "asc_sha256"), ("deterministic_compilation", "compiled_sha256")):
            digests = [sample.get(key) for sample in entry["samples"]]
            entry[field] = None if samples < 2 or not stable or any(value is None for value in digests) else len(set(digests)) == 1
        entry["determinism_status"] = "IMPLEMENTATION_CHANGED" if not stable else "DIFFERENT" if any(entry[key] is False for key in ("deterministic_asc", "deterministic_compilation", "deterministic_outcome")) else "OBSERVED" if samples > 1 else "NOT_MEASURED"
        if entry["determinism_status"] == "DIFFERENT":
            entry["overall"] = "FAIL"
        entry["support"] = sorted({sample["support"] for sample in entry["samples"]})
        entry["validation"] = sorted({sample["validation"] for sample in entry["samples"]})
        metrics = sorted({key for sample in entry["samples"] for key in sample["timings_ms"]})
        entry["timings_ms"] = {key: {"samples": [sample["timings_ms"][key] for sample in entry["samples"] if key in sample["timings_ms"]],
                                          "median": statistics.median(sample["timings_ms"][key] for sample in entry["samples"] if key in sample["timings_ms"])} for key in metrics}
        report["cases"].append(entry)
        report["summary"] = summarize(report["cases"])
        write_json(output / "corpus_report.json", report)
    report["summary"] = summarize(report["cases"])
    validated = enrich_catalog(execution_catalog(catalog, report), catalog_path.parent,
                               report=report, evidence_root=output)
    report = enrich_report(report, validated)
    write_json(output / "corpus_report.json", report)
    write_json(output / "validated_catalog.json", validated)
    write_category_indexes(validated, catalog_path.parent, output / "indexes")
    lines = ["Circuit corpus report", f"Cases: {report['summary']['cases']}; attempts: {report['summary']['attempts']}",
             f"Case status: {canonical(report['summary']['case_status'])}",
             f"Successful cases by stage: {canonical(report['summary']['successful_cases_by_stage'])}", "", "ID | name | outcome | input components | compile / route / export / serialized"]
    for case in report["cases"]:
        stage = case["samples"][0]["stages"]
        lines.append(f"{case['id']} | {case['name']} | {case['overall']} | {case['counts']['components']} | " + " / ".join(stage[key] for key in ("compile", "route", "export", "serialized_validation")))
    lines.extend(["", "Limitations:"] + report["limitations"])
    (output / "corpus_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect-circuits", help="Inventory first, then snapshot all extractable circuits")
    collect.add_argument("--output", type=Path)
    collect.add_argument("--no-synthetic", action="store_true")
    collect.add_argument("--timeout", type=float, default=30)
    test = commands.add_parser("test-corpus", help="Run real compiler/export stages in isolated processes")
    test.add_argument("--catalog", required=True, type=Path)
    test.add_argument("--output", type=Path)
    test.add_argument("--samples", type=int, default=1)
    test.add_argument("--timeout", type=float, default=30)
    test.add_argument("--id", action="append", default=[])
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    for name in ("compiled", "result", "asc"):
        worker.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "_worker":
        backend_worker(args.compiled, args.result, args.asc)
        return 0
    try:
        if args.command == "collect-circuits":
            if args.timeout <= 0:
                raise ValueError("Timeout must be positive")
            output, report = collect_circuits(args.output, include_synthetic=not args.no_synthetic, timeout=args.timeout)
        else:
            output, report = test_corpus(args.catalog, args.output, samples=args.samples, timeout=args.timeout, ids=args.id)
        print(json.dumps({"output": str(output), "summary": report["summary"]}, indent=2))
        if args.command == "test-corpus":
            return 1 if any(case["overall"] != "PASS" for case in report["cases"]) else 0
        return 0
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

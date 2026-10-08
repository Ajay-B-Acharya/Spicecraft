"""Read-only corpus enrichment and reference-only category indexes.

Support describes observed frontend compiler/shared-export kind eligibility,
not backend model acceptance, circuit validity, routing, export or simulation.
No compiler is invoked and no component support table is maintained here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

CATEGORIES = ("small", "medium", "large", "extreme", "regression", "unsupported", "malformed", "failing")
SIZE_BOUNDS = ((20, "small"), (100, "medium"), (500, "large"))
SUPPORT_BOUNDARY = "frontend_compiler_and_shared_export_kind"
UNKNOWN_TYPE = re.compile(r"Unknown component type '(.+)' on component (.+)\.")


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def classify_size(component_count):
    """Classify actual input slots: 1..20, 21..100, 101..500, 501+.

    Missing, empty, negative, boolean and non-integer counts remain unknown.
    """
    if type(component_count) is not int or component_count < 1:
        return "unknown"
    return next((name for bound, name in SIZE_BOUNDS if component_count <= bound), "extreme")


def _input_components(value):
    if isinstance(value, str):
        text = re.sub(r"^```(?:json)?\s*\n([\s\S]*?)\n```$", r"\1", value.strip())
        try:
            value = json.loads(text)
        except (ValueError, UnicodeError):
            return None, "invalid_json_string"
    if not isinstance(value, dict):
        return None, "non_object_input"
    if isinstance(value.get("circuit"), dict):
        value = value["circuit"]
    elif isinstance(value.get("data"), dict) and isinstance(value["data"].get("circuit"), dict):
        value = value["data"]["circuit"]
    # The compiler selects the first array, including a nodes fallback.
    components = next((value[key] for key in ("components", "nodes") if isinstance(value.get(key), list)), None)
    if components is None:
        return None, "missing_or_non_array_components"
    if not components:
        return components, "empty_components"
    return components, "non_object_component" if any(not isinstance(item, dict) for item in components) else "observed"


def _text(value):
    if isinstance(value, str):
        return value.strip() or None
    if type(value) in (int, float):
        return str(value)
    return None


def _identity(component):
    return next((_text(component.get(key)) for key in ("id", "reference", "name") if _text(component.get(key)) is not None), None)


def _unique(items, key, value):
    matches = [item for item in items if item.get(key) == value]
    return matches[0] if len(matches) == 1 else None


def _diagnostic_target(item, components, mappings):
    index = item.get("source_index")
    if type(index) is int and 0 <= index < len(components):
        return index
    compiled_id = item.get("compiled_id")
    if compiled_id is not None:
        mapping = _unique(mappings, "compiled_id", compiled_id)
        if mapping is not None:
            index = mapping.get("source_index")
            if type(index) is int and 0 <= index < len(components):
                return index
        identity = _text(compiled_id)
    else:
        match = UNKNOWN_TYPE.fullmatch(str(item.get("message", ""))) if item.get("code") == "COMPILER_ERROR" else None
        identity = match[2] if match else None
    if identity is None:
        return None
    candidates = [index for index, component in enumerate(components)
                  if isinstance(component, dict) and _identity(component) == identity]
    return candidates[0] if len(candidates) == 1 else None


def component_support(components, observations=()):
    """Attribute real bridge definitions/diagnostics to original input slots.

    Each observation contains optional compiled and diagnostics fields. Positive
    evidence requires a unique identity_mapping and a real pin_definitions entry.
    Conflicting observations remain unknown; missing observations never imply
    support. Non-component unsupported diagnostics are retained but not assigned.
    """
    components = components if isinstance(components, list) else []
    evidence = [[] for _ in components]
    unmatched = []
    for observation in observations:
        compiled = observation.get("compiled") or {}
        mappings = [item for item in compiled.get("identity_mapping", []) if isinstance(item, dict)]
        compiled_components = [item for item in compiled.get("components", []) if isinstance(item, dict)]
        definitions = [item for item in compiled.get("pin_definitions", []) if isinstance(item, dict)]
        for mapping in mappings:
            index = mapping.get("source_index")
            if type(index) is not int or not 0 <= index < len(components) or not isinstance(components[index], dict):
                continue
            if _unique(mappings, "source_index", index) is None or _unique(mappings, "compiled_id", mapping.get("compiled_id")) is None:
                continue
            component = _unique(compiled_components, "id", mapping.get("compiled_id"))
            definition = _unique(definitions, "type", component.get("type")) if component else None
            if not definition or type(definition.get("shared_export")) is not bool:
                continue
            evidence[index].append({"status": "supported" if definition["shared_export"] else "unsupported",
                                    "basis": "compiled.pin_definitions.shared_export",
                                    "compiled_id": mapping.get("compiled_id"), "backend_id": mapping.get("backend_id"),
                                    "compiled_type": component.get("type"), "backend_type": definition.get("backend_type")})
        diagnostics = list(compiled.get("diagnostics", [])) + list(observation.get("diagnostics", []))
        for item in diagnostics:
            if not isinstance(item, dict) or item.get("severity") != "error":
                continue
            code = item.get("code", "")
            unknown = code == "COMPILER_ERROR" and UNKNOWN_TYPE.fullmatch(str(item.get("message", "")))
            if code != "UNSUPPORTED_SHARED_EXPORT_KIND" and not unknown:
                if str(code).startswith("UNSUPPORTED_"):
                    unmatched.append(deepcopy(item))
                continue
            index = _diagnostic_target(item, components, mappings)
            if index is None:
                unmatched.append(deepcopy(item))
            else:
                evidence[index].append({"status": "unsupported", "basis": "diagnostic", "diagnostic": deepcopy(item)})
    result = {"boundary": SUPPORT_BOUNDARY, "supported": [], "unsupported": [], "unknown": [],
              "unattributed_diagnostics": [_item for _, _item in sorted({_canonical(item): item for item in unmatched}.items())]}
    for index, component in enumerate(components):
        observed = [item for _, item in sorted({_canonical(item): item for item in evidence[index]}.items())]
        statuses = {item["status"] for item in observed}
        status = next(iter(statuses)) if len(statuses) == 1 else "unknown"
        record = {"source_index": index, "evidence": observed}
        if isinstance(component, dict):
            record.update({key: deepcopy(component[key]) for key in ("id", "reference", "name", "type", "value") if key in component})
        if status == "unknown":
            record["reason"] = "conflicting_evidence" if observed else "no_attributable_evidence"
        result[status].append(record)
    result["counts"] = {status: len(result[status]) for status in ("supported", "unsupported", "unknown")}
    result["coverage"] = "unknown" if not components else "partial" if result["unknown"] else "complete"
    return result


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig")), None
    except OSError:
        return None, "unreadable_file"
    except (ValueError, UnicodeError):
        return None, "invalid_json_file"


def _child(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("Missing relative artifact path")
    path = (Path(root).resolve() / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Artifact path escapes its root")
    return path


def _observations(entry, evidence_root, case_id):
    observations, issues = [], []
    samples = entry.get("samples", [])
    if not samples and entry.get("diagnostics"):
        samples = [entry]
    for sample in samples:
        compiled = None
        directory = sample.get("evidence_directory")
        if evidence_root is not None and directory:
            try:
                path = _child(evidence_root, str(Path(directory) / "compiled.json"))
                compiled, error = _read_json(path)
            except ValueError:
                error = "invalid_evidence_path"
            if error:
                issues.append(error)
            elif not isinstance(compiled, dict) or compiled.get("key") != case_id:
                compiled = None
                issues.append("compiled_identity_mismatch")
            elif sample.get("compiled_sha256") and _digest({key: value for key, value in compiled.items() if key != "duration_ms"}) != sample["compiled_sha256"]:
                compiled = None
                issues.append("compiled_digest_mismatch")
        observations.append({"compiled": compiled, "diagnostics": sample.get("diagnostics", [])})
    return observations, sorted(set(issues))


def _categories(case, metadata, entry):
    categories = {metadata["size_class"]} & set(CATEGORIES)
    origins = case.get("origins", [])
    if case.get("regression") is True or any("tests" in str(origin.get("source", "")).replace("\\", "/").split("/")
                                             and origin.get("kind") != "synthetic" for origin in origins):
        categories.add("regression")
    support = metadata["component_support"]
    statuses = {entry.get("overall"), case.get("overall")}
    statuses.update(sample.get("overall") for sample in entry.get("samples", []))
    if support["unsupported"] or support["unattributed_diagnostics"] or "UNSUPPORTED" in statuses:
        categories.add("unsupported")
    if metadata["input_structure"] not in {"observed", "unavailable"} or "INVALID" in statuses:
        categories.add("malformed")
    if statuses & {"FAIL", "TIMEOUT", "INCOMPLETE"}:
        categories.add("failing")
    return [category for category in CATEGORIES if category in categories]


def enrich_catalog(catalog, collection_root, *, report=None, evidence_root=None):
    """Return a deep copy with case.catalog_metadata; never rewrite input fields.

    Works on collection or validated catalogs. collection_root always names the
    original collected inputs, even when the validated catalog lives elsewhere.
    report/evidence_root supply completed execution evidence when available.
    """
    result = deepcopy(catalog)
    entries = {entry["id"]: entry for entry in (report or {}).get("cases", [])}
    for case in result["cases"]:
        try:
            value, error = _read_json(_child(collection_root, case.get("input")))
        except ValueError:
            value, error = None, "invalid_input_path"
        components, structure = _input_components(value) if not error else (None, "invalid_json_file" if error == "invalid_json_file" else "unavailable")
        actual_hash = _digest(value) if not error else None
        expected_hash = case.get("sha256")
        integrity = "unavailable" if error else "unverified" if not expected_hash else "match" if actual_hash == expected_hash else "mismatch"
        entry = entries.get(case["id"], {})
        observations, issues = _observations(entry, evidence_root, case["id"])
        if integrity in {"mismatch", "unavailable"}:
            observations = []
        count = len(components) if components is not None else None
        metadata = {"schema_version": 1, "input_component_count": count, "size_class": classify_size(count),
                    "input_structure": structure, "input_integrity": integrity, "observed_input_sha256": actual_hash,
                    "evidence_issues": sorted(set(issues + ([error] if error else []))),
                    "component_support": component_support(components, observations)}
        metadata["categories"] = _categories(case, metadata, entry)
        case["catalog_metadata"] = metadata
    result["catalog_metadata_policy"] = {
        "schema_version": 1, "size_basis": "Actual input array slots, including malformed entries; never target or compiled counts.",
        "size_ranges": {"small": [1, 20], "medium": [21, 100], "large": [101, 500], "extreme": [501, None], "unknown": None},
        "support_boundary": SUPPORT_BOUNDARY,
        "support_limit": "Kind eligibility only; not backend model acceptance, topology validity, routing, export or simulation. Unobserved and ambiguous components remain unknown.",
        "categories": "Overlapping views. Regression means non-synthetic test-source provenance or explicit regression=true; malformed means structural rejection or INVALID; failing means FAIL/TIMEOUT/INCOMPLETE.",
    }
    return result


def enrich_report(report, enriched_catalog):
    """Return a report copy with original input references and matching metadata.

    Unexecuted cases stay in the catalog, not fabricated report attempts. Report
    entries absent from the catalog are retained with an explicit lookup issue.
    """
    result = deepcopy(report)
    cases = {case["id"]: case for case in enriched_catalog["cases"]}
    for entry in result["cases"]:
        case = cases.get(entry["id"])
        if case is None:
            entry["catalog_metadata"] = {"schema_version": 1, "evidence_issues": ["case_not_in_catalog"]}
            continue
        entry["catalog_metadata"] = deepcopy(case["catalog_metadata"])
        for key in ("input", "sha256", "origins"):
            if key in case and key not in entry:
                entry[key] = deepcopy(case[key])
    result["catalog_metadata_policy"] = deepcopy(enriched_catalog["catalog_metadata_policy"])
    return result


def category_indexes(enriched_catalog, collection_root, *, index_root):
    """Build JSON views referencing original files, plus an all-cases view."""
    root = Path(collection_root).resolve()
    destination = Path(index_root).resolve()
    views = {}
    for category in ("all",) + CATEGORIES:
        entries = []
        for case in enriched_catalog["cases"]:
            metadata = case["catalog_metadata"]
            if category != "all" and category not in metadata["categories"]:
                continue
            entry = {key: deepcopy(case[key]) for key in ("id", "name", "input", "sha256", "origins", "synthetic", "overall") if key in case}
            try:
                entry["input_path"] = Path(os.path.relpath(_child(root, case.get("input")), destination)).as_posix()
            except ValueError:
                entry["input_path"] = None
            entry["catalog_metadata"] = deepcopy(metadata)
            entries.append(entry)
        entries.sort(key=lambda entry: (str(entry["id"]), _canonical(entry)))
        views[category] = {"schema_version": 1, "category": category, "count": len(entries),
                           "collection_root": Path(os.path.relpath(root, destination)).as_posix(), "cases": entries}
    return views


def write_category_indexes(enriched_catalog, collection_root, output):
    """Write only reference indexes to a new/empty directory; return their paths."""
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Index output must be a new/empty directory: {output}")
    views = category_indexes(enriched_catalog, collection_root, index_root=output)
    output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for category, view in views.items():
        path = output / f"{category}.json"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(view, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
        paths[category] = path
    return paths

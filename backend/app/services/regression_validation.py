"""Phase 9 validation only: no exporting, routing, snapping, or file I/O.

Public results are plain JSON-friendly dictionaries/lists (canonical topology
uses sorted tuples, also JSON-serializable). Diagnostics always contain
``circuit, component, pin, net, expected, actual, error, code, severity``; unused
context is None. ``error`` is an actionable message, not a boolean. Parser
records also carry one-based ``line`` numbers. Only metric issues are review
items; structural/electrical failures have severity ``error``.

This module uses the standard library and existing dependency-free pin/routing
validators. It neither imports the production exporter nor needs Pillow or an
LTspice installation. Expected source/value comparisons remain the caller's job.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from itertools import combinations
import math
import re
from typing import Any

from app.services.asc_validation import NetGeometry, PinPoint, WireSegment, validate_net_geometry
from app.services.grid_system import GridSystem
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver
from app.services.routing.geometry import CollisionDetector, box_contains, intersection, on_segment, prepare_problem
from app.services.routing.models import RoutingOptions


_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_REFERENCE = re.compile(r"[A-Za-z][A-Za-z0-9_$-]*\Z")
_JUSTIFICATIONS = {"Left", "Right", "Center", "VLeft", "VRight", "VCenter"}
_SYMBOLS = {definition.symbol.replace("\\", "/").casefold(): definition
            for definition in COMPONENT_LIBRARY.values()}
_ANONYMOUS = re.compile(r"(?:N\$?[0-9]+|@[\s\S]*)\Z", re.IGNORECASE)


def _json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


def _diagnostic(code: str, error: str, *, circuit: str = "", component=None,
                pin=None, net=None, expected=None, actual=None, severity="error",
                **extra) -> dict:
    return _json(dict(circuit=circuit, component=component, pin=pin, net=net,
                      expected=expected, actual=actual, error=error, code=code,
                      severity=severity, **extra))


class _Syntax(ValueError):
    def __init__(self, code: str, message: str, expected: Any):
        super().__init__(message)
        self.code, self.expected = code, expected


def _integer(token: str) -> int:
    if not _INTEGER.fullmatch(token):
        raise _Syntax("INVALID_INTEGER", "Use an exact decimal integer, not a float or expression", "exact decimal integer")
    try:
        return int(token)
    except ValueError:
        raise _Syntax("INVALID_INTEGER", "Integer token exceeds the supported size", "decimal integer") from None


def parse_asc_semantics(text: str, circuit: str = "", *, require_headers: bool = True) -> dict:
    """Parse the strict exported ASC subset, diagnosing malformed lines, not raising.

    Shape: version=int|None; sheet={index,width,height,line}|None;
    components=[{symbol,anchor:[x,y],orientation,kind,reference,value,
    attributes:{original_name:raw_value},pins:{canonical_pin:[x,y]},windows,line}];
    wires=[{start:[x,y],end:[x,y],line}]; flags=[{point:[x,y],name,line}];
    text=[{point,justification,size,value,line}]; windows=[{index,point,
    justification,size,component,line}]; diagnostics=[diagnostic]. Text ``value``
    includes its native ';' comment / '!' directive marker. Attribute/text
    payloads retain internal and trailing whitespace; separator whitespace is
    not payload. Missing Value is None, never a substituted/default value.

    Supported records: Version 4, SHEET 1 with positive dimensions, SYMBOL,
    WINDOW, SYMATTR, WIRE, FLAG, TEXT. Full ASC input must start with Version then
    SHEET (ignoring blank lines); missing/invalid/misordered headers are errors.
    Header-only empty schematics are valid: symbols/wires/flags/text/windows are
    never required. Set require_headers=False ONLY for parsing isolated fragments;
    present headers must still be unique and valid. WINDOW/SYMATTR belong only to the
    immediately preceding symbol block; ANY non-block record closes that scope,
    even when malformed. Unknown records are errors. References are ASCII letter
    followed by letters/digits/_/$/-, with case-insensitive uniqueness. Native
    symbol paths are case-insensitive; aliases/fallback resistor symbols are not
    guessed. Only symbol/wire/flag coordinates must be on the 16-unit grid.
    Window/text coordinates are exact integers but may be off-grid.

    Invalid records are retained where parseable for inspection, never repaired.
    Callers must check diagnostics before using the recovered semantic data.
    """
    result = dict(version=None, sheet=None, components=[], wires=[], flags=[],
                  text=[], windows=[], diagnostics=[])
    diagnostics = result["diagnostics"]
    if not isinstance(text, str):
        diagnostics.append(_diagnostic("INVALID_ASC", "ASC input must be text", circuit=circuit,
                                       expected="str", actual=type(text).__name__))
        return result
    current = None
    record_count = 0
    owners: dict[int, dict] = {}
    seen: dict[str, set] = {key: set() for key in ("Version", "SHEET", "SYMBOL", "WIRE", "FLAG", "TEXT")}

    def issue(code, message, expected=None, actual=None, **context):
        diagnostics.append(_diagnostic(code, message, circuit=circuit, line=number,
                                       expected=expected, actual=raw if actual is None else actual,
                                       **context))

    def duplicate(record, key):
        if key in seen[record]:
            issue("DUPLICATE_" + record.upper(), "Remove the duplicate " + record + " record", actual=key)
        seen[record].add(key)

    def grid(point):
        if not GridSystem.is_point_on_grid(point):
            issue("OFF_GRID", "Place symbol/wire/flag coordinates on the 16-unit grid without rounding",
                  expected=f"multiples of {GridSystem.SIZE}", actual=point)

    def fields_exact(fields, count, syntax):
        if len(fields) != count:
            raise _Syntax("MALFORMED_RECORD", "Use " + syntax, syntax)

    from app.services.production import checkpoint
    for number, raw in enumerate(text.splitlines(), 1):
        checkpoint()
        fields = raw.split()
        if not fields:
            continue
        command = fields[0]
        record_count += 1
        expected_header = {1: "Version", 2: "SHEET"}.get(record_count)
        if require_headers and ((expected_header is not None and command != expected_header)
                                or (command in {"Version", "SHEET"} and command != expected_header)):
            issue("HEADER_ORDER", "Start the ASC with Version then SHEET, before all drawing records",
                  expected=expected_header or "drawing record (headers must come first)", actual=command)
        if command not in {"SYMATTR", "WINDOW"}:
            current = None
        if current is not None:
            owners[number] = current
        try:
            if command == "Version":
                duplicate(command, command)
                fields_exact(fields, 2, "Version 4")
                version = _integer(fields[1])
                if version != 4:
                    raise _Syntax("INVALID_VERSION", "Only exported ASC Version 4 is supported", 4)
                if result["version"] is None:
                    result["version"] = version
            elif command == "SHEET":
                duplicate(command, command)
                fields_exact(fields, 4, "SHEET 1 <positive width> <positive height>")
                index, width, height = map(_integer, fields[1:])
                if index != 1 or width <= 0 or height <= 0:
                    raise _Syntax("INVALID_SHEET", "Use sheet index 1 and positive dimensions", "SHEET 1 width>0 height>0")
                if result["sheet"] is None:
                    result["sheet"] = dict(index=index, width=width, height=height, line=number)
            elif command == "SYMBOL":
                fields_exact(fields, 5, "SYMBOL <native symbol> <x> <y> <orientation>")
                name, x, y, orientation = fields[1:]
                anchor = [_integer(x), _integer(y)]
                current = dict(symbol=name, anchor=anchor, orientation=orientation,
                               kind=None, reference=None, value=None, attributes={},
                               pins={}, windows=[], line=number)
                result["components"].append(current)
                owners[number] = current
                grid(anchor)
                duplicate(command, (name.replace("\\", "/").casefold(), *anchor, orientation))
                definition = _SYMBOLS.get(name.replace("\\", "/").casefold())
                if definition is None:
                    issue("UNKNOWN_SYMBOL", "Add a verified native symbol definition; no fallback pin mapping is allowed",
                          expected=sorted(_SYMBOLS), actual=name)
                else:
                    current["kind"] = definition.kind
                if not re.fullmatch(r"[RM](?:0|90|180|270)", orientation):
                    raise _Syntax("INVALID_ORIENTATION", "Use a native quarter-turn orientation", "R0/R90/R180/R270/M0/M90/M180/M270")
                if definition is not None:
                    current["pins"] = _json(PinResolver.resolve_all_pins(definition, tuple(anchor), orientation))
            elif command in {"SYMATTR", "WINDOW"}:
                if current is None:
                    raise _Syntax("ORPHAN_" + command, "Move this record into its preceding SYMBOL block, before wires/flags/text", "preceding SYMBOL")
                if command == "SYMATTR":
                    match = re.fullmatch(r"\s*SYMATTR[ \t]+(\S+)(?:[ \t]+(.*))?", raw)
                    if match is None:
                        raise _Syntax("MALFORMED_RECORD", "Use SYMATTR <name> <value>", "SYMATTR name value")
                    name, value = match.group(1), match.group(2) or ""
                    attrs = current["attributes"]
                    if name.casefold() in {key.casefold() for key in attrs}:
                        issue("DUPLICATE_ATTRIBUTE", "Keep exactly one attribute of each name per symbol", actual=name)
                    else:
                        attrs[name] = value
                    if not value.strip():
                        issue("EMPTY_ATTRIBUTE", "Provide a nonempty attribute value", actual=name)
                else:
                    fields_exact(fields, 6, "WINDOW <index> <x> <y> <justification> <size>")
                    index, x, y = map(_integer, fields[1:4])
                    size = _integer(fields[5])
                    if index < 0 or fields[4] not in _JUSTIFICATIONS or not 0 <= size <= 7:
                        raise _Syntax("INVALID_WINDOW", "Use a nonnegative window index, native justification and size 0..7", "WINDOW index>=0 x y Left|Right|Center|VLeft|VRight|VCenter size=0..7")
                    if any(window["index"] == index for window in current["windows"]):
                        issue("DUPLICATE_WINDOW", "Keep one WINDOW for each index in a symbol block", actual=index)
                    window = dict(index=index, point=[x, y], justification=fields[4], size=size,
                                  component=None, line=number)
                    current["windows"].append(window)
                    result["windows"].append(window)
            elif command == "WIRE":
                fields_exact(fields, 5, "WIRE <x1> <y1> <x2> <y2>")
                x1, y1, x2, y2 = map(_integer, fields[1:])
                start, end = [x1, y1], [x2, y2]
                grid(start)
                grid(end)
                duplicate(command, tuple(sorted((tuple(start), tuple(end)))))
                if start == end:
                    issue("ZERO_LENGTH_WIRE", "Remove the zero-length wire", actual=start)
                elif x1 != x2 and y1 != y2:
                    issue("NON_ORTHOGONAL_WIRE", "Use horizontal or vertical wire segments", actual=[start, end])
                result["wires"].append(dict(start=start, end=end, line=number))
            elif command == "FLAG":
                fields_exact(fields, 4, "FLAG <x> <y> <single-token name>")
                point = [_integer(fields[1]), _integer(fields[2])]
                grid(point)
                duplicate(command, (*point, fields[3].casefold()))
                result["flags"].append(dict(point=point, name=fields[3], line=number))
            elif command == "TEXT":
                match = re.fullmatch(r"\s*TEXT[ \t]+(\S+)[ \t]+(\S+)[ \t]+(\S+)[ \t]+(\S+)[ \t]+([;!].*)", raw)
                if match is None:
                    raise _Syntax("MALFORMED_RECORD", "Use TEXT <x> <y> <justification> <size> ;comment or !directive", "TEXT x y Left 2 ;text")
                x, y, justification, size, value = match.groups()
                point, size = [_integer(x), _integer(y)], _integer(size)
                if justification not in _JUSTIFICATIONS or not 0 <= size <= 7:
                    raise _Syntax("INVALID_TEXT", "Use native text justification and size 0..7", sorted(_JUSTIFICATIONS))
                duplicate(command, (*point, justification, size, value))
                result["text"].append(dict(point=point, justification=justification, size=size, value=value, line=number))
            else:
                raise _Syntax("UNKNOWN_RECORD", "Remove or explicitly support this ASC record", "Version/SHEET/SYMBOL/WINDOW/SYMATTR/WIRE/FLAG/TEXT")
        except _Syntax as exc:
            issue(exc.code, str(exc), expected=exc.expected)
        except ValueError as exc:
            issue("INVALID_SYMBOL_GEOMETRY", str(exc))

    if require_headers:
        for record in ("Version", "SHEET"):
            if not seen[record]:
                diagnostics.append(_diagnostic("MISSING_" + record.upper(), "Add the required " + record + " header before drawing records",
                                               circuit=circuit, expected="Version 4" if record == "Version" else "SHEET 1 width height"))
    references = set()
    for component in result["components"]:
        attrs = {key.casefold(): value for key, value in component["attributes"].items()}
        reference = attrs.get("instname")
        component["reference"], component["value"] = reference, attrs.get("value")
        context = dict(circuit=circuit, line=component["line"], component=reference,
                       actual=reference, expected="unique reference: letter followed by letters/digits/_/$/-")
        if reference is None or not reference.strip():
            diagnostics.append(_diagnostic("MISSING_REFERENCE", "Add SYMATTR InstName to this SYMBOL block", **context))
        elif not _REFERENCE.fullmatch(reference):
            diagnostics.append(_diagnostic("INVALID_REFERENCE", "Use a single valid component reference without whitespace or dots", **context))
        elif reference.casefold() in references:
            diagnostics.append(_diagnostic("DUPLICATE_REFERENCE", "Give every symbol a case-insensitively unique InstName", **context))
        if reference:
            references.add(reference.casefold())
        for window in component["windows"]:
            window["component"] = reference
    for diagnostic in diagnostics:
        owner = owners.get(diagnostic.get("line"))
        if owner is not None and diagnostic["component"] is None:
            diagnostic["component"] = owner["reference"]
    return result


def _groups(groups) -> dict[str, tuple[str, ...]]:
    entries = groups.items() if isinstance(groups, Mapping) else enumerate(groups)
    answer, owners = {}, set()
    for name, pins in entries:
        if isinstance(pins, (str, bytes)):
            raise ValueError("A net's pins must be an iterable of Component.Pin strings, not text")
        members = []
        for pin in pins:
            if (not isinstance(pin, str) or pin.count(".") != 1
                    or not all(pin.split(".")) or any(c.isspace() for c in pin)):
                raise ValueError(f"Expected canonical Component.Pin, got {pin!r}")
            if pin in owners:
                raise ValueError(f"Partition repeats pin {pin}")
            owners.add(pin)
            members.append(pin)
        if str(name) in answer:
            raise ValueError(f"Duplicate net identifier {name!r}")
        answer[str(name)] = tuple(sorted(members))
    return answer


def _labels(name: str, labels: Mapping | None) -> tuple[str, ...]:
    values = labels.get(name, ()) if labels is not None else (() if _ANONYMOUS.fullmatch(name) else (name,))
    if isinstance(values, str):
        values = (values,)
    else:
        values = tuple(values)
    if any(not isinstance(value, str) or not value or any(c.isspace() for c in value) for value in values):
        raise ValueError("Electrical labels must be nonempty single-token strings")
    return tuple(sorted({value.casefold() for value in values}))


def canonical_topology(groups: Mapping[str, Iterable[str]], *, preserve_labels: bool = False,
                       labels: Mapping[str, Iterable[str] | str] | None = None) -> list[tuple]:
    """Canonical net->canonical-pin partition, independent of geometry/order.

    Default output is sorted pin tuples; empty groups are ignored. With
    preserve_labels=True each entry is (sorted_label_tuple, sorted_pin_tuple).
    Explicit ``labels={net_id: electrical_labels}`` is authoritative (missing
    entries are anonymous), recommended for source model labels. Without it,
    only N<number>, N$<number>, and @... names are treated as anonymous; other
    names, including ground '0', are electrical labels. Label case is ignored,
    not label identity. A named zero-pin net is retained in label-aware mode.
    Invalid partitions/labels raise ValueError; comparison wraps those as issues.
    """
    partition = _groups(groups)
    if not preserve_labels:
        return sorted(pins for pins in partition.values() if pins)
    entries = [(_labels(name, labels), pins) for name, pins in partition.items()]
    return sorted(entry for entry in entries if entry[0] or entry[1])


def compare_topology(expected, actual, *, preserve_labels: bool = False,
                     expected_labels: Mapping | None = None, actual_labels: Mapping | None = None,
                     circuit: str = "") -> list[dict]:
    """Compare net->pins mappings (or pin-group iterables); return only issues.

    Uses the independent verifier's compare_partitions, with synthetic actual
    node IDs so arbitrary net spelling/case cannot accidentally merge groups.
    Includes missing/unexpected pins as well as opens and shorts. Optional label
    comparison checks each electrical label's pin membership, including empty
    named nets; it never treats mere equal group names as connectivity.
    """
    from tools.verify_ltspice import compare_partitions

    try:
        left, right = _groups(expected), _groups(actual)
        pin_nodes = {pin: f"node-{index}" for index, pins in enumerate(right.values()) for pin in pins}
        report = compare_partitions(left, pin_nodes)
        issues = []
        for code, pins, message in (("MISSING_PIN", report.missing_pins, "Restore the missing canonical pin"),
                                    ("UNEXPECTED_PIN", report.unexpected_pins, "Remove or account for the unexpected canonical pin")):
            for key in pins:
                component, pin = key.split(".")
                issues.append(_diagnostic(code, message, circuit=circuit, component=component, pin=pin,
                                          expected=key if code == "MISSING_PIN" else None,
                                          actual=key if code == "UNEXPECTED_PIN" else None))
        for item in report.opens:
            name = item["expected_group"]
            issues.append(_diagnostic("OPEN", "Reconnect the separated fragments of this expected net", circuit=circuit,
                                      net=name, expected=left[name], actual=item["actual_fragments"]))
        for item in report.shorts:
            issues.append(_diagnostic("SHORT", "Separate pins that belong to different expected nets", circuit=circuit,
                                      net=", ".join(item["expected_groups"]),
                                      expected={name: left[name] for name in item["expected_groups"]}, actual=item["pins"]))
        if preserve_labels:
            def memberships(groups, labels):
                found = {}
                for name, pins in groups.items():
                    for label in _labels(name, labels):
                        found.setdefault(label, set()).update(pins)
                return {label: sorted(pins) for label, pins in sorted(found.items())}
            before, after = memberships(left, expected_labels), memberships(right, actual_labels)
            if before != after:
                issues.append(_diagnostic("NAMED_NET_MISMATCH", "Restore electrical label identities and their pin membership",
                                          circuit=circuit, expected=before, actual=after))
        return issues
    except (TypeError, ValueError) as exc:
        return [_diagnostic("INVALID_TOPOLOGY", str(exc), circuit=circuit,
                            expected="disjoint groups of canonical Component.Pin strings")]


DEFAULT_METRIC_THRESHOLDS = {
    "total_length": {"relative": 0.20, "absolute": 64},
    "bend_count": {"relative": 0.30, "absolute": 2},
    "crossing_count": {"relative": 0.0, "absolute": 0},
}


def _number(value) -> bool:
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value)) and value >= 0


def compare_metrics(before: Mapping, after: Mapping, *, thresholds: Mapping | None = None,
                    circuit: str = "") -> list[dict]:
    """Review only: delta > relative*before AND delta >= absolute (delta > 0).

    Defaults: length >20% and >=64 units; bends >30% and >=2; ANY increase in
    crossings, including 0->1. ``thresholds`` partially overrides the public
    DEFAULT_METRIC_THRESHOLDS mapping by metric and relative/absolute field.
    Decimal comparisons make the strict percentage boundary explicit. Smaller
    changes/improvements are accepted. Metrics absent on both sides are ignored;
    one-sided/malformed measurements are review issues, never fabricated zeros.
    Invalid configuration raises ValueError. All issues have severity='review'.
    """
    config = {key: dict(value) for key, value in DEFAULT_METRIC_THRESHOLDS.items()}
    for metric, values in (thresholds or {}).items():
        if metric not in config or not isinstance(values, Mapping) or set(values) - {"relative", "absolute"}:
            raise ValueError(f"Unknown metric/threshold configuration: {metric}")
        config[metric].update(values)
    if any(not _number(value) for values in config.values() for value in values.values()):
        raise ValueError("Metric thresholds must be finite, nonnegative numbers")
    issues = []
    for metric, limits in config.items():
        if metric not in before and metric not in after:
            continue
        context = dict(circuit=circuit, severity="review", metric=metric,
                       expected=before.get(metric), actual=after.get(metric), thresholds=limits)
        if metric not in before or metric not in after:
            issues.append(_diagnostic("METRIC_MISSING", "Measure this metric on both sides before reviewing a regression", **context))
            continue
        old, new = before[metric], after[metric]
        if not _number(old) or not _number(new):
            # Keep the diagnostic itself strict JSON (no NaN/Infinity).
            context.update(expected=old if _number(old) else repr(old), actual=new if _number(new) else repr(new))
            issues.append(_diagnostic("INVALID_METRIC", "Use finite, nonnegative numeric measurements", **context))
            continue
        old, new = Decimal(str(old)), Decimal(str(new))
        delta = new - old
        if delta > 0 and delta > old * Decimal(str(limits["relative"])) and delta >= Decimal(str(limits["absolute"])):
            issues.append(_diagnostic("METRIC_REGRESSION", "Review this material increase; it is not an electrical failure", **context))
    return issues


def _point(point) -> bool:
    return isinstance(point, (list, tuple)) and len(point) == 2 and all(type(value) is int for value in point)


def validate_routing(model, layouts: Mapping, routed, *, options: RoutingOptions | None = None,
                     circuit: str = "") -> list[dict]:
    """Read-only audit of ConnectivityModel, placed layouts, and RoutingResult.

    Returns diagnostics, reusing validate_net_geometry (including reserved pins)
    and CollisionDetector with prepare_problem's exact pin escape corridors.
    Geometry/flat routed flags both supply legal endpoints. Original wires are
    structurally checked before PRIVATE audit segments split at matching-net
    escape points: cleaned long leads must not fail merely because their escape
    vertices were merged away. Original wires, pins, flags and crossings are
    never edited, and artificial audit vertices never establish connectivity.

    Crossings are independently detected on original wires; the exact unordered
    (net pair, point) set must equal routed.crossings (no missing, stale, or
    duplicate declarations). Collision policy still rejects conductive contacts
    and forbidden crossings at pins/corridors. All foreign overlaps and same-net
    duplicate/partial overlaps are errors. Supply the same RoutingOptions used
    for routing when they differ from defaults. Source/topology completeness is
    deliberately separate; use compare_topology for expected pin membership.
    """
    issues = []

    def add_export(diagnostic):
        issues.append(_diagnostic(diagnostic.code, diagnostic.message, circuit=circuit,
                                  component=diagnostic.component, pin=diagnostic.pin, net=diagnostic.net,
                                  expected=diagnostic.expected, actual=diagnostic.actual))

    for diagnostic in routed.diagnostics:
        add_export(diagnostic)
    safe_layouts = {}
    for reference, layout in layouts.items():
        if not isinstance(layout, Mapping) or not _point(layout.get("_ltspice_anchor")):
            issues.append(_diagnostic("INVALID_ROUTING_GEOMETRY", "Supply an exact two-integer placed anchor", circuit=circuit,
                                      component=reference, actual=layout.get("_ltspice_anchor") if isinstance(layout, Mapping) else None))
        else:
            safe_layouts[reference] = layout
    problem, preparation = prepare_problem(model, safe_layouts, options or RoutingOptions())
    for diagnostic in preparation:
        add_export(diagnostic)
    geometries = [NetGeometry(net.name, list(net.pins), list(net.flags), list(net.segments)) for net in routed.net_geometries]
    for flag in routed.flags:
        targets = [net for net in geometries if net.name == flag.net]
        if not targets:
            issues.append(_diagnostic("UNKNOWN_FLAG_NET", "Attach this flag to an existing routed net", circuit=circuit,
                                      net=flag.net, actual=flag.point))
        for net in targets:
            if flag.point not in net.flags:
                net.flags.append(flag.point)
    invalid = False
    for net in geometries:
        points = [pin.point for pin in net.pins] + net.flags + [p for wire in net.segments for p in (wire.start, wire.end)]
        for point in points:
            if not _point(point):
                invalid = True
                issues.append(_diagnostic("INVALID_COORDINATE", "Routing coordinates must be exact integer pairs", circuit=circuit,
                                          net=net.name, actual=point))
    if invalid:
        return issues  # The shared predicates require well-formed integer points.
    # Shared validators use hashable coordinates; normalize private copies only.
    geometries = [NetGeometry(net.name,
                             [PinPoint(pin.component, pin.pin, tuple(pin.point)) for pin in net.pins],
                             [tuple(point) for point in net.flags],
                             [WireSegment(wire.net, tuple(wire.start), tuple(wire.end)) for wire in net.segments])
                  for net in geometries]
    for diagnostic in validate_net_geometry(geometries, reserved_pins=[pin.terminal for pin in problem.pins.values()]):
        add_export(diagnostic)
    segments = [segment for net in geometries for segment in net.segments
                if segment.start != segment.end
                and (segment.start[0] == segment.end[0] or segment.start[1] == segment.end[1])
                and all(GridSystem.is_point_on_grid(point) for point in (segment.start, segment.end))]
    detected = set()
    for left, right in combinations(segments, 2):
        kind, point = intersection(left, right)
        if left.net != right.net and kind == "cross":
            detected.add((tuple(sorted((left.net, right.net))), point))
        if left.net == right.net and kind == "overlap" and {left.start, left.end} != {right.start, right.end}:
            issues.append(_diagnostic("OVERLAPPING_WIRE_SEGMENTS", "Remove the redundant same-net collinear overlap", circuit=circuit,
                                      net=left.net, expected=[left.start, left.end], actual=[right.start, right.end]))
    declared, crossings = set(), []
    for crossing in routed.crossings:
        if (not _point(crossing.point) or len(crossing.nets) != 2 or len(set(crossing.nets)) != 2
                or any(not isinstance(net, str) or not net for net in crossing.nets)):
            issues.append(_diagnostic("INVALID_CROSSING", "Declare two distinct nets and one integer crossing point", circuit=circuit,
                                      actual=[crossing.nets, crossing.point]))
            continue
        key = (tuple(sorted(crossing.nets)), tuple(crossing.point))
        if key in declared:
            issues.append(_diagnostic("DUPLICATE_CROSSING", "Keep one declaration per physical crossing", circuit=circuit, actual=key))
        declared.add(key)
        # Normalize pair order only in the private audit metadata.
        crossings.append(type(crossing)(key[0], key[1]))
    if detected != declared:
        issues.append(_diagnostic("CROSSING_MISMATCH", "Declare exactly the actual unsplit foreign-net crossings; remove unintended crossings",
                                  circuit=circuit, expected=sorted(declared), actual=sorted(detected),
                                  missing=sorted(declared - detected), unexpected=sorted(detected - declared)))
    detector = CollisionDetector(problem)
    for segment in segments:
        cuts = {segment.start, segment.end}
        cuts.update(pin.escape for pin in problem.pins.values()
                    if pin.net == segment.net and on_segment(pin.escape, segment.start, segment.end, strict=True))
        ordered = sorted(cuts)
        for start, end in zip(ordered, ordered[1:]):
            audit = WireSegment(segment.net, start, end)
            designated = next((pin.key for pin in problem.pins.values()
                               if pin.net == segment.net and on_segment(start, pin.point, pin.escape)
                               and on_segment(end, pin.point, pin.escape)), None)
            allowed, _ = detector.segment_allowed(audit, segments, crossings,
                                                  allow_crossings=problem.options.allow_crossings,
                                                  escape_pin=designated)
            if not allowed:
                pin = problem.pins.get(designated)
                issues.append(_diagnostic("UNSAFE_ROUTING_SEGMENT", "Route outside component bodies/clearance and foreign pins, corridors, or conductive contacts",
                                          circuit=circuit, net=segment.net,
                                          component=pin.terminal.component if pin else None,
                                          pin=pin.terminal.pin if pin else None,
                                          expected="collision-free segment or designated outward escape", actual=[start, end]))
    for net in geometries:
        for flag in net.flags:
            # A direct flag on its own canonical pin is legal, even at a body
            # boundary. Other flags must obey the same point collision policy.
            own_pins = [pin for pin in problem.pins.values() if pin.net == net.name and pin.point == flag]
            own_owners = {pin.terminal.component for pin in own_pins}
            direct_pin_allowed = bool(own_pins) and not (
                any(crossing.point == flag for crossing in crossings)
                or any(box_contains(obstacle.expanded, flag) and obstacle.component not in own_owners
                       for obstacle in problem.obstacles)
                or any(pin.net != net.name and on_segment(flag, pin.point, pin.escape)
                       for pin in problem.pins.values())
                or any(segment.net != net.name and on_segment(flag, segment.start, segment.end) for segment in segments))
            if not direct_pin_allowed and not detector.point_allowed(flag, net.name, segments, crossings):
                issues.append(_diagnostic("UNSAFE_ROUTING_FLAG", "Move the flag outside foreign geometry, reserved crossings and bodies (own-pin flags are allowed)",
                                          circuit=circuit, net=net.name, actual=flag))
    return issues

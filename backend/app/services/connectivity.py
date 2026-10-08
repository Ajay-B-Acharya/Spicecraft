"""Source-only electrical connectivity, extracted from the ASC exporter.

Only explicit wires join nodes. Component bodies, coordinates, routing, and pin
names that happen to look like supply labels never create electrical edges.
Pin definitions/aliases come from ``pin_maps``. Groups, members, and wire traces
retain source insertion order, which is also the Phase 6 router's input order.

``build_connectivity`` reports malformed source without repairing it. Its nets
are useful for inspection even when invalid; exporters must check diagnostics
before consuming them. ``validate_connectivity`` compares a possibly mutated
net model (including NetGeometry objects) with the captured explicit source.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.asc_validation import ERROR, WARNING, ExportDiagnostic
from app.services.production import checkpoint, current_execution
from app.services.pin_maps import (
    COMPONENT_KIND_ALIASES,
    COMPONENT_LIBRARY,
    canonical_pin_id,
    resolve_component_kind,
)

SPECIAL_NODE_FLAGS: dict[str, str] = {
    "0": "0", "GND": "0", "GROUND": "0",
    "VCC": "VCC", "VDD": "VCC", "PWR": "VCC",
    "VIN": "VIN", "IN": "VIN", "VOUT": "VOUT", "OUT": "VOUT",
}
SPECIAL_NODE_ORDER = {"GND": 0, "VCC": 1, "VIN": 2, "VOUT": 3}


def canonical_special_node(node: str) -> str | None:
    flag = SPECIAL_NODE_FLAGS.get(node.strip().upper())
    return "GND" if flag == "0" else flag


def parse_node(node: str) -> tuple[str, str]:
    raw = node.strip()
    if not raw:
        return "", ""
    if "." in raw:
        ref, pin = raw.split(".", 1)
        return "component", f"{ref.strip()}.{pin.strip()}"
    special = canonical_special_node(raw)
    return ("special", special) if special else ("net", raw)


def choose_special_node(nodes: list[str]) -> str:
    return min(nodes, key=lambda node: SPECIAL_NODE_ORDER.get(node, 99))


def component_identity(component: dict[str, Any], index: int) -> str:
    # Same naming fallback as Phase 6; missing identities are diagnosed below.
    return str(component.get("reference") or component.get("id") or f"X{index + 1}")


class _UnionFind:
    """The exporter's original ordered union-find, now shared with debugging."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self._parent.setdefault(item, item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while item != root:
            parent = self._parent[item]
            self._parent[item] = root
            item = parent
        return root

    def union(self, left: str, right: str) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left

    def groups(self) -> list[list[str]]:
        groups: dict[str, list[str]] = {}
        for node in self._parent:
            groups.setdefault(self.find(node), []).append(node)
        return list(groups.values())


@dataclass(frozen=True)
class LogicalPin:
    component: str
    pin: str

    @property
    def key(self) -> str:
        return f"{self.component}.{self.pin}"


@dataclass(frozen=True)
class SourceWire:
    index: int                         # one-based position in source wires
    source: str                        # canonical endpoint
    destination: str
    raw_source: str
    raw_destination: str
    identity: str = ""

    def format(self) -> str:
        return f"Wire #{self.index} ({self.raw_source} -> {self.raw_destination})"


@dataclass
class LogicalNet:
    name: str                          # ASC/diagnostic name: 0, VCC, N1, etc.
    members: list[str] = field(default_factory=list)
    pins: list[LogicalPin] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    special: str = ""                  # legacy label/hub policy, not a repair
    wire_indices: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class SourceGroup:
    """Immutable source partition, separate from mutable produced net lists."""

    name: str
    members: tuple[str, ...]
    pins: tuple[LogicalPin, ...]
    labels: tuple[str, ...]
    special: str


@dataclass
class ConnectivityModel:
    nets: list[LogicalNet]
    diagnostics: list[ExportDiagnostic]
    components: dict[str, dict[str, Any]]
    pin_refs: dict[str, LogicalPin]
    wires: list[SourceWire]
    source_groups: tuple[SourceGroup, ...]

    @property
    def has_errors(self) -> bool:
        return any(d.severity == ERROR for d in self.diagnostics)

    def canonical_node(self, node: str) -> str:
        kind, key = parse_node(node)
        if kind != "component":
            return key
        ref, pin = key.split(".", 1)
        component = self.components.get(ref)
        if component is None:
            return key
        return f"{component['_inst_name']}.{canonical_pin_id(component, pin)}"

    def trace_net(self, node_or_name: str) -> LogicalNet | None:
        key = self.canonical_node(node_or_name)
        # Node lookup wins over an anonymous display name such as N1.
        member_net = next((net for net in self.nets if key in net.members), None)
        return member_net or next((net for net in self.nets if net.name == node_or_name), None)

    def trace_pin(self, component: str, pin: str | None = None) -> LogicalNet | None:
        return self.trace_net(f"{component}.{pin}" if pin is not None else component)

    def wires_for_net(self, node_or_name: str) -> list[SourceWire]:
        net = self.trace_net(node_or_name)
        if net is None:
            return []
        return [wire for wire in self.wires if wire.index in net.wire_indices]

    def unconnected_pins(self) -> list[LogicalPin]:
        """Defined pins absent from explicit wires, not automatically errors."""
        connected = {pin.key for net in self.nets for pin in net.pins}
        return [pin for key, pin in self.pin_refs.items() if key not in connected]


def build_connectivity(
    circuit: dict[str, Any], *, mega_net_threshold: int | None = None
) -> ConnectivityModel:
    """Validate source endpoints and build its explicit electrical partition.

    Duplicate edges are harmless warnings (including reversed/aliased edges).
    Self edges and ambiguous representations are errors. Explicit GND--VCC is
    an error; other distinct labels sharing an explicitly wired group warn,
    because signal labels alone cannot establish a forbidden circuit topology.
    Optional mega-net warnings are purely size-based and never split a net.
    """
    diagnostics: list[ExportDiagnostic] = []
    if not isinstance(circuit, dict):
        diagnostics.append(ExportDiagnostic(ERROR, "INVALID_CIRCUIT", "Circuit must be an object"))
        return ConnectivityModel([], diagnostics, {}, {}, [], ())
    components: dict[str, dict[str, Any]] = {}
    pin_refs: dict[str, LogicalPin] = {}
    ambiguous: set[str] = set()
    raw_components = circuit.get("components", [])
    raw_wires = circuit.get("wires", [])
    if not isinstance(raw_components, list):
        diagnostics.append(ExportDiagnostic(ERROR, "INVALID_COMPONENTS", "Components must be a list"))
        raw_components = []
    if not isinstance(raw_wires, list):
        diagnostics.append(ExportDiagnostic(ERROR, "INVALID_WIRES", "Wires must be a list"))
        raw_wires = []

    for index, raw in enumerate(raw_components):
        checkpoint(iterations=1)
        if not isinstance(raw, dict):
            diagnostics.append(ExportDiagnostic(ERROR, "INVALID_COMPONENT", f"Component #{index + 1} must be an object"))
            continue
        inst = component_identity(raw, index)
        identities = [inst]
        comp_id = str(raw.get("id") or "").strip()
        if comp_id and comp_id not in identities:
            identities.append(comp_id)
        if not str(raw.get("reference") or raw.get("id") or "").strip():
            diagnostics.append(ExportDiagnostic(ERROR, "MISSING_COMPONENT_IDENTITY", "Component has neither reference nor id", component=inst))
        component = dict(raw, _inst_name=inst)
        for identity in identities:
            if not identity or identity != identity.strip() or "." in identity or any(c.isspace() for c in identity):
                diagnostics.append(ExportDiagnostic(ERROR, "INVALID_COMPONENT_IDENTITY", "Component identity must be a nonempty token without dots/whitespace", component=identity))
            if identity in components:
                ambiguous.add(identity)
                diagnostics.append(ExportDiagnostic(ERROR, "DUPLICATE_COMPONENT_IDENTITY", f"Identity '{identity}' belongs to multiple component definitions (id/reference collision)", component=identity))
            else:
                components[identity] = component

        type_kind = COMPONENT_KIND_ALIASES.get(str(raw.get("type") or "").strip().lower())
        value_kind = COMPONENT_KIND_ALIASES.get(str(raw.get("value") or "").strip().lower())
        if type_kind and value_kind and type_kind != value_kind:
            diagnostics.append(ExportDiagnostic(ERROR, "CONFLICTING_COMPONENT_DEFINITION", f"Type '{raw.get('type')}' defines {type_kind}, but value '{raw.get('value')}' defines {value_kind}; no definition was changed", component=inst))
        definition = COMPONENT_LIBRARY.get(resolve_component_kind(raw))
        if definition is None:
            diagnostics.append(ExportDiagnostic(ERROR, "UNSUPPORTED_COMPONENT", "Component is not currently supported by SpiceCraft; no symbol substitution is allowed", component=inst, stage="input_validation"))
        else:
            for pin in definition.pins:
                key = f"{inst}.{pin.id}"
                pin_refs.setdefault(key, LogicalPin(inst, pin.id))

    def endpoint(value: Any, context: str) -> str | None:
        if not isinstance(value, str):
            diagnostics.append(ExportDiagnostic(ERROR, "INVALID_ENDPOINT", f"{context}: endpoint must be a string"))
            return None
        kind, key = parse_node(value)
        if not key:
            diagnostics.append(ExportDiagnostic(ERROR, "EMPTY_ENDPOINT", f"{context}: endpoint is empty"))
            return None
        if kind != "component":
            if any(c.isspace() for c in key):
                diagnostics.append(ExportDiagnostic(ERROR, "INVALID_ENDPOINT", f"{context}: label must be a single token", net=key))
                return None
            return key
        ref, pin = key.split(".", 1)
        if not ref or not pin or "." in pin or any(c.isspace() for c in ref + pin):
            diagnostics.append(ExportDiagnostic(ERROR, "INVALID_ENDPOINT", f"{context}: expected Component.Pin", component=ref, pin=pin))
            return None
        if ref in ambiguous:
            diagnostics.append(ExportDiagnostic(ERROR, "AMBIGUOUS_COMPONENT", f"{context}: component identity is ambiguous", component=ref, pin=pin))
            return None
        component = components.get(ref)
        if component is None:
            diagnostics.append(ExportDiagnostic(ERROR, "MISSING_COMPONENT", f"{context}: references a component that does not exist", component=ref, pin=pin))
            return None
        inst = component["_inst_name"]
        pin_id = canonical_pin_id(component, pin)
        definition = COMPONENT_LIBRARY.get(resolve_component_kind(component))
        if definition is None or definition.pin(pin_id) is None:
            valid = [p.id for p in definition.pins] if definition else []
            diagnostics.append(ExportDiagnostic(ERROR, "UNRESOLVED_PIN", f"{context}: pin '{pin}' is not defined for '{resolve_component_kind(component)}'; valid pins: {valid}", component=inst, pin=pin))
            return None
        return f"{inst}.{pin_id}"

    def wire_endpoint(wire: dict[str, Any], primary: str, alias: str, index: int) -> tuple[str | None, str]:
        fields = [field for field in (primary, alias) if field in wire]
        if not fields:
            diagnostics.append(ExportDiagnostic(ERROR, "MISSING_ENDPOINT", f"Wire #{index}: missing {primary}/{alias}"))
            return None, ""
        resolved = [endpoint(wire[field], f"Wire #{index} {field}") for field in fields]
        if len(fields) == 2 and (resolved[0] != resolved[1] or (None in resolved and wire[primary] != wire[alias])):
            diagnostics.append(ExportDiagnostic(ERROR, "CONFLICTING_WIRE_ENDPOINT", f"Wire #{index}: {primary}={wire[primary]!r} disagrees with {alias}={wire[alias]!r}; no representation was selected"))
            return None, str(wire[primary])
        if None in resolved:
            return None, str(wire[fields[0]])
        return resolved[0], str(wire[fields[0]])

    uf = _UnionFind()
    wires: list[SourceWire] = []
    edges: dict[frozenset[str], int] = {}
    wire_ids: dict[str, tuple[frozenset[str], int]] = {}
    for index, wire in enumerate(raw_wires, 1):
        checkpoint(iterations=1)
        if not isinstance(wire, dict):
            diagnostics.append(ExportDiagnostic(ERROR, "INVALID_WIRE", f"Wire #{index} must be an object"))
            continue
        src, raw_src = wire_endpoint(wire, "source", "from", index)
        dst, raw_dst = wire_endpoint(wire, "destination", "to", index)
        identity = str(wire.get("id") or "").strip()
        edge = frozenset(node for node in (src, dst) if node is not None)
        if identity:
            if identity in wire_ids:
                old_edge, old_index = wire_ids[identity]
                severity = WARNING if edge == old_edge else ERROR
                diagnostics.append(ExportDiagnostic(severity, "DUPLICATE_WIRE_IDENTITY", f"Wire #{index} repeats id '{identity}' from wire #{old_index}"))
            else:
                wire_ids[identity] = (edge, index)
        if src is None or dst is None:
            continue
        if src == dst:
            diagnostics.append(ExportDiagnostic(ERROR, "SELF_WIRE", f"Wire #{index} ({raw_src} -> {raw_dst}) resolves to the same endpoint '{src}'", net=src))
            continue
        if edge in edges:
            diagnostics.append(ExportDiagnostic(WARNING, "DUPLICATE_WIRE", f"Wire #{index} duplicates wire #{edges[edge]} after alias resolution"))
        else:
            edges[edge] = index
        wires.append(SourceWire(index, src, dst, raw_src, raw_dst, identity))
        uf.union(src, dst)

    wire_indices_by_root: dict[str, list[int]] = {}
    for wire in wires:
        checkpoint(iterations=1)
        wire_indices_by_root.setdefault(uf.find(wire.source), []).append(wire.index)
    nets: list[LogicalNet] = []
    anonymous = 0
    reserved_labels = {node for node in uf._parent if node not in pin_refs}
    used_names: set[str] = set()
    for members in uf.groups():
        checkpoint(iterations=1)
        execution = current_execution()
        if execution is not None:
            execution.require('nets', len(nets) + 1)
        pins = [pin_refs[node] for node in members if node in pin_refs]
        labels = [node for node in members if node not in pin_refs]
        specials = [node for node in labels if node in SPECIAL_NODE_ORDER]
        special = choose_special_node(specials) if specials else ""
        if special:
            name = "0" if special == "GND" else special
        elif labels:
            name = labels[0]
        elif pins:
            anonymous += 1
            while f"N{anonymous}" in reserved_labels or f"N{anonymous}" in used_names:
                anonymous += 1
            name = f"N{anonymous}"
        else:
            name = f"label-group-{len(nets) + 1}"
        used_names.add(name)
        wire_indices = wire_indices_by_root[uf.find(members[0])]
        net = LogicalNet(name, members, pins, labels, special, wire_indices)
        nets.append(net)
        if len(labels) > 1:
            severity = ERROR if {"GND", "VCC"}.issubset(labels) else WARNING
            diagnostics.append(ExportDiagnostic(severity, "CONFLICTING_NET_LABELS", f"Explicit source wires {wire_indices} join distinct labels {labels}; source connectivity is retained, not repaired", net=name))
        if mega_net_threshold is not None and len(pins) > mega_net_threshold:
            diagnostics.append(ExportDiagnostic(WARNING, "MEGA_NET", f"Explicit net contains {len(pins)} pins, exceeding inspection threshold {mega_net_threshold}; no topology is inferred", net=name))
        if not pins:
            diagnostics.append(ExportDiagnostic(WARNING, "LABEL_ONLY_NET", "Explicit net has labels but no component pins; no ASC geometry can be emitted", net=name))

    # Annotate edge diagnostics with the final source net's stable display name.
    for position, diagnostic in enumerate(diagnostics):
        checkpoint(iterations=1)
        if diagnostic.net is not None:
            continue
        indices = [wire.index for wire in wires if diagnostic.message.startswith(f"Wire #{wire.index} ")]
        if indices:
            net = next((net for net in nets if indices[0] in net.wire_indices), None)
            if net:
                diagnostics[position] = ExportDiagnostic(diagnostic.severity, diagnostic.code, diagnostic.message, net=net.name, component=diagnostic.component, pin=diagnostic.pin)

    source_groups = tuple(SourceGroup(net.name, tuple(net.members), tuple(net.pins), tuple(net.labels), net.special) for net in nets)
    return ConnectivityModel(nets, diagnostics, components, pin_refs, wires, source_groups)


def validate_connectivity(
    source: ConnectivityModel | dict[str, Any], produced_nets: Iterable[Any] | None = None
) -> list[ExportDiagnostic]:
    """Compare produced memberships to explicit source, never to geometry.

    Accepts LogicalNet or NetGeometry objects (each has name and pins). Logical
    nets also validate label membership. Unwired definition pins are not errors
    unless a produced net unexpectedly contains them. A removed expected pin is
    FLOATING_PIN; a moved/added pin is UNEXPECTED_PIN. Net merges/splits and lost
    labels are errors. This validates the recorded model, not parsed ASC text.
    """
    model = source if isinstance(source, ConnectivityModel) else build_connectivity(source)
    actual_nets = list(model.nets if produced_nets is None else produced_nets)
    found = list(model.diagnostics)
    expected = {group.name: group for group in model.source_groups}
    expected_owner = {pin.key: group.name for group in model.source_groups for pin in group.pins}
    seen_names: set[str] = set()
    actual_owners: dict[str, list[str]] = {}
    for net in actual_nets:
        checkpoint(iterations=1)
        name = net.name
        if name in seen_names:
            found.append(ExportDiagnostic(ERROR, "DUPLICATE_NET", "Produced net name is repeated", net=name))
        seen_names.add(name)
        group = expected.get(name)
        expected_pins = {pin.key for pin in group.pins} if group else set()
        counts = Counter(f"{pin.component}.{pin.pin}" for pin in net.pins)
        for key, count in counts.items():
            component, pin = key.split(".", 1)
            actual_owners.setdefault(key, []).append(name)
            if count > 1:
                found.append(ExportDiagnostic(ERROR, "DUPLICATE_NET_PIN", "Produced net repeats a pin (repeated source edges do not repeat net membership)", net=name, component=component, pin=pin))
            if key not in expected_pins:
                owner = expected_owner.get(key)
                found.append(ExportDiagnostic(ERROR, "UNEXPECTED_PIN", f"Produced net contains a pin not assigned to it by explicit source; source net: {owner or '<unwired/undefined>'}", net=name, component=component, pin=pin))
        if hasattr(net, "members"):
            expected_members = set(group.members) if group else set()
            if set(net.members) != expected_members or set(counts) != {member for member in net.members if member in model.pin_refs}:
                found.append(ExportDiagnostic(ERROR, "NET_MEMBERSHIP_MISMATCH", "Produced members/pins differ from the explicit source partition", net=name))
            if len(net.members) != len(set(net.members)):
                found.append(ExportDiagnostic(ERROR, "DUPLICATE_NET_MEMBER", "Produced net repeats a node", net=name))
            if group and (set(net.labels) != set(group.labels) or net.special != group.special):
                found.append(ExportDiagnostic(ERROR, "NET_LABEL_MISMATCH", "Produced labels differ from explicit source", net=name))
        if group is None:
            found.append(ExportDiagnostic(ERROR, "UNEXPECTED_NET", "Produced net is absent from explicit source", net=name))
    for group in model.source_groups:
        # Label-only groups intentionally have no routed geometry.
        if group.pins and group.name not in seen_names:
            found.append(ExportDiagnostic(ERROR, "MISSING_NET", "Explicit source net is absent from produced nets", net=group.name))
        for pin in group.pins:
            owners = actual_owners.get(pin.key, [])
            if group.name not in owners:
                found.append(ExportDiagnostic(ERROR, "FLOATING_PIN", f"Pin is missing from its explicit source net; produced nets: {owners or '<none>'}", net=group.name, component=pin.component, pin=pin.pin))
            if len(owners) > 1:
                found.append(ExportDiagnostic(ERROR, "PIN_IN_MULTIPLE_NETS", f"Pin occurs in multiple produced nets: {owners}", net=group.name, component=pin.component, pin=pin.pin))
    return found


def trace_net(model: ConnectivityModel, node_or_name: str) -> LogicalNet | None:
    return model.trace_net(node_or_name)


def trace_pin(model: ConnectivityModel, component: str, pin: str | None = None) -> LogicalNet | None:
    return model.trace_pin(component, pin)

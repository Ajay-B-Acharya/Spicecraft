"""Topology-aware physical placement; electrical membership is read-only.

Small passive chains and active-device neighbourhoods receive conventional
placement hints. Unknown arrangements retain deterministic grid placement.
All anchors are derived from canonical pin offsets, never a second pin table.
"""
from __future__ import annotations

from typing import Any

from app.services.connectivity import ConnectivityModel
from app.services.grid_system import GridSystem
from app.services.production import checkpoint
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, resolve_component_kind


def _place(layout: dict, pin: str, point: tuple[int, int], rotation: str = "R0") -> dict:
    result = dict(layout)
    definition = COMPONENT_LIBRARY[resolve_component_kind(layout)]
    offset = PinResolver.resolve_pin_geometry(definition, pin, (0, 0), rotation, False).absolute
    result["_ltspice_anchor"] = GridSystem.snap_point((point[0] - offset[0], point[1] - offset[1]))
    result["_ltspice_rotation"] = rotation
    result["_ltspice_mirror"] = False
    return result


def refine_layout(model: ConnectivityModel, layouts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    checkpoint("layout")
    refs = list(model.components)
    unique = {}
    definitions = {}
    for ref in refs:
        checkpoint(iterations=1)
        unique[ref] = dict(layouts[ref])
        definitions[ref] = COMPONENT_LIBRARY.get(resolve_component_kind(unique[ref]))
    if not refs or any(definition is None for definition in definitions.values()):
        return layouts
    nets = {pin.key: net.name for net in model.nets for pin in net.pins}
    members = {net.name: {pin.key for pin in net.pins} for net in model.nets}
    labels = {net.name: set(net.labels) for net in model.nets}

    def net(ref: str, pin: str) -> str | None:
        return nets.get(f"{ref}.{pin}")

    def ports(ref: str) -> set[str]:
        return {nets[f"{ref}.{p.id}"] for p in definitions[ref].pins if f"{ref}.{p.id}" in nets}

    active = [ref for ref in refs if len(definitions[ref].pins) > 2]
    if len(refs) == 2 and all(len(definitions[r].pins) == 2 for r in refs):
        ground = next((r for r in refs if "0" in ports(r)), None)
        series = next((r for r in refs if r != ground), None)
        if ground and series:
            shared = ports(ground) & ports(series)
            if len(shared) == 1:
                common = next(iter(shared))
                a, b = definitions[series].pins
                c, d = definitions[ground].pins
                source_pin = a.id if net(series, b.id) == common else b.id
                join_pin = b.id if source_pin == a.id else a.id
                ground_join = c.id if net(ground, c.id) == common else d.id
                vertical = all(definitions[r].kind == "resistor" for r in refs)
                rotation = ("R0" if source_pin == a.id else "R180") if vertical else ("R270" if source_pin == a.id else "R90")
                unique[series] = _place(unique[series], source_pin, (160, 192), rotation)
                endpoint = PinResolver.resolve_pin_geometry(definitions[series], join_pin,
                    unique[series]["_ltspice_anchor"], rotation, False).absolute
                target = (endpoint[0], endpoint[1] + 96) if vertical else (endpoint[0] + 96, endpoint[1])
                unique[ground] = _place(unique[ground], ground_join, target,
                    "R0" if ground_join == c.id else "R180")
    elif len(active) == 1 and len(refs) <= 10:
        center = active[0]
        definition = definitions[center]
        unique[center]["_ltspice_anchor"] = (448, 336)
        unique[center]["_ltspice_rotation"] = "R0"
        assigned = {center}
        occupied_slots: dict[tuple[int, int], int] = {}
        for ref in refs:
            if ref == center or len(definitions[ref].pins) != 2:
                continue
            pins = definitions[ref].pins
            shared = ports(ref) & ports(center)
            if not shared:
                continue
            active_pins = {p.id for p in definition.pins if net(center, p.id) in shared}
            power = "VCC" in ports(ref)
            ground = "0" in ports(ref)
            orientation = "R0"
            attach = pins[0].id
            target = (800, 528)
            if definition.kind == "bc547":
                if "B" in active_pins:
                    target = (240, 240 if power else 464)
                    top_net = "VCC" if power else net(center, "B")
                    attach = next(p.id for p in pins if net(ref, p.id) == top_net)
                    orientation = "R0" if attach == pins[0].id else "R180"
                elif "C" in active_pins and power:
                    target = (512, 160)
                    attach = next(p.id for p in pins if net(ref, p.id) == "VCC")
                    orientation = "R0" if attach == pins[0].id else "R180"
                elif "C" in active_pins:
                    target = (672, 304)
                    attach = next(p.id for p in pins if net(ref, p.id) == net(center, "C"))
                    orientation = "R270" if attach == pins[0].id else "R90"
                elif "E" in active_pins:
                    target = (512, 528)
                    attach = next(p.id for p in pins if net(ref, p.id) == net(center, "E"))
                    orientation = "R0" if attach == pins[0].id else "R180"
            else:
                # Power-facing branches sit above timing/signal branches; ground
                # returns sit on the left of an IC, without inventing new nets.
                if power:
                    target = (736, 224)
                    attach = next(p.id for p in pins if net(ref, p.id) == "VCC")
                elif ground:
                    target = (224, 448)
                    attach = next(p.id for p in pins if net(ref, p.id) != "0")
                else:
                    target = (736, 432)
                    attach = pins[0].id
                orientation = "R0" if attach == pins[0].id else "R180"
            duplicate = occupied_slots.get(target, 0)
            occupied_slots[target] = duplicate + 1
            target = (target[0] + duplicate * 208, target[1])
            unique[ref] = _place(unique[ref], attach, target, orientation)
            assigned.add(ref)
        for index, ref in enumerate(r for r in refs if r not in assigned):
            if len(definitions[ref].pins) != 2:
                continue
            pins = definitions[ref].pins
            attach = next((p.id for p in pins if net(ref, p.id) != "0"), pins[0].id)
            unique[ref] = _place(unique[ref], attach, (800 + index * 208, 480),
                "R0" if attach == pins[0].id else "R180")
    elif not active:
        diodes = [r for r in refs if definitions[r].kind == "diode"]
        loads = [r for r in refs if r not in diodes]
        if len(diodes) == 4 and len(loads) == 1 and len(definitions[loads[0]].pins) == 2:
            load = loads[0]
            output = next((n for n in ports(load) if n != "0" and labels.get(n)), None)
            upper = [r for r in diodes if net(r, definitions[r].pins[1].id) == output]
            lower = [r for r in diodes if net(r, definitions[r].pins[0].id) == "0"]
            pairs = [(u, l) for u in upper for l in lower
                     if net(u, definitions[u].pins[0].id) == net(l, definitions[l].pins[1].id)]
            if len(pairs) == 2 and len({r for pair in pairs for r in pair}) == 4:
                for column, (up, low) in enumerate(sorted(pairs)):
                    x = 224 + column * 288
                    unique[up] = _place(unique[up], definitions[up].pins[1].id, (x, 224), "R180")
                    unique[low] = _place(unique[low], definitions[low].pins[1].id, (x, 416), "R180")
                load_pin = next(p.id for p in definitions[load].pins if net(load, p.id) == output)
                unique[load] = _place(unique[load], load_pin, (736, 304),
                    "R0" if load_pin == definitions[load].pins[0].id else "R180")
    # Preserve reference/id aliases in the existing layout contract.
    result = dict(layouts)
    for ref, layout in unique.items():
        checkpoint(iterations=1)
        result[ref] = layout
        alias = str(layout.get("id", "")).strip()
        if alias:
            result[alias] = layout
    return result

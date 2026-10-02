"""Source-only connectivity and frozen Phase 6 symbol/header regressions.

Phase 7 intentionally replaces unsafe WIRE/FLAG bytes. Exact symbol/placement
bytes remain frozen; real LTspice tests separately establish routing correctness.
The original known-short ASC/netlist artifacts remain a negative control.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ERROR, WARNING, AscExportError, NetGeometry, PinPoint
from app.services.connectivity import (
    LogicalNet,
    LogicalPin,
    build_connectivity,
    trace_net,
    trace_pin,
    validate_connectivity,
)
from app.services.exporter_debugger import ExporterDebugger
from app.services.ltspice_exporter import generate_asc, generate_asc_with_diagnostics

CIRCUITS_DIR = BACKEND_ROOT / "circuits"

# Captured by running the exporter from e8bb314 in an isolated temp directory,
# filtering ONLY WIRE/FLAG lines. Phase 7 must change those unsafe route bytes,
# not SYMBOL/SYMATTR/header/placement. Not hashes of the new implementation.
PHASE6_SYMBOL_HEADER_HASHES = {
    "555_astable_multivibrator.json": "9f8ccab8f04ffaaee328013d37a2a026fa07207b135f0cdc00066288ab1a11dd",
    "common_emitter_amplifier.json": "e899404461d0e4d7d7e22d682fe9e85399612b37732a3c7fd9f6247d4c0c0c94",
    "led_blinker.json": "5c81dad93d32b6690fe866d937d70e1530b4dac0ce4ab96b8ed42f1070d93df4",
    "rc_high_pass_filter.json": "f4ca1f8e9dd7bfcdfca7513d7306b86874082c49d004d6d48e481ab20d4feeec",
    "rc_low_pass_filter.json": "3353cc048bcb8c62ab116d972a7fb28dabaae7d35fb13cfe62b8e72f83612920",
}

# Independent expectations taken from each bundled file's explicit wires.
# These are logical partitions only: the legacy ASC router can short them.
TEMPLATE_PARTITIONS = {
    "common_emitter_amplifier.json": {
        "VCC": {"R1.1", "R3.2"},
        "N1": {"R1.2", "Q1.B", "R2.1"},
        "0": {"R2.2", "C1.2"},
        "N2": {"Q1.C", "R3.1", "C2.1"},
        "N3": {"Q1.E", "C1.1"},
        "VOUT": {"C2.2"},
    },
    "555_astable_multivibrator.json": {
        "VCC": {"U1.8", "R1.2"},
        "0": {"U1.1", "C1.2"},
        "N1": {"U1.2", "U1.6", "R2.2", "C1.1"},
        "N2": {"U1.7", "R1.1", "R2.1"},
    },
    "led_blinker.json": {
        "VCC": {"R1.1"},
        "N1": {"R1.2", "Q1.B", "C1.1"},
        "N2": {"Q1.C", "D1.A"},
        "N3": {"D1.K", "R2.1"},
        "0": {"R2.2", "C1.2"},
    },
    "rc_low_pass_filter.json": {
        "VIN": {"R1.1"}, "VOUT": {"R1.2", "C1.1"}, "0": {"C1.2"},
    },
    "rc_high_pass_filter.json": {
        "VIN": {"C1.1"}, "VOUT": {"C1.2", "R1.1"}, "0": {"R1.2"},
    },
}


def load_circuit(filename: str) -> dict:
    return json.loads((CIRCUITS_DIR / filename).read_text(encoding="utf-8"))


def component(ref: str, kind: str = "resistor", **extra) -> dict:
    return {"reference": ref, "type": kind, **extra}


def circuit(components=None, edges=()) -> dict:
    return {
        "components": components if components is not None else [component("R1"), component("R2")],
        "wires": [{"from": src, "to": dst} for src, dst in edges],
    }


def codes(diagnostics, severity=None) -> set[str]:
    return {d.code for d in diagnostics if severity is None or d.severity == severity}


def partition(model) -> dict[str, set[str]]:
    return {net.name: {pin.key for pin in net.pins} for net in model.nets}


class ConnectivityBasicsTests(unittest.TestCase):
    def test_explicit_edges_only_no_component_body_union(self) -> None:
        model = build_connectivity(circuit(edges=[("VIN", "R1.1"), ("R1.2", "R2.1"), ("R2.2", "GND")]))
        self.assertEqual(partition(model), {"VIN": {"R1.1"}, "N1": {"R1.2", "R2.1"}, "0": {"R2.2"}})
        self.assertEqual(validate_connectivity(model), [])

    def test_multiple_edges_referencing_one_pin_are_normal(self) -> None:
        model = build_connectivity(circuit(
            [component("R1"), component("R2"), component("Q1", "transistor", value="BC547")],
            [("R1.2", "Q1.B"), ("Q1.base", "R2.1")],
        ))
        self.assertEqual(model.nets[0].members, ["R1.2", "Q1.B", "R2.1"])
        self.assertEqual([pin.key for pin in model.nets[0].pins], ["R1.2", "Q1.B", "R2.1"])
        self.assertEqual(model.nets[0].wire_indices, [1, 2])
        self.assertEqual(model.diagnostics, [])

    def test_identity_and_transistor_numeric_aliases(self) -> None:
        source = circuit([component("Q1", "npn", id="transistor-id"), component("R1", "res")],
                         [("transistor-id.2", "R1.PLUS"), ("Q1.BASE", "VIN")])
        model = build_connectivity(source)
        self.assertEqual(partition(model), {"VIN": {"Q1.B", "R1.1"}})
        self.assertIs(trace_pin(model, "transistor-id", "2"), trace_pin(model, "Q1.base"))
        self.assertEqual(model.diagnostics, [])

    def test_multipin_ne555_keeps_unwired_pins_separate(self) -> None:
        source = circuit([component("U1", "ic", value="NE555")],
                         [("VDD", "U1.VCC"), ("U1.GROUND", "0"), ("U1.TRIG", "U1.THR")])
        model = build_connectivity(source)
        self.assertEqual(partition(model), {"VCC": {"U1.8"}, "0": {"U1.1"}, "N1": {"U1.2", "U1.6"}})
        self.assertEqual({pin.key for pin in model.unconnected_pins()}, {"U1.3", "U1.4", "U1.5", "U1.7"})
        self.assertEqual(validate_connectivity(model), [])

    def test_empty_circuit_and_unwired_definitions_are_valid(self) -> None:
        self.assertEqual(validate_connectivity({}), [])
        model = build_connectivity(circuit())
        self.assertEqual(model.nets, [])
        self.assertEqual(len(model.unconnected_pins()), 4)
        self.assertEqual(validate_connectivity(model), [])

    def test_led_diode_capacitor_aliases_use_existing_definitions(self) -> None:
        model = build_connectivity(circuit(
            [component("D1", "led"), component("D2", "diode"), component("C1", "cap")],
            [("D1.ANODE", "D2.A"), ("D2.2", "C1.K"), ("D1.2", "C1.LEFT")],
        ))
        self.assertEqual(partition(model), {"N1": {"D1.A", "D2.1"}, "N2": {"D2.2", "C1.2"}, "N3": {"D1.K", "C1.1"}})
        self.assertEqual(model.diagnostics, [])

    def test_same_coordinates_never_union_distinct_pins(self) -> None:
        source = circuit([component("R1", _ltspice_anchor=(0, 0)), component("R2", _ltspice_anchor=(0, 0))],
                         [("R1.1", "VIN"), ("R2.1", "VOUT")])
        model = build_connectivity(source)
        self.assertEqual(partition(model), {"VIN": {"R1.1"}, "VOUT": {"R2.1"}})
        self.assertIsNot(trace_pin(model, "R1.1"), trace_pin(model, "R2.1"))
        self.assertEqual(model.diagnostics, [])

    def test_layout_fields_do_not_affect_partition_or_source(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        before = copy.deepcopy(source)
        expected = partition(build_connectivity(source))
        self.assertEqual(source, before)
        for index, comp in enumerate(source["components"]):
            comp.update(position={"x": index * -1.5, "y": 999}, rotation=45,
                        _ltspice_anchor=(0, 0), _ltspice_rotation="INVALID", _ltspice_mirror=True)
        self.assertEqual(partition(build_connectivity(source)), expected)
        self.assertEqual(build_connectivity(source).diagnostics, [])

    def test_source_member_iteration_order_is_retained(self) -> None:
        model = build_connectivity(circuit(edges=[("R2.2", "GND"), ("VIN", "R1.1"), ("R1.2", "R2.1")]))
        self.assertEqual([net.name for net in model.nets], ["0", "VIN", "N1"])
        self.assertEqual([net.members for net in model.nets], [["R2.2", "GND"], ["VIN", "R1.1"], ["R1.2", "R2.1"]])


class ConnectivitySourceDiagnosticsTests(unittest.TestCase):
    def test_missing_invalid_and_empty_endpoints(self) -> None:
        cases = [
            ({"from": "R1.1"}, "MISSING_ENDPOINT"),
            ({"from": " ", "to": "R1.1"}, "EMPTY_ENDPOINT"),
            ({"from": None, "to": "R1.1"}, "INVALID_ENDPOINT"),
            ({"from": 2, "to": "R1.1"}, "INVALID_ENDPOINT"),
            ({"from": "R1.", "to": "GND"}, "INVALID_ENDPOINT"),
            ({"from": ".1", "to": "GND"}, "INVALID_ENDPOINT"),
            ({"from": "R1.1.extra", "to": "GND"}, "INVALID_ENDPOINT"),
            ({"from": "bad label", "to": "R1.1"}, "INVALID_ENDPOINT"),
            ({"from": "R99.1", "to": "GND"}, "MISSING_COMPONENT"),
            ({"from": "R1.9", "to": "GND"}, "UNRESOLVED_PIN"),
        ]
        for wire, expected in cases:
            with self.subTest(wire=wire):
                source = circuit()
                source["wires"] = [wire]
                model = build_connectivity(source)
                self.assertIn(expected, codes(model.diagnostics, ERROR))
                self.assertEqual(model.nets, [])
                asc, diagnostics = generate_asc_with_diagnostics(source)
                self.assertEqual(asc, "")
                self.assertIn(expected, codes(diagnostics, ERROR))
                with self.assertRaises(AscExportError):
                    generate_asc(source)

    def test_malformed_collections_are_diagnostics_not_crashes(self) -> None:
        for source, expected in [
            ([], "INVALID_CIRCUIT"),
            (None, "INVALID_CIRCUIT"),
            ({"components": None}, "INVALID_COMPONENTS"),
            ({"wires": {}}, "INVALID_WIRES"),
            ({"components": [None]}, "INVALID_COMPONENT"),
            ({"wires": ["R1.1"]}, "INVALID_WIRE"),
        ]:
            with self.subTest(source=source):
                self.assertIn(expected, codes(validate_connectivity(source), ERROR))
                self.assertEqual(generate_asc_with_diagnostics(source)[0], "")

    def test_component_id_reference_collisions_never_overwrite_silently(self) -> None:
        definitions = [
            [component("R1"), component("R1")],
            [component("R1", id="same"), component("R2", id="same")],
            [component("R1", id="R2"), component("R2")],
        ]
        for components in definitions:
            with self.subTest(components=components):
                source = circuit(components)
                self.assertIn("DUPLICATE_COMPONENT_IDENTITY", codes(build_connectivity(source).diagnostics, ERROR))
                with self.assertRaises(AscExportError):
                    generate_asc(source)
        good = build_connectivity(circuit([component("R1", id="R1")]))
        self.assertEqual(good.diagnostics, [])

    def test_ambiguous_identity_endpoint_is_not_resolved(self) -> None:
        model = build_connectivity(circuit([component("R1", id="R2"), component("R2")], [("R2.1", "GND")]))
        self.assertIn("AMBIGUOUS_COMPONENT", codes(model.diagnostics, ERROR))
        self.assertEqual(model.nets, [])

    def test_missing_or_malformed_component_identity(self) -> None:
        for comp, expected in [
            ({"type": "resistor"}, "MISSING_COMPONENT_IDENTITY"),
            (component("bad.ref"), "INVALID_COMPONENT_IDENTITY"),
            (component(" R1"), "INVALID_COMPONENT_IDENTITY"),
        ]:
            with self.subTest(comp=comp):
                self.assertIn(expected, codes(build_connectivity(circuit([comp])).diagnostics, ERROR))

    def test_type_value_definition_disagreement_is_not_repaired(self) -> None:
        source = circuit([component("R1", "resistor", value="BC547")])
        before = copy.deepcopy(source)
        model = build_connectivity(source)
        self.assertIn("CONFLICTING_COMPONENT_DEFINITION", codes(model.diagnostics, ERROR))
        self.assertEqual(source, before)
        self.assertEqual(generate_asc_with_diagnostics(source)[0], "")
        for kind, value in [("transistor", "BC547"), ("ic", "NE555"), ("res", "1k")]:
            with self.subTest(kind=kind):
                self.assertEqual(build_connectivity(circuit([component("X1", kind, value=value)])).diagnostics, [])

    def test_unknown_kind_warns_unwired_and_errors_when_wired(self) -> None:
        source = circuit([component("X1", "unknown")])
        self.assertEqual(codes(build_connectivity(source).diagnostics), {"UNKNOWN_COMPONENT_KIND"})
        self.assertIn("SYMBOL res", generate_asc(source))
        source["wires"] = [{"from": "X1.1", "to": "GND"}]
        self.assertIn("UNRESOLVED_PIN", codes(build_connectivity(source).diagnostics, ERROR))

    def test_duplicate_wires_are_warnings_not_repeated_pins(self) -> None:
        model = build_connectivity(circuit(edges=[("R1.2", "R2.1"), ("R2.PLUS", "R1.K")]))
        self.assertEqual(codes(model.diagnostics, WARNING), {"DUPLICATE_WIRE"})
        self.assertEqual(len(model.nets[0].pins), 2)
        self.assertEqual(model.nets[0].wire_indices, [1, 2])
        self.assertEqual(model.diagnostics[0].net, "N1")
        self.assertIn("Net: N1", model.diagnostics[0].format())

    def test_duplicate_wire_identity_warns_if_same_edge_errors_if_different(self) -> None:
        source = circuit(edges=[("R1.1", "VIN"), ("IN", "R1.A")])
        for wire in source["wires"]:
            wire["id"] = "w1"
        self.assertIn("DUPLICATE_WIRE_IDENTITY", codes(build_connectivity(source).diagnostics, WARNING))
        source["wires"][1]["to"] = "R2.1"
        self.assertIn("DUPLICATE_WIRE_IDENTITY", codes(build_connectivity(source).diagnostics, ERROR))

    def test_raw_canonical_and_special_self_wires_are_errors(self) -> None:
        for src, dst in [("R1.1", "R1.1"), ("R1.A", "R1.1"), ("GND", "0"), ("VDD", "PWR")]:
            with self.subTest(src=src, dst=dst):
                self.assertIn("SELF_WIRE", codes(build_connectivity(circuit(edges=[(src, dst)])).diagnostics, ERROR))

    def test_dual_wire_fields_disagreement_including_empty_is_error(self) -> None:
        for fields in [
            {"from": "R1.1", "source": "R2.1", "to": "GND"},
            {"from": "R1.1", "source": "", "to": "GND"},
            {"from": "R1.1", "source": None, "to": "GND"},
            {"from": "R1.1", "to": "GND", "destination": "VCC"},
        ]:
            with self.subTest(fields=fields):
                source = circuit()
                source["wires"] = [fields]
                before = copy.deepcopy(source)
                model = build_connectivity(source)
                self.assertIn("CONFLICTING_WIRE_ENDPOINT", codes(model.diagnostics, ERROR))
                self.assertEqual(model.nets, [])
                self.assertEqual(source, before)

    def test_dual_wire_fields_canonical_equivalence_is_allowed(self) -> None:
        source = circuit([component("Q1", "transistor", id="q-id")])
        source["wires"] = [{"source": "q-id.2", "from": "Q1.base", "destination": "in", "to": "VIN"}]
        self.assertEqual(partition(build_connectivity(source)), {"VIN": {"Q1.B"}})
        self.assertEqual(build_connectivity(source).diagnostics, [])


class ConnectivityLabelsAndTracingTests(unittest.TestCase):
    def test_canonical_special_semantics(self) -> None:
        model = build_connectivity(circuit(edges=[("ground", "R1.1"), ("0", "R2.1"), ("IN", "R1.2"), ("OUT", "R2.2")]))
        self.assertEqual(partition(model), {"0": {"R1.1", "R2.1"}, "VIN": {"R1.2"}, "VOUT": {"R2.2"}})
        self.assertIs(trace_net(model, "GROUND"), trace_net(model, "0"))
        self.assertEqual(model.diagnostics, [])

    def test_special_pin_names_never_implicitly_join_labels(self) -> None:
        model = build_connectivity(circuit([component("U1", "ne555"), component("R1")], [("U1.VCC", "R1.1")]))
        self.assertEqual(partition(model), {"N1": {"U1.8", "R1.1"}})
        self.assertEqual(model.nets[0].labels, [])

    def test_explicit_power_ground_conflict_blocks_other_labels_warn(self) -> None:
        for labels, severity in [(('VCC', 'GND'), ERROR), (('VIN', 'VOUT'), WARNING), (('VCC', 'VOUT'), WARNING), (('bias', 'other'), WARNING)]:
            with self.subTest(labels=labels):
                source = circuit(edges=[(labels[0], "R1.1"), ("R1.1", labels[1])])
                before = copy.deepcopy(source)
                model = build_connectivity(source)
                conflict = next(d for d in model.diagnostics if d.code == "CONFLICTING_NET_LABELS")
                self.assertEqual(conflict.severity, severity)
                self.assertEqual(conflict.net, model.nets[0].name)
                self.assertEqual(set(model.nets[0].labels), set(labels))
                self.assertEqual(model.nets[0].wire_indices, [1, 2])
                self.assertEqual(source, before)
                if severity == ERROR:
                    with self.assertRaises(AscExportError):
                        generate_asc(source)
                else:
                    self.assertTrue(generate_asc(source))

    def test_custom_labels_merge_only_exact_spelling_and_have_named_output(self) -> None:
        model = build_connectivity(circuit(edges=[("bias", "R1.1"), ("bias", "R2.1"), ("BIAS", "R1.2")]))
        self.assertEqual(partition(model), {"bias": {"R1.1", "R2.1"}, "BIAS": {"R1.2"}})
        self.assertIn("Net bias", ExporterDebugger.format_connections(circuit(edges=[("bias", "R1.1")])))

    def test_anonymous_name_never_collides_with_source_label(self) -> None:
        model = build_connectivity(circuit(edges=[("R1.1", "R2.1"), ("N1", "R1.2")]))
        self.assertEqual(partition(model), {"N2": {"R1.1", "R2.1"}, "N1": {"R1.2"}})
        self.assertEqual(trace_net(model, "N1").pins, [LogicalPin("R1", "2")])
        self.assertEqual(validate_connectivity(model), [])

    def test_label_only_and_optional_mega_net_warnings_do_not_guess_topology(self) -> None:
        model = build_connectivity(circuit(edges=[("R1.1", "R2.1"), ("a", "b")]), mega_net_threshold=1)
        self.assertIn("MEGA_NET", codes(model.diagnostics, WARNING))
        self.assertIn("LABEL_ONLY_NET", codes(model.diagnostics, WARNING))
        self.assertEqual(len(model.nets), 2)
        self.assertFalse(model.has_errors)
        self.assertNotIn("MEGA_NET", codes(build_connectivity(circuit(edges=[("R1.1", "R2.1")])).diagnostics))

    def test_debugger_traces_named_nets_source_edges_and_pin_aliases(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        text = ExporterDebugger.trace_pin(source, "Q1", "base")
        self.assertIn("Net N1", text)
        for key in ("R1.2", "Q1.B", "R2.1"):
            self.assertIn(key, text)
        self.assertIn("Wire #2", text)
        self.assertIn("Wire #3", text)
        self.assertNotIn("Q1.C", text)
        named = ExporterDebugger.trace_net(source, "OUT")
        self.assertIn("Net VOUT", named)
        self.assertIn("C2.2", named)
        listing = ExporterDebugger.format_connections(source)
        self.assertIn("Net 0", listing)
        self.assertEqual(listing.count("\nNet "), 6)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            printed = ExporterDebugger.print_connections(source)
        self.assertEqual(buffer.getvalue().strip(), printed)
        self.assertIn("no explicit net", ExporterDebugger.trace_pin(source, "missing.1"))

    def test_debugger_reports_source_diagnostics_not_silent_skips(self) -> None:
        text = ExporterDebugger.format_connections(circuit(edges=[("R1.9", "GND")]))
        self.assertIn("Connectivity Diagnostics", text)
        self.assertIn("ERROR", text)
        self.assertIn("UNRESOLVED_PIN", text)
        self.assertIn("Component: R1", text)


class ProducedNetValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = build_connectivity(load_circuit("common_emitter_amplifier.json"))

    def test_unmodified_source_and_routed_memberships_validate(self) -> None:
        self.assertEqual(validate_connectivity(self.model), [])
        geometry = [NetGeometry(net.name, pins=[PinPoint(pin.component, pin.pin, (0, 0)) for pin in net.pins]) for net in self.model.nets]
        # All coordinates coincide: logical validation deliberately ignores them.
        self.assertEqual(validate_connectivity(self.model, geometry), [])

    def test_missing_expected_pin_is_floating_even_if_members_still_claim_it(self) -> None:
        self.model.nets[1].pins.remove(LogicalPin("Q1", "B"))
        diagnostics = validate_connectivity(self.model)
        floating = next(d for d in diagnostics if d.code == "FLOATING_PIN")
        self.assertEqual((floating.net, floating.component, floating.pin), ("N1", "Q1", "B"))
        self.assertIn("NET_MEMBERSHIP_MISMATCH", codes(diagnostics, ERROR))
        self.assertEqual(len(self.model.source_groups[1].pins), 3)

    def test_unexpected_pin_on_wrong_net_is_reported_with_source_net(self) -> None:
        self.model.nets[0].pins.append(LogicalPin("Q1", "B"))
        diagnostics = validate_connectivity(self.model)
        unexpected = next(d for d in diagnostics if d.code == "UNEXPECTED_PIN")
        self.assertEqual((unexpected.net, unexpected.component, unexpected.pin), ("VCC", "Q1", "B"))
        self.assertIn("source net: N1", unexpected.message)
        self.assertIn("PIN_IN_MULTIPLE_NETS", codes(diagnostics, ERROR))

    def test_moving_pin_detects_both_unexpected_and_floating(self) -> None:
        pin = self.model.nets[1].pins.pop(1)
        self.model.nets[0].pins.append(pin)
        diagnostics = validate_connectivity(self.model)
        self.assertIn("UNEXPECTED_PIN", codes(diagnostics, ERROR))
        self.assertIn("FLOATING_PIN", codes(diagnostics, ERROR))

    def test_unwired_and_undefined_produced_pins_are_unexpected(self) -> None:
        model = build_connectivity(circuit(edges=[("R1.1", "VIN")]))
        for pin in [LogicalPin("R1", "2"), LogicalPin("R99", "1"), LogicalPin("R1", "9")]:
            with self.subTest(pin=pin):
                actual = copy.deepcopy(model.nets)
                actual[0].pins.append(pin)
                self.assertIn("UNEXPECTED_PIN", codes(validate_connectivity(model, actual), ERROR))

    def test_removed_net_merged_net_and_split_net_are_errors(self) -> None:
        actual = copy.deepcopy(self.model.nets)
        actual.pop(0)
        self.assertIn("MISSING_NET", codes(validate_connectivity(self.model, actual), ERROR))
        actual = copy.deepcopy(self.model.nets)
        actual[0].pins.extend(actual.pop(1).pins)
        self.assertIn("UNEXPECTED_PIN", codes(validate_connectivity(self.model, actual), ERROR))
        actual = copy.deepcopy(self.model.nets)
        pin = actual[1].pins.pop()
        actual.append(LogicalNet("extra", [pin.key], [pin]))
        self.assertIn("UNEXPECTED_NET", codes(validate_connectivity(self.model, actual), ERROR))

    def test_duplicate_net_and_membership_mutations_are_errors(self) -> None:
        self.model.nets.append(copy.deepcopy(self.model.nets[0]))
        self.model.nets[1].pins.append(self.model.nets[1].pins[0])
        self.model.nets[1].members.append(self.model.nets[1].members[0])
        diagnostics = validate_connectivity(self.model)
        self.assertTrue({"DUPLICATE_NET", "DUPLICATE_NET_PIN", "DUPLICATE_NET_MEMBER"}.issubset(codes(diagnostics, ERROR)))

    def test_removed_or_changed_labels_are_not_hidden(self) -> None:
        self.model.nets[0].labels = ["VIN"]
        self.model.nets[0].special = "VIN"
        self.assertIn("NET_LABEL_MISMATCH", codes(validate_connectivity(self.model), ERROR))
        self.model.nets[0].members.remove("VCC")
        self.assertIn("NET_MEMBERSHIP_MISMATCH", codes(validate_connectivity(self.model), ERROR))


class BundledSourceRegressionTests(unittest.TestCase):
    def test_all_actual_templates_match_independent_explicit_partitions(self) -> None:
        self.assertEqual({path.name for path in CIRCUITS_DIR.glob("*.json")}, set(TEMPLATE_PARTITIONS))
        for filename, expected in TEMPLATE_PARTITIONS.items():
            with self.subTest(filename=filename):
                source = load_circuit(filename)
                before = copy.deepcopy(source)
                model = build_connectivity(source)
                self.assertEqual(partition(model), expected)
                self.assertEqual(validate_connectivity(model), [])
                self.assertEqual(source, before)

    def test_common_emitter_source_order_and_no_conventional_topology_repair(self) -> None:
        model = build_connectivity(load_circuit("common_emitter_amplifier.json"))
        self.assertEqual([net.name for net in model.nets], ["VCC", "N1", "0", "N2", "N3", "VOUT"])
        self.assertEqual(model.nets[0].members, ["VCC", "R1.1", "R3.2"])
        self.assertEqual(model.nets[1].members, ["R1.2", "Q1.B", "R2.1"])
        self.assertEqual(model.nets[3].members, ["Q1.C", "R3.1", "C2.1"])
        self.assertEqual([wire.index for wire in model.wires_for_net("Q1.collector")], [5, 9])
        self.assertEqual(model.trace_pin("Q1.emitter").name, "N3")
        self.assertEqual(model.trace_net("VOUT").members, ["C2.2", "VOUT"])
        self.assertEqual(model.unconnected_pins(), [])

    def test_common_emitter_aliases_and_layout_change_preserve_partition(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        aliases = {"Q1.B": "Q1.base", "Q1.C": "Q1.1", "Q1.E": "Q1.emitter", "VCC": "PWR", "GND": "GROUND", "OUT": "VOUT", "R1.1": "r-id.PLUS"}
        for comp in source["components"]:
            if comp["reference"] == "R1":
                comp["id"] = "r-id"
            comp.update(_ltspice_anchor=(1, 3), _ltspice_rotation="M270", position={"x": -123, "y": 789})
        for wire in source["wires"]:
            # Aliases may differ between equivalent representations.
            wire["source"] = aliases.get(wire["source"], wire["source"])
            wire["destination"] = aliases.get(wire["destination"], wire["destination"])
        self.assertEqual(partition(build_connectivity(source)), TEMPLATE_PARTITIONS["common_emitter_amplifier.json"])
        self.assertEqual(build_connectivity(source).diagnostics, [])

    def test_all_bundled_phase6_symbol_header_bytes_unchanged(self) -> None:
        for filename, expected in PHASE6_SYMBOL_HEADER_HASHES.items():
            with self.subTest(filename=filename):
                asc, diagnostics = generate_asc_with_diagnostics(load_circuit(filename), strict=True)
                self.assertTrue(asc)
                self.assertEqual(codes(diagnostics, ERROR), set())
                frozen = "\n".join(line for line in asc.splitlines()
                                   if not line.startswith(("WIRE ", "FLAG "))) + "\n"
                self.assertEqual(hashlib.sha256(frozen.encode("utf-8")).hexdigest(), expected)

    def test_model_validation_does_not_claim_physical_short_free_asc(self) -> None:
        from tools.verify_ltspice import compare_partitions, parse_netlist
        source = load_circuit("common_emitter_amplifier.json")
        self.assertEqual(validate_connectivity(source), [])
        # Independent actual Phase6.5 ASC/netlist, NOT today's safe export:
        # logical validation still makes no claim that this old artifact is safe.
        root = BACKEND_ROOT / "tests/artifacts/phase_6_5"
        asc = (root / "common_emitter_before.asc").read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(asc.encode("utf-8")).hexdigest(),
                         "22dc2630f44e4dc5261ea5dc1d24d5254f74667a18ec13729d9be816427dff93")
        # Stock-shaped independent ASY files make this negative parser test
        # portable without requiring a local LTspice installation.
        import tempfile
        from test_pin_geometry import ASY_PINS, SYMBOLS
        with tempfile.TemporaryDirectory() as directory:
            symbols = Path(directory)
            for kind, pins in ASY_PINS.items():
                path = symbols / (SYMBOLS[kind].replace("\\", "/") + ".asy")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n".join(
                    f"PIN {x} {y} NONE 0\nPINATTR SpiceOrder {order}"
                    for order, (x, y) in enumerate(pins.values(), 1)
                ), encoding="utf-8")
            actual = parse_netlist(asc, (root / "common_emitter_before.net").read_text(encoding="utf-8"),
                                   symbol_roots=[symbols])
        report = compare_partitions(TEMPLATE_PARTITIONS["common_emitter_amplifier.json"], actual)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.shorts), 1)
        self.assertEqual(report.shorts[0]["actual_node"], "0")
        # New Phase7 geometry is safe, while the historical fixture stays bad.
        current, diagnostics = generate_asc_with_diagnostics(source, strict=True)
        self.assertTrue(current)
        self.assertEqual(codes(diagnostics, ERROR), set())
        self.assertTrue(generate_asc(source, strict=True))

    def test_exporter_checks_produced_pins_against_source_model(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        model = build_connectivity(source)
        original = validate_connectivity

        def mutate_geometry(model, produced_nets=None):
            if produced_nets is not None:
                produced_nets[0].pins.append(PinPoint("Q1", "B", (0, 0)))
            return original(model, produced_nets)

        with patch("app.services.ltspice_exporter.validate_connectivity", side_effect=mutate_geometry):
            with self.assertRaises(AscExportError) as ctx:
                generate_asc(source)
        self.assertIn("UNEXPECTED_PIN", codes(ctx.exception.diagnostics, ERROR))
        self.assertEqual(validate_connectivity(model), [])

    def test_exporter_fails_before_placement_on_source_errors(self) -> None:
        with patch("app.services.ltspice_exporter.place_component") as placement:
            with self.assertRaises(AscExportError):
                generate_asc(circuit(edges=[("R1.9", "GND")]))
        placement.assert_not_called()


class CircuitsApiLogicalValidationTests(unittest.TestCase):
    @staticmethod
    def api_payload(source: dict):
        from app.schemas.circuit import CircuitUpdateRequest
        return CircuitUpdateRequest.model_validate({
            "id": "test-circuit", "name": "Test", "description": "", "category": "Test", "tags": [], **source,
        })

    def test_put_rejects_logical_errors_before_repository_write(self) -> None:
        from fastapi import HTTPException
        from app.routers import circuits
        source = circuit(edges=[("R1.9", "GND")])
        with patch.object(circuits.repository, "get_circuit_by_id", return_value={"id": "test-circuit"}), patch.object(circuits.repository, "update_circuit") as save:
            with self.assertRaises(HTTPException) as ctx:
                circuits.update_circuit("test-circuit", self.api_payload(source))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("UNRESOLVED_PIN", "\n".join(ctx.exception.detail))
        save.assert_not_called()

    def test_put_allows_warnings_and_unwired_definition_pins(self) -> None:
        from app.routers import circuits
        source = circuit(edges=[("R1.1", "VIN"), ("IN", "R1.A")])
        with patch.object(circuits.repository, "get_circuit_by_id", return_value={"id": "test-circuit"}), patch.object(circuits.repository, "update_circuit", return_value={"id": "test-circuit"}) as save:
            result = circuits.update_circuit("test-circuit", self.api_payload(source))
        self.assertEqual(result, {"id": "test-circuit"})
        save.assert_called_once()
        self.assertEqual(save.call_args.args[1]["wires"], source["wires"])

    def test_export_errors_use_existing_422_shape(self) -> None:
        from fastapi import HTTPException
        from app.routers import circuits
        with patch.object(circuits.repository, "get_circuit_by_id", return_value=circuit(edges=[("R1.1", "R1.1")])):
            with self.assertRaises(HTTPException) as ctx:
                circuits.export_circuit_asc("test-circuit")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIsInstance(ctx.exception.detail, list)
        self.assertIn("SELF_WIRE", "\n".join(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()

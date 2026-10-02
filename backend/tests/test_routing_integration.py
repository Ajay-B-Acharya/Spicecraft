"""Phase 7 source -> pins -> router -> ASC -> real LTspice equivalence.

Frontend compiler tests are separate: these tests consume its canonical JSON
wire contract. Expected partitions and ASY coordinates are frozen independent
fixture data, never recovered from the router or exporter being tested.
"""
from __future__ import annotations

from collections import Counter
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ERROR, WARNING, AscExportError, ExportDiagnostic, WireSegment
from app.services.connectivity import build_connectivity, validate_connectivity
from app.services.exporter_debugger import ExporterDebugger
from app.services.ltspice_exporter import generate_asc, generate_asc_with_diagnostics, generate_asc_with_routing
from app.services.routing import RoutedFlag, RoutingResult, route_nets
from test_connectivity import TEMPLATE_PARTITIONS, circuit, component, load_circuit
from test_pin_geometry import parse_asc, pin_world_positions
from tools.verify_ltspice import (
    compare_partitions, discover_ltspice_executable, discover_symbol_roots,
    parse_netlist, read_ltspice_text, run_ltspice_netlist,
)

# Pins absent from the bundled JSON's explicit wires. The partition oracle
# includes these independent singleton nodes, not just actively routed pins.
UNWIRED_TEMPLATE_PINS = {
    "555_astable_multivibrator.json": {"U1.3", "U1.4", "U1.5"},
    "common_emitter_amplifier.json": set(),
    "led_blinker.json": {"Q1.E"},
    "rc_high_pass_filter.json": set(),
    "rc_low_pass_filter.json": set(),
}


def expected_partition(filename: str) -> dict[str, set[str]]:
    return {**TEMPLATE_PARTITIONS[filename],
            **{f"unwired:{pin}": {pin} for pin in UNWIRED_TEMPLATE_PINS[filename]}}


def error_codes(diagnostics) -> set[str]:
    return {d.code for d in diagnostics if d.severity == ERROR}


class RoutingIntegrationTests(unittest.TestCase):
    def test_all_templates_preserve_source_and_serialize_exact_router_geometry(self) -> None:
        for filename, expected in TEMPLATE_PARTITIONS.items():
            with self.subTest(filename=filename):
                source = load_circuit(filename)
                before = copy.deepcopy(source)
                model = build_connectivity(source)
                self.assertEqual({net.name: {pin.key for pin in net.pins} for net in model.nets}, expected)
                asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
                self.assertEqual(error_codes(diagnostics), set(), diagnostics)
                self.assertTrue(asc)
                self.assertIsNotNone(routed)
                self.assertTrue(routed.ok)
                self.assertEqual(validate_connectivity(model, routed.net_geometries), [])
                symbols, wires, flags = parse_asc(asc)
                independent_pins = pin_world_positions(symbols)
                self.assertEqual(set(f"{ref}.{pin}" for ref, pin in independent_pins),
                                 set().union(*expected_partition(filename).values()))
                for net in routed.net_geometries:
                    self.assertEqual({f"{pin.component}.{pin.pin}" for pin in net.pins}, expected[net.name])
                    for pin in net.pins:
                        self.assertEqual(pin.point, independent_pins[(pin.component, pin.pin)])
                    for segment in net.segments:
                        self.assertIn(segment.orientation, ("horizontal", "vertical"))
                        self.assertEqual(segment.net, net.name)
                self.assertEqual(Counter(wires), Counter((s.start, s.end)
                                 for net in routed.net_geometries for s in net.segments))
                self.assertEqual(Counter(flags), Counter((point, net.name)
                                 for net in routed.net_geometries for point in net.flags))
                self.assertEqual(Counter(flags), Counter((flag.point, flag.name) for flag in routed.flags))
                self.assertEqual(source, before)

    def test_debugger_reuses_exact_route_result_without_any_compute(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        with patch("app.services.ltspice_exporter.route_nets", wraps=route_nets) as router:
            asc, diagnostics, routed = generate_asc_with_routing(source)
            self.assertTrue(asc)
            text = ExporterDebugger.format_routing(routed, diagnostics)
            router.assert_called_once()
        self.assertIn("Routing Metrics", text)
        for net in routed.net_geometries:
            self.assertIn(f"Net {net.name}", text)
            for pin in net.pins:
                self.assertIn(f"{pin.component}.{pin.pin} -> {pin.point}", text)
        self.assertIn("nonconductive", text)
        self.assertIn("routing not produced", ExporterDebugger.format_routing(None))

    def test_custom_labels_are_canonical_route_flags_not_inferred_membership(self) -> None:
        source = circuit(edges=[("bias", "R1.1"), ("bias", "R2.1"),
                                ("AC+", "R1.2"), ("AC-", "R2.2")])
        asc, diagnostics, routed = generate_asc_with_routing(source)
        self.assertEqual(error_codes(diagnostics), set())
        self.assertEqual({name for _, name in parse_asc(asc)[2]}, {"bias", "AC+", "AC-"})
        self.assertEqual({net.name: {f"{pin.component}.{pin.pin}" for pin in net.pins}
                          for net in routed.net_geometries},
                         {"bias": {"R1.1", "R2.1"}, "AC+": {"R1.2"}, "AC-": {"R2.2"}})
        self.assertTrue(all(flag.name == flag.net for flag in routed.flags))

    def test_casefold_label_collision_blocks_without_merging_source(self) -> None:
        source = circuit(edges=[("bias", "R1.1"), ("BIAS", "R2.1")])
        self.assertEqual({net.name: {p.key for p in net.pins} for net in build_connectivity(source).nets},
                         {"bias": {"R1.1"}, "BIAS": {"R2.1"}})
        with patch("app.services.ltspice_exporter.route_nets") as router:
            asc, diagnostics = generate_asc_with_diagnostics(source)
        self.assertEqual(asc, "")
        self.assertIn("NET_LABEL_COLLISION", error_codes(diagnostics))
        router.assert_not_called()
        with self.assertRaises(AscExportError):
            generate_asc(source, strict=False)

    def test_same_net_label_aliases_emit_one_canonical_flag(self) -> None:
        source = circuit(edges=[("bias", "R1.1"), ("R1.1", "BIAS")])
        asc, diagnostics, routed = generate_asc_with_routing(source)
        self.assertEqual(error_codes(diagnostics), set())
        self.assertEqual(len(parse_asc(asc)[2]), 1)
        self.assertEqual(routed.flags[0].name, "bias")
        self.assertIn("CONFLICTING_NET_LABELS", {d.code for d in diagnostics})

    def test_injected_route_failure_never_returns_plausible_artifact_in_any_mode(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        failed = RoutingResult(diagnostics=[ExportDiagnostic(ERROR, "ROUTING_FAILED", "No valid path")])
        for strict in (False, True):
            with self.subTest(strict=strict), patch("app.services.ltspice_exporter.route_nets", return_value=failed):
                asc, diagnostics = generate_asc_with_diagnostics(source, strict=strict)
                self.assertEqual(asc, "")
                self.assertIn("ROUTING_FAILED", error_codes(diagnostics))
                with self.assertRaises(AscExportError) as ctx:
                    generate_asc(source, strict=strict)
                self.assertIn("ROUTING_FAILED", error_codes(ctx.exception.diagnostics))
        with patch("app.services.ltspice_exporter.route_nets", side_effect=AscExportError(failed.diagnostics)):
            self.assertEqual(generate_asc_with_diagnostics(source)[0], "")

    def test_empty_success_result_cannot_hide_missing_nets(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        with patch("app.services.ltspice_exporter.route_nets", return_value=RoutingResult()):
            asc, diagnostics = generate_asc_with_diagnostics(source)
        self.assertEqual(asc, "")
        self.assertTrue({"MISSING_NET", "FLOATING_PIN"}.issubset(error_codes(diagnostics)))

    def test_missing_or_misnamed_flags_fail_without_inventing_label_position(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        for mode in ("missing", "wrong-name"):
            with self.subTest(mode=mode):
                _, _, routed = generate_asc_with_routing(source)
                if mode == "missing":
                    routed.net_geometries[0].flags = []
                    routed.flags = [flag for flag in routed.flags if flag.net != "VCC"]
                else:
                    flag = routed.flags[0]
                    routed.flags[0] = RoutedFlag(flag.net, flag.point, "INVENTED")
                with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
                    asc, diagnostics = generate_asc_with_diagnostics(source)
                self.assertEqual(asc, "")
                self.assertIn("NET_FLAG_MISMATCH", error_codes(diagnostics))

    def test_nonorthogonal_and_zero_length_injected_routes_block_export(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        for offset, code in [((16, 16), "NON_ORTHOGONAL_WIRE"), ((0, 0), "ZERO_LENGTH_WIRE")]:
            with self.subTest(code=code):
                _, _, routed = generate_asc_with_routing(source)
                net = routed.net_geometries[0]
                start = net.pins[0].point
                end = (start[0] + offset[0], start[1] + offset[1])
                net.segments.append(WireSegment(net.name, start, end))
                with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
                    with self.assertRaises(AscExportError) as ctx:
                        generate_asc(source, strict=False)
                self.assertIn(code, error_codes(ctx.exception.diagnostics))

    def test_router_cannot_mutate_logical_input_to_hide_a_merge(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        before = copy.deepcopy(source)

        def mutate(model, layouts):
            routed = route_nets(model, layouts)
            model.nets[0].pins.extend(model.nets.pop(1).pins)
            return routed

        with patch("app.services.ltspice_exporter.route_nets", side_effect=mutate):
            asc, diagnostics = generate_asc_with_diagnostics(source)
        self.assertEqual(asc, "")
        self.assertIn("UNEXPECTED_PIN", error_codes(diagnostics))
        self.assertEqual(source, before)

    def test_wrong_routed_pin_coordinate_fails_symbol_consistency_gate(self) -> None:
        from app.services.asc_validation import PinPoint
        source = load_circuit("common_emitter_amplifier.json")
        _, _, routed = generate_asc_with_routing(source)
        pin = routed.net_geometries[0].pins[0]
        routed.net_geometries[0].pins[0] = PinPoint(pin.component, pin.pin, (0, 0))
        with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
            asc, diagnostics = generate_asc_with_diagnostics(source)
        self.assertEqual(asc, "")
        self.assertIn("PIN_POSITION_MISMATCH", error_codes(diagnostics))

    def test_unsafe_foreign_pin_contact_blocks_even_nonstrict(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        _, _, routed = generate_asc_with_routing(source)
        net = routed.net_geometries[0]
        start, end = net.pins[0].point, routed.net_geometries[1].pins[0].point
        elbow = (end[0], start[1])
        net.segments.extend(WireSegment(net.name, a, b) for a, b in [(start, elbow), (elbow, end)] if a != b)
        for strict in (False, True):
            with self.subTest(strict=strict), patch("app.services.ltspice_exporter.route_nets", return_value=routed):
                asc, diagnostics = generate_asc_with_diagnostics(source, strict=strict)
                self.assertEqual(asc, "")
                self.assertIn("NET_SHORT", error_codes(diagnostics))
                with self.assertRaises(AscExportError):
                    generate_asc(source, strict=strict)

    def test_reserved_unwired_pin_contact_blocks_default_export(self) -> None:
        source = load_circuit("led_blinker.json")
        asc, _, routed = generate_asc_with_routing(source)
        pins = pin_world_positions(parse_asc(asc)[0])
        net = routed.net_geometries[0]
        start, end = net.pins[0].point, pins[("Q1", "E")]
        elbow = (end[0], start[1])
        net.segments.extend(WireSegment(net.name, a, b) for a, b in [(start, elbow), (elbow, end)] if a != b)
        with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
            with self.assertRaises(AscExportError) as ctx:
                generate_asc(source)
        contacts = [d for d in ctx.exception.diagnostics if d.component == "Q1" and d.pin == "E"]
        self.assertTrue(any(d.severity == ERROR and d.code in {"NET_SHORT", "WIRE_CROSSES_PIN"} for d in contacts))

    def test_flag_on_foreign_wire_blocks_export(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        _, _, routed = generate_asc_with_routing(source)
        net = routed.net_geometries[0]
        point = routed.net_geometries[1].segments[0].start
        net.flags = [point]
        routed.flags = [RoutedFlag(flag.net, point, flag.name) if flag.net == net.name else flag
                        for flag in routed.flags]
        with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
            with self.assertRaises(AscExportError) as ctx:
                generate_asc(source)
        self.assertIn("NET_SHORT", error_codes(ctx.exception.diagnostics))

    def test_router_short_warning_is_promoted_and_returns_empty_text(self) -> None:
        source = load_circuit("common_emitter_amplifier.json")
        routed = RoutingResult(diagnostics=[ExportDiagnostic(WARNING, "NET_SHORT", "unsafe")])
        with patch("app.services.ltspice_exporter.route_nets", return_value=routed):
            asc, diagnostics = generate_asc_with_diagnostics(source)
        self.assertEqual(asc, "")
        self.assertIn("NET_SHORT", error_codes(diagnostics))


class RealLtspiceRoutingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = discover_ltspice_executable()
        if cls.executable is None:
            raise unittest.SkipTest("LTspice unavailable; set LTSPICE_EXECUTABLE for electrical integration")
        cls.symbol_roots = discover_symbol_roots(cls.executable)
        if not cls.symbol_roots:
            raise unittest.SkipTest("Stock LTspice symbol library unavailable")

    def netlist(self, asc: str, name: str) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory(prefix="spicecraft-phase7-") as directory:
            root = Path(directory)
            source = root / f"{name}.asc"
            source.write_text(asc, encoding="utf-8")
            output = run_ltspice_netlist(source, root / "outputs", executable=self.executable, timeout=30)
            text = read_ltspice_text(output)
            return parse_netlist(asc, text, symbol_roots=self.symbol_roots), text

    def test_all_five_actual_exports_match_complete_source_partition(self) -> None:
        for filename in TEMPLATE_PARTITIONS:
            with self.subTest(filename=filename):
                source = load_circuit(filename)
                asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
                self.assertEqual(error_codes(diagnostics), set())
                actual, netlist = self.netlist(asc, Path(filename).stem)
                report = compare_partitions(expected_partition(filename), actual)
                self.assertTrue(report.ok, f"{report.to_dict()}\n{netlist}")
                # Unwired pins must each remain independent of every other pin.
                for pin in UNWIRED_TEMPLATE_PINS[filename]:
                    self.assertEqual(sum(node.casefold() == actual[pin].casefold() for node in actual.values()), 1)
                for net in routed.net_geometries:
                    if net.flags:
                        for pin in net.pins:
                            self.assertEqual(actual[f"{pin.component}.{pin.pin}"].casefold(), net.name.casefold())
                print(f"LTspice Phase7 {filename}: {len(actual)} pins, no shorts/opens, "
                      f"{len(routed.crossings)} safe crossings")

    def test_custom_flags_preserve_actual_node_names_and_pin_partition(self) -> None:
        source = circuit([component("R1", value="1k"), component("R2", value="2k")],
                         [("bias", "R1.1"), ("bias", "R2.1"), ("AC+", "R1.2"), ("AC-", "R2.2")])
        asc = generate_asc(source, strict=True)
        actual, netlist = self.netlist(asc, "custom_flags")
        expected = {"bias": {"R1.1", "R2.1"}, "AC+": {"R1.2"}, "AC-": {"R2.2"}}
        self.assertTrue(compare_partitions(expected, actual).ok, netlist)
        self.assertEqual(actual["R1.1"].casefold(), "bias")
        self.assertEqual(actual["R1.2"].casefold(), "ac+")
        self.assertEqual(actual["R2.2"].casefold(), "ac-")


if __name__ == "__main__":
    unittest.main()

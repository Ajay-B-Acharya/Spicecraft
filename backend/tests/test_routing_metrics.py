"""Hand-computable Phase 7.5 measurement tests; no exporter or LTspice runs."""
from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import NetGeometry, PinPoint, WireSegment
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver
from app.services.routing.metrics import measure_routing
from app.services.routing.models import SafeCrossing


def geometry(name, pins=(), wires=(), flags=()):
    return NetGeometry(
        name,
        pins=[PinPoint(f"{name}_{index}", "1", point) for index, point in enumerate(pins)],
        flags=list(flags),
        segments=[WireSegment(name, start, end) for start, end in wires],
    )


def u_route(width, height):
    return geometry("U", [(0, 0), (width, 0)], [
        ((0, 0), (0, height)),
        ((0, height), (width, height)),
        ((width, height), (width, 0)),
    ])


class RoutingMetricsTests(unittest.TestCase):
    def test_empty_metrics_are_json_safe_and_explicitly_zero(self):
        metrics = measure_routing([])
        self.assertEqual(metrics, {
            "total_length": 0,
            "segment_count": 0,
            "bend_count": 0,
            "junction_count": 0,
            "crossing_count": 0,
            "terminal_pair_count": 0,
            "evaluated_pair_count": 0,
            "disconnected_pair_count": 0,
            "coincident_pair_count": 0,
            "detour_count": 0,
            "detour_ratio": 0.0,
            "max_detour_ratio": 0.0,
            "bounding_box": None,
            "area": 0,
            "reference_length": 0,
            "routing_efficiency": 0.0,
        })
        self.assertEqual(json.loads(json.dumps(metrics, allow_nan=False)), metrics)
        self.assertEqual(measure_routing([NetGeometry("empty")], {}), metrics)

    def test_straight_route_has_unit_efficiency_and_no_bends(self):
        net = geometry("N", [(-32, 16), (64, 16)], [((-32, 16), (64, 16))])
        metrics = measure_routing([net])
        self.assertEqual(metrics["total_length"], 96)
        self.assertEqual(metrics["segment_count"], 1)
        self.assertEqual(metrics["bend_count"], 0)
        self.assertEqual(metrics["junction_count"], 0)
        self.assertEqual(metrics["evaluated_pair_count"], 1)
        self.assertEqual(metrics["detour_count"], 0)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["reference_length"], 96)
        self.assertEqual(metrics["routing_efficiency"], 1.0)
        self.assertEqual(metrics["bounding_box"], [-32, 16, 64, 16])
        self.assertEqual(metrics["area"], 0)

    def test_l_shape_and_collinear_subdivisions_count_one_bend(self):
        for wires in [
            [((0, 0), (64, 0)), ((64, 0), (64, 32))],
            [((0, 0), (16, 0)), ((16, 0), (64, 0)),
             ((64, 0), (64, 16)), ((64, 16), (64, 32))],
        ]:
            with self.subTest(wires=wires):
                metrics = measure_routing([geometry("L", [(0, 0), (64, 32)], wires)])
                self.assertEqual(metrics["total_length"], 96)
                self.assertEqual(metrics["segment_count"], len(wires))
                self.assertEqual(metrics["bend_count"], 1)
                self.assertEqual(metrics["junction_count"], 0)
                self.assertEqual(metrics["detour_ratio"], 1.0)
                self.assertEqual(metrics["routing_efficiency"], 1.0)
                self.assertEqual(metrics["bounding_box"], [0, 0, 64, 32])
                self.assertEqual(metrics["area"], 2048)

    def test_unsplit_trunk_t_contact_is_one_junction_not_arbitrary_turns(self):
        net = geometry("T", [(-64, 0), (64, 0), (0, 64)], [
            ((-64, 0), (64, 0)), ((0, 0), (0, 64)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["segment_count"], 2)
        self.assertEqual(metrics["total_length"], 192)
        self.assertEqual(metrics["junction_count"], 1)
        self.assertEqual(metrics["bend_count"], 0)
        self.assertEqual(metrics["evaluated_pair_count"], 3)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["routing_efficiency"], 1.0)

    def test_hpwl_reference_remains_lower_bound_for_steiner_branch(self):
        # Terminal Manhattan MST = 128, but this Steiner T is only 96 long.
        net = geometry("T", [(0, 0), (64, 0), (32, 32)], [
            ((0, 0), (32, 0)), ((32, 0), (64, 0)), ((32, 0), (32, 32)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["total_length"], 96)
        self.assertEqual(metrics["reference_length"], 96)
        self.assertEqual(metrics["routing_efficiency"], 1.0)

    def test_multi_terminal_detour_ratio_uses_each_pair_not_net_length(self):
        net = geometry("U", [(0, 0), (0, 64), (64, 64), (64, 0)], [
            ((0, 0), (0, 64)), ((0, 64), (64, 64)), ((64, 64), (64, 0)),
        ])
        metrics = measure_routing([net])
        # Five shortest paths equal Manhattan; the open top takes 192 vs 64.
        self.assertEqual(metrics["total_length"], 192)
        self.assertEqual(metrics["reference_length"], 128)
        self.assertEqual(metrics["routing_efficiency"], 2 / 3)
        self.assertEqual(metrics["bend_count"], 2)
        self.assertEqual(metrics["terminal_pair_count"], 6)
        self.assertEqual(metrics["evaluated_pair_count"], 6)
        self.assertEqual(metrics["detour_count"], 1)
        self.assertAlmostEqual(metrics["detour_ratio"], 4 / 3)
        self.assertEqual(metrics["max_detour_ratio"], 3.0)

    def test_detour_requires_strict_ratio_and_inclusive_excess_thresholds(self):
        for width, height, ratio, detours in [
            (64, 32, 2.0, 1),    # Exactly 64 excess qualifies.
            (128, 32, 1.5, 0),   # Exactly 1.5 ratio does not qualify.
            (32, 16, 2.0, 0),    # Only 32 excess does not qualify.
            (64, 64, 3.0, 1),
        ]:
            with self.subTest(width=width, height=height):
                metrics = measure_routing([u_route(width, height)])
                self.assertEqual(metrics["total_length"], width + 2 * height)
                self.assertEqual(metrics["detour_ratio"], ratio)
                self.assertEqual(metrics["max_detour_ratio"], ratio)
                self.assertEqual(metrics["detour_count"], detours)

    def test_shortest_path_beats_longer_cycle_and_ignores_dead_end_for_detours(self):
        net = u_route(64, 64)
        net.segments.extend([WireSegment("U", (0, 0), (64, 0)),
                             WireSegment("U", (32, 0), (32, -160))])
        metrics = measure_routing([net])
        self.assertEqual(metrics["total_length"], 416)
        self.assertEqual(metrics["segment_count"], 5)
        self.assertEqual(metrics["bend_count"], 4)
        self.assertEqual(metrics["junction_count"], 1)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["detour_count"], 0)
        self.assertEqual(metrics["routing_efficiency"], 64 / 416)

    def test_interior_pins_are_graph_terminals_not_nearest_endpoints(self):
        net = geometry("N", [(16, 0), (48, 0)], [((0, 0), (64, 0))])
        metrics = measure_routing([net])
        self.assertEqual(metrics["evaluated_pair_count"], 1)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["reference_length"], 32)
        self.assertEqual(metrics["routing_efficiency"], 0.5)
        self.assertEqual(metrics["bend_count"], 0)

    def test_same_net_unsplit_x_does_not_connect_four_pin_terminals(self):
        net = geometry("X", [(-64, 0), (64, 0), (0, -64), (0, 64)], [
            ((-64, 0), (64, 0)), ((0, -64), (0, 64)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["total_length"], 256)
        self.assertEqual(metrics["segment_count"], 2)
        self.assertEqual(metrics["junction_count"], 0)
        self.assertEqual(metrics["bend_count"], 0)
        self.assertEqual(metrics["terminal_pair_count"], 6)
        self.assertEqual(metrics["evaluated_pair_count"], 2)
        self.assertEqual(metrics["disconnected_pair_count"], 4)
        self.assertIsNone(metrics["routing_efficiency"])
        self.assertEqual(metrics["detour_ratio"], 1.0)
        # Explicit endpoint in the same geometry really does make a junction.
        net.segments[:1] = [WireSegment("X", (-64, 0), (0, 0)),
                            WireSegment("X", (0, 0), (64, 0))]
        connected = measure_routing([net])
        self.assertEqual(connected["junction_count"], 1)
        self.assertEqual(connected["bend_count"], 0)
        self.assertEqual(connected["evaluated_pair_count"], 6)
        self.assertEqual(connected["disconnected_pair_count"], 0)
        self.assertEqual(connected["routing_efficiency"], 1.0)

    def test_foreign_unsplit_crossing_is_distinct_from_junction(self):
        horizontal = geometry("H", [(-64, 0), (64, 0)], [((-64, 0), (64, 0))])
        vertical = geometry("V", [(0, -64), (0, 64)], [((0, -64), (0, 64))])
        crossings = [SafeCrossing(("H", "V"), (0, 0)),
                     SafeCrossing(("V", "H"), (0, 0))]
        metrics = measure_routing([horizontal, vertical], crossings=crossings)
        self.assertEqual(metrics["crossing_count"], 1)
        self.assertEqual(metrics["junction_count"], 0)
        self.assertEqual(metrics["bend_count"], 0)
        self.assertEqual(metrics["segment_count"], 2)
        self.assertEqual(metrics["terminal_pair_count"], 2)
        self.assertEqual(metrics["evaluated_pair_count"], 2)
        self.assertEqual(metrics["detour_count"], 0)
        self.assertEqual(metrics["routing_efficiency"], 1.0)
        self.assertEqual(measure_routing([horizontal, vertical])["crossing_count"], 0)

    def test_foreign_route_never_supplies_shortcut_to_disconnected_net(self):
        broken = geometry("A", [(0, 0), (64, 0)], [
            ((0, 0), (16, 0)), ((48, 0), (64, 0)),
        ])
        bridge = geometry("B", wires=[((16, 0), (48, 0))])
        metrics = measure_routing([broken, bridge])
        self.assertEqual(metrics["disconnected_pair_count"], 1)
        self.assertEqual(metrics["evaluated_pair_count"], 0)
        self.assertEqual(metrics["detour_ratio"], 0.0)
        self.assertIsNone(metrics["routing_efficiency"])

    def test_flags_form_only_local_contacts_and_are_not_pair_endpoints(self):
        net = geometry("N", [(-64, 0), (0, 64)], [
            ((-64, 0), (64, 0)), ((0, -64), (0, 64)),
        ], flags=[(0, 0), (4096, 4096)])
        metrics = measure_routing([net])
        self.assertEqual(metrics["junction_count"], 1)
        self.assertEqual(metrics["evaluated_pair_count"], 1)
        self.assertEqual(metrics["terminal_pair_count"], 1)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["bounding_box"], [-64, -64, 64, 64])
        # A single NetGeometry/label name does not bridge disconnected islands.
        broken = geometry("N", [(0, 0), (64, 0)], flags=[(0, 0), (64, 0)])
        self.assertEqual(measure_routing([broken])["disconnected_pair_count"], 1)

    def test_coincident_duplicate_disconnected_and_singleton_pin_zero_cases(self):
        net = geometry("N", [(0, 0), (0, 0), (64, 0)])
        net.pins.append(net.pins[0])  # Same record is not a fourth terminal.
        metrics = measure_routing([net])
        self.assertEqual(metrics["terminal_pair_count"], 3)
        self.assertEqual(metrics["coincident_pair_count"], 1)
        self.assertEqual(metrics["disconnected_pair_count"], 2)
        self.assertEqual(metrics["evaluated_pair_count"], 0)
        self.assertEqual(metrics["detour_ratio"], 0.0)
        self.assertEqual(metrics["max_detour_ratio"], 0.0)
        self.assertEqual(metrics["detour_count"], 0)
        self.assertIsNone(metrics["routing_efficiency"])
        self.assertEqual(json.loads(json.dumps(metrics, allow_nan=False)), metrics)
        for pins, pairs, coincident in [([(16, 32)], 0, 0), ([(16, 32), (16, 32)], 1, 1)]:
            with self.subTest(pins=pins):
                isolated = measure_routing([geometry("N", pins)])
                self.assertEqual(isolated["terminal_pair_count"], pairs)
                self.assertEqual(isolated["coincident_pair_count"], coincident)
                self.assertEqual(isolated["routing_efficiency"], 0.0)
                self.assertEqual(isolated["bounding_box"], [16, 32, 16, 32])
                self.assertEqual(isolated["area"], 0)

    def test_wire_records_are_not_normalized_but_duplicate_graph_edges_are(self):
        net = geometry("N", [(0, 0), (64, 32)], [
            ((0, 0), (64, 0)), ((64, 0), (0, 0)), ((16, 0), (48, 0)),
            ((64, 0), (64, 32)), ((32, 0), (32, 0)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["segment_count"], 5)
        self.assertEqual(metrics["total_length"], 192)
        self.assertEqual(metrics["bend_count"], 1)
        self.assertEqual(metrics["junction_count"], 0)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["routing_efficiency"], 0.5)
        zero = measure_routing([geometry("Z", wires=[((16, 32), (16, 32))])])
        self.assertEqual(zero["segment_count"], 1)
        self.assertEqual(zero["total_length"], 0)
        self.assertEqual(zero["bounding_box"], [16, 32, 16, 32])
        self.assertEqual(zero["routing_efficiency"], 0.0)

    def test_zero_length_record_does_not_make_an_unsplit_x_conductive(self):
        net = geometry("N", [(-64, 0), (0, 64)], [
            ((-64, 0), (64, 0)), ((0, -64), (0, 64)), ((0, 0), (0, 0)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["disconnected_pair_count"], 1)
        self.assertEqual(metrics["junction_count"], 0)
        self.assertEqual(metrics["segment_count"], 3)

    def test_partial_collinear_overlap_connects_using_union_distance(self):
        net = geometry("N", [(0, 0), (96, 0)], [
            ((0, 0), (64, 0)), ((32, 0), (96, 0)),
        ])
        metrics = measure_routing([net])
        self.assertEqual(metrics["total_length"], 128)
        self.assertEqual(metrics["detour_ratio"], 1.0)
        self.assertEqual(metrics["routing_efficiency"], 0.75)
        self.assertEqual(metrics["bend_count"], 0)
        self.assertEqual(metrics["junction_count"], 0)

    def test_efficiency_sums_per_net_references_not_global_envelope(self):
        a = geometry("A", [(0, 0), (64, 0)], [((0, 0), (64, 0))])
        b = geometry("B", [(1024, 1024), (1088, 1024)], [((1024, 1024), (1088, 1024))])
        metrics = measure_routing([a, b])
        self.assertEqual(metrics["reference_length"], 128)
        self.assertEqual(metrics["total_length"], 128)
        self.assertEqual(metrics["routing_efficiency"], 1.0)
        self.assertEqual(metrics["bounding_box"], [0, 0, 1088, 1024])
        self.assertEqual(metrics["area"], 1088 * 1024)

    def test_diagonal_wire_is_rejected_not_reinterpreted_or_snapped(self):
        net = geometry("N", wires=[((0, 0), (16, 16))])
        with self.assertRaisesRegex(ValueError, "orthogonal"):
            measure_routing([net])
        off_grid = geometry("N", [(1, 3), (8, 3)], [((1, 3), (8, 3))])
        self.assertEqual(measure_routing([off_grid])["total_length"], 7)

    def test_iterables_order_and_endpoint_direction_are_deterministic_and_pure(self):
        nets = [u_route(64, 64), geometry("T", [(-64, 0), (64, 0), (0, 64)], [
            ((-64, 0), (64, 0)), ((0, 0), (0, 64)),
        ])]
        layouts = {"R1": {"type": "resistor", "_ltspice_anchor": [256, 128],
                           "_ltspice_rotation": "R90", "_ltspice_mirror": True}}
        crossings = [SafeCrossing(("T", "U"), (0, 32))]
        before = copy.deepcopy((nets, layouts, crossings))
        expected = measure_routing(nets, layouts, crossings)
        self.assertEqual(measure_routing(iter(nets), layouts, iter(crossings)), expected)
        shuffled = copy.deepcopy(nets)
        shuffled.reverse()
        for net in shuffled:
            net.pins.reverse()
            net.segments = [WireSegment(s.net, s.end, s.start) for s in reversed(net.segments)]
        self.assertEqual(measure_routing(shuffled, layouts, crossings), expected)
        self.assertEqual((nets, layouts, crossings), before)
        self.assertEqual(json.loads(json.dumps(expected, allow_nan=False)), expected)


class SymbolOccupancyMetricsTests(unittest.TestCase):
    def test_resistor_bounds_all_orientations_and_explicit_mirror(self):
        # Independently calculated from res.asy bounds (0,16)-(32,96).
        expected = {
            "R0": [64, 144, 96, 224], "R90": [-32, 128, 48, 160],
            "R180": [32, 32, 64, 112], "R270": [80, 96, 160, 128],
            "M0": [32, 144, 64, 224], "M90": [80, 128, 160, 160],
            "M180": [64, 32, 96, 112], "M270": [-32, 96, 48, 128],
        }
        for orientation, bounds in expected.items():
            forms = [(orientation, False)]
            if orientation.startswith("M"):
                forms.append(("R" + orientation[1:], True))
            for rotation, mirrored in forms:
                with self.subTest(rotation=rotation, mirrored=mirrored):
                    layouts = {"R1": {"type": "resistor", "_ltspice_anchor": (64, 128),
                                       "_ltspice_rotation": rotation, "_ltspice_mirror": mirrored}}
                    metrics = measure_routing([], layouts)
                    self.assertEqual(metrics["bounding_box"], bounds)
                    self.assertEqual(metrics["area"], 32 * 80)
                    self.assertEqual(metrics["total_length"], 0)
                    self.assertEqual(metrics["terminal_pair_count"], 0)
                    self.assertEqual(metrics["routing_efficiency"], 0.0)

    def test_bounds_include_symbol_artwork_not_only_pins_plus_all_routing_points(self):
        layouts = {"D1": {"type": "led", "_ltspice_anchor": (64, 128)}}
        # LED pins are at x=80; artwork extends to x=136.
        symbol_only = measure_routing([], layouts)
        self.assertEqual(symbol_only["bounding_box"], [64, 128, 136, 192])
        self.assertEqual(symbol_only["area"], 72 * 64)
        nets = [geometry("N", [(-32, -16)], [((192, 64), (192, 96))])]
        metrics = measure_routing(nets, layouts)
        self.assertEqual(metrics["bounding_box"], [-32, -16, 192, 192])
        self.assertEqual(metrics["area"], 224 * 208)
        self.assertEqual(metrics["reference_length"], 0)

    def test_bounds_use_library_and_resolver_including_definition_anchor(self):
        definition = replace(COMPONENT_LIBRARY["resistor"], anchor=(16, -32),
                             bounds=(-16, 0, 48, 112))
        layouts = {"R1": {"type": "resistor", "_ltspice_anchor": (64, 128),
                           "_ltspice_rotation": "M90"}}
        with patch.dict(COMPONENT_LIBRARY, {"resistor": definition}):
            with patch.object(PinResolver, "transform_offset", wraps=PinResolver.transform_offset) as transform:
                with patch.object(PinResolver, "resolve_all_pins", wraps=PinResolver.resolve_all_pins) as resolve:
                    metrics = measure_routing([], layouts)
        self.assertEqual(metrics["bounding_box"], [80, 80, 192, 144])
        self.assertEqual(metrics["area"], 112 * 64)
        self.assertGreaterEqual(transform.call_count, 4)
        resolve.assert_called_once_with(definition, (64, 128), "M90", False)

    def test_unknown_unplaced_and_bad_orientation_layouts_are_not_guessed(self):
        for layout in [
            {"type": "unknown", "_ltspice_anchor": (0, 0)},
            {"type": "resistor"},
            {"type": "resistor", "_ltspice_anchor": (0,)},
            {"type": "resistor", "_ltspice_anchor": (0, float("nan"))},
            {"type": "resistor", "_ltspice_anchor": (0, 0), "_ltspice_rotation": "R45"},
        ]:
            with self.subTest(layout=layout):
                with self.assertRaises(ValueError):
                    measure_routing([], {"X1": layout})


if __name__ == "__main__":
    unittest.main()

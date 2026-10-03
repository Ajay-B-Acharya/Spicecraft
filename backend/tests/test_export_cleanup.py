"""Scoped Phase 8 regressions for validation and export-only simplification."""
from __future__ import annotations

import copy
from dataclasses import replace
from itertools import permutations
from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import (
    ERROR, WARNING, AscExportError, ExportDiagnostic, NetGeometry, PinPoint,
    WireSegment, validate_net_geometry,
)
from app.services.export_cleanup import clean_export_geometry


def geometry(name, edges=(), pins=(), flags=()):
    return NetGeometry(
        name,
        pins=[PinPoint(f"{name}_R{index}", "1", point) for index, point in enumerate(pins)],
        flags=list(flags),
        segments=[WireSegment(name, start, end) for start, end in edges],
    )


def codes(nets, severity=None):
    return {d.code for d in validate_net_geometry(nets)
            if severity is None or d.severity == severity}


def endpoints(net):
    return {point for edge in net.segments for point in (edge.start, edge.end)}


def coverage(nets):
    """Integer physical coverage per net, independent of cleanup predicates."""
    result = {}
    for net in nets:
        points = set()
        for edge in net.segments:
            (x1, y1), (x2, y2) = edge.start, edge.end
            if y1 == y2:
                points.update((x, y1) for x in range(min(x1, x2), max(x1, x2) + 1))
            else:
                assert x1 == x2
                points.update((x1, y) for y in range(min(y1, y2), max(y1, y2) + 1))
        result[net.name] = points
    return result


class DistinctPhysicalEdgeValidationTests(unittest.TestCase):
    def test_duplicate_and_reversed_spur_still_has_dangling_endpoint(self):
        spur = WireSegment("N", (64, 0), (64, 32))
        for duplicate in (spur, replace(spur, start=spur.end, end=spur.start)):
            with self.subTest(duplicate=duplicate):
                net = geometry("N", [((0, 0), (128, 0))], [(0, 0), (128, 0)])
                net.segments.extend([spur, duplicate, duplicate])
                diagnostics = validate_net_geometry([net])
                invalid = [d for d in diagnostics if d.code == "INVALID_WIRE_ENDPOINT"]
                self.assertEqual([(d.severity, d.actual) for d in invalid], [(ERROR, (64, 32))])
                duplicates = [d for d in diagnostics if d.code == "DUPLICATE_WIRE_SEGMENT"]
                self.assertEqual(len(duplicates), 1)
                self.assertEqual(duplicates[0].severity, WARNING)
                self.assertIn("INVALID_WIRE_ENDPOINT", codes(clean_export_geometry([net]), ERROR))

    def test_duplicate_terminal_edge_is_warning_only(self):
        net = geometry("N", [((0, 0), (64, 0)), ((64, 0), (0, 0))], [(0, 0), (64, 0)])
        self.assertEqual(codes([net], ERROR), set())
        self.assertEqual(codes([net], WARNING), {"DUPLICATE_WIRE_SEGMENT"})
        self.assertEqual(validate_net_geometry(clean_export_geometry([net])), [])

    def test_malformed_incidence_cannot_support_valid_dangling_tip(self):
        tip = (32, 0)
        malformed = [
            (WireSegment("N", tip, tip), "ZERO_LENGTH_WIRE"),
            (WireSegment("N", tip, (64, 32)), "NON_ORTHOGONAL_WIRE"),
            (WireSegment("N", tip, (33, 0)), "OFF_GRID"),
            (WireSegment("foreign", tip, (64, 0)), "WIRE_NET_MISMATCH"),
        ]
        for edge, code in malformed:
            with self.subTest(code=code):
                net = geometry("N", [((0, 0), tip)], [(0, 0)])
                net.segments.append(edge)
                diagnostics = validate_net_geometry([net])
                self.assertIn(code, {d.code for d in diagnostics if d.severity == ERROR})
                self.assertIn(tip, {d.actual for d in diagnostics if d.code == "INVALID_WIRE_ENDPOINT"})

    def test_malformed_interior_cannot_supply_t_junction_support(self):
        for edge in (WireSegment("N", (0, -32), (64, 32)),
                     WireSegment("foreign", (32, -32), (32, 32)),
                     WireSegment("N", (32, -31), (32, 32))):
            with self.subTest(edge=edge):
                net = geometry("N", [((0, 0), (32, 0))], [(0, 0)])
                net.segments.append(edge)
                invalid = [d.actual for d in validate_net_geometry([net])
                           if d.code == "INVALID_WIRE_ENDPOINT"]
                self.assertIn((32, 0), invalid)

    def test_malformed_records_cannot_attach_pins_or_flags(self):
        for edge in (WireSegment("N", (0, 0), (0, 0)),
                     WireSegment("N", (0, 0), (32, 32)),
                     WireSegment("foreign", (0, 0), (32, 0)),
                     WireSegment("N", (0, 0), (33, 0))):
            with self.subTest(edge=edge):
                net = geometry("N", pins=[(0, 0)], flags=[edge.end])
                net.segments.append(edge)
                self.assertIn("PIN_NOT_CONNECTED", codes([net], ERROR))
                if edge.end != edge.start:
                    self.assertIn("FLAG_NOT_CONNECTED", codes([net], ERROR))
                    self.assertIn("NET_DISCONNECTED", codes([net], ERROR))

    def test_malformed_vertices_keep_grid_and_invalid_endpoint_diagnostics(self):
        net = geometry("N", [((1, 1), (17, 17))])
        diagnostics = validate_net_geometry([net])
        self.assertEqual({d.actual for d in diagnostics if d.code == "OFF_GRID"}, {(1, 1), (17, 17)})
        self.assertEqual({d.actual for d in diagnostics if d.code == "INVALID_WIRE_ENDPOINT"},
                         {(1, 1), (17, 17)})
        self.assertIn("NON_ORTHOGONAL_WIRE", codes([net], ERROR))

    def test_invalid_endpoint_identifies_missing_pin_and_optional_circuit(self):
        net = geometry("N", [((0, 0), (48, 0))], [(0, 0), (64, 0)])
        invalid = next(d for d in validate_net_geometry([net]) if d.code == "INVALID_WIRE_ENDPOINT")
        self.assertEqual((invalid.net, invalid.component, invalid.pin, invalid.expected, invalid.actual),
                         ("N", "N_R1", "1", (64, 0), (48, 0)))
        tagged = replace(invalid, circuit="phase8")
        self.assertEqual(tagged.format(), invalid.format() + "\nCircuit: phase8")
        self.assertIn("Circuit: phase8", str(AscExportError([tagged])))

    def test_diagnostic_positional_constructor_remains_compatible(self):
        diagnostic = ExportDiagnostic(ERROR, "CODE", "Message", "N", "R1", "2", (0, 0), (16, 0))
        self.assertIsNone(diagnostic.circuit)
        self.assertEqual(diagnostic.format(),
                         "Message [CODE]\nNet: N\nComponent: R1\nPin: 2\nExpected: (0, 0)\nActual: (16, 0)")
        tagged = ExportDiagnostic(ERROR, "CODE", "Message", "N", "R1", "2", (0, 0), (16, 0), "C")
        self.assertEqual(tagged.circuit, "C")


class ExportCleanupTests(unittest.TestCase):
    def assert_clean_valid(self, nets):
        self.assertEqual(codes(nets, ERROR), set())
        cleaned = clean_export_geometry(nets)
        self.assertEqual(codes(cleaned, ERROR), set())
        self.assertEqual(coverage(cleaned), coverage(nets))
        self.assertEqual(clean_export_geometry(cleaned), cleaned)
        return cleaned

    def test_empty_and_zero_only_inputs(self):
        self.assertEqual(clean_export_geometry([]), [])
        net = geometry("N", [((16, 16), (16, 16))], [(16, 16)], [(16, 16), (16, 16)])
        cleaned = clean_export_geometry([net])[0]
        self.assertEqual(cleaned.segments, [])
        self.assertEqual(cleaned.flags, [(16, 16)])
        self.assertEqual(cleaned.pins, net.pins)
        self.assertEqual(clean_export_geometry([NetGeometry("empty")]), [NetGeometry("empty")])

    def test_zero_length_is_blocking_before_cleanup_not_silently_repaired(self):
        net = geometry("N", [((0, 0), (64, 0)), ((32, 0), (32, 0))], [(0, 0), (64, 0)])
        raw = validate_net_geometry([net])
        self.assertIn("ZERO_LENGTH_WIRE", {d.code for d in raw if d.severity == ERROR})
        self.assertEqual(validate_net_geometry(clean_export_geometry([net])), [])
        self.assertIn("ZERO_LENGTH_WIRE", str(AscExportError(raw)))
        self.assertEqual(len(net.segments), 2)

    def test_repeated_collinear_joins_and_dedup_in_both_axes(self):
        for vertical in (False, True):
            def point(value):
                return (0, value) if vertical else (value, 0)
            with self.subTest(vertical=vertical):
                net = geometry("N", [(point(64), point(48)), (point(0), point(16)),
                                     (point(32), point(16)), (point(16), point(32)),
                                     (point(32), point(48))], [point(0), point(64)],
                               [point(64), point(0), point(64)])
                cleaned = self.assert_clean_valid([net])[0]
                self.assertEqual(cleaned.segments, [WireSegment("N", point(0), point(64))])
                self.assertEqual(cleaned.flags, [point(0), point(64)])

    def test_pin_and_flag_boundaries_are_protected(self):
        net = geometry("N", [((x, 0), (x + 16, 0)) for x in range(0, 96, 16)],
                       [(0, 0), (32, 0), (96, 0)], [(64, 0), (64, 0)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertEqual(cleaned.segments, [WireSegment("N", (0, 0), (32, 0)),
                                            WireSegment("N", (32, 0), (64, 0)),
                                            WireSegment("N", (64, 0), (96, 0))])
        self.assertEqual(cleaned.pins, net.pins)
        self.assertEqual(cleaned.flags, [(64, 0)])

    def test_interior_flag_is_not_a_request_to_split_wire(self):
        net = geometry("N", [((0, 0), (64, 0))], [(0, 0), (64, 0)], [(32, 0)])
        self.assertEqual(self.assert_clean_valid([net]), [net])

    def test_invalid_interior_pin_is_not_repaired_by_splitting(self):
        net = geometry("N", [((0, 0), (64, 0))], [(0, 0), (32, 0), (64, 0)])
        self.assertEqual(clean_export_geometry([net]), [net])
        self.assertIn("PIN_NOT_CONNECTED", codes(clean_export_geometry([net]), ERROR))

    def test_foreign_pin_and_flag_boundaries_are_also_protected(self):
        for terminal in (geometry("B", pins=[(32, 0)]), geometry("B", flags=[(32, 0)])):
            with self.subTest(terminal=terminal):
                net = geometry("A", [((0, 0), (32, 0)), ((32, 0), (64, 0))], [(0, 0), (64, 0)])
                self.assertEqual(clean_export_geometry([net, terminal])[0], net)

    def test_unrelated_cross_net_interior_x_stays_unsplit_after_other_joins(self):
        a = geometry("A", [((-64, 0), (-32, 0)), ((-32, 0), (32, 0)), ((32, 0), (64, 0))],
                     [(-64, 0), (64, 0)])
        b = geometry("B", [((0, -64), (0, 64))], [(0, -64), (0, 64)])
        cleaned = self.assert_clean_valid([a, b])
        self.assertEqual(cleaned[0].segments, [WireSegment("A", (-64, 0), (64, 0))])
        self.assertEqual(cleaned[1], b)
        self.assertNotIn((0, 0), endpoints(cleaned[0]) | endpoints(cleaned[1]))
        self.assertEqual(validate_net_geometry(cleaned), [])

    def test_same_net_unsplit_x_is_not_repaired_into_conductive_junction(self):
        net = geometry("N", [((-64, 0), (64, 0)), ((0, -64), (0, 64))],
                       [(-64, 0), (64, 0), (0, -64), (0, 64)])
        self.assertEqual(clean_export_geometry([net]), [net])
        self.assertIn("NET_DISCONNECTED", codes(clean_export_geometry([net]), ERROR))
        self.assertNotIn((0, 0), endpoints(clean_export_geometry([net])[0]))

    def test_degree_two_boundary_contacting_unsplit_perpendicular_is_preserved(self):
        net = geometry("N", [((-64, 0), (0, 0)), ((0, 0), (64, 0)), ((0, -64), (0, 64))],
                       [(-64, 0), (64, 0), (0, -64), (0, 64)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertEqual(set(cleaned.segments), set(net.segments))
        self.assertIn((0, 0), endpoints(cleaned))

    def test_cleanup_does_not_hide_existing_foreign_conductive_crossing(self):
        a = geometry("A", [((-64, 0), (0, 0)), ((0, 0), (64, 0))], [(-64, 0), (64, 0)])
        b = geometry("B", [((0, -64), (0, 64))], [(0, -64), (0, 64)])
        cleaned = self.assert_clean_valid([a, b])
        self.assertEqual(cleaned, [a, b])
        self.assertIn("NET_SHORT", codes(cleaned, WARNING))

    def test_true_t_and_x_junction_endpoints_survive(self):
        for branches in ([((0, -64), (0, 0))],
                         [((0, -64), (0, 0)), ((0, 0), (0, 64))]):
            with self.subTest(branches=branches):
                edges = [((-64, 0), (0, 0)), ((0, 0), (64, 0))] + branches
                pins = [(-64, 0), (64, 0), (0, -64)] + ([(0, 64)] if len(branches) == 2 else [])
                net = geometry("N", edges, pins)
                cleaned = self.assert_clean_valid([net])[0]
                self.assertEqual(set(cleaned.segments), set(net.segments))
                self.assertEqual(sum((0, 0) in (s.start, s.end) for s in cleaned.segments), len(edges))

    def test_endpoint_on_unsplit_t_trunk_is_not_split_or_lost(self):
        net = geometry("N", [((-64, 0), (64, 0)), ((0, -64), (0, 0))],
                       [(-64, 0), (64, 0), (0, -64)])
        self.assertEqual(self.assert_clean_valid([net]), [net])

    def test_redundant_covered_edge_without_protected_boundary_is_removed(self):
        net = geometry("N", [((0, 0), (96, 0)), ((16, 0), (64, 0)), ((32, 0), (48, 0))],
                       [(0, 0), (96, 0)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertEqual(cleaned.segments, [WireSegment("N", (0, 0), (96, 0))])

    def test_covered_edges_keep_last_pin_and_flag_endpoints(self):
        for pin, flag in (([(32, 0)], []), ([], [(32, 0)])):
            with self.subTest(pin=pin, flag=flag):
                net = geometry("N", [((0, 0), (96, 0)), ((32, 0), (64, 0))],
                               [(0, 0), (96, 0)] + pin, flag)
                cleaned = self.assert_clean_valid([net])[0]
                self.assertEqual(set(cleaned.segments), set(net.segments))
                self.assertIn((32, 0), endpoints(cleaned))

    def test_covered_edge_cannot_erase_only_endpoint_at_conductive_crossing(self):
        net = geometry("N", [((-64, 0), (64, 0)), ((0, 0), (32, 0)), ((0, -64), (0, 64))],
                       [(-64, 0), (64, 0), (0, -64), (0, 64)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertIn((0, 0), endpoints(cleaned))
        self.assertEqual(set(cleaned.segments), set(net.segments))

    def test_covered_edge_with_other_terminal_endpoint_support_can_be_removed(self):
        net = geometry("N", [((0, 0), (96, 0)), ((32, 0), (64, 0)), ((32, -32), (32, 0))],
                       [(0, 0), (96, 0), (32, 0), (32, -32)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertEqual(set(cleaned.segments), {net.segments[0], net.segments[2]})

    def test_partial_overlap_is_not_union_normalized(self):
        net = geometry("N", [((0, 0), (64, 0)), ((32, 0), (96, 0))], [(0, 0), (96, 0)])
        self.assertEqual(self.assert_clean_valid([net]), [net])

    def test_backtracking_covered_run_does_not_discard_original_coverage(self):
        net = geometry("N", [((0, 0), (64, 0)), ((64, 0), (32, 0))], [(0, 0), (32, 0)])
        cleaned = self.assert_clean_valid([net])[0]
        self.assertEqual(set(cleaned.segments), {WireSegment("N", (0, 0), (64, 0)),
                                               WireSegment("N", (32, 0), (64, 0))})

    def test_no_new_paths_across_gaps_or_right_angle_bends(self):
        net = geometry("N", [((0, 0), (32, 0)), ((64, 0), (96, 0)), ((96, 0), (96, 32))],
                       [(0, 0), (32, 0), (64, 0), (96, 32)])
        self.assertEqual(clean_export_geometry([net]), [net])
        self.assertIn("NET_DISCONNECTED", codes(clean_export_geometry([net]), ERROR))

    def test_nonzero_malformed_edges_and_ownership_are_not_repaired(self):
        net = geometry("N", [((0, 0), (32, 0)), ((32, 0), (64, 32)), ((32, 0), (33, 0))], [(0, 0)])
        net.segments.append(WireSegment("foreign", (32, 0), (64, 0)))
        cleaned = clean_export_geometry([net])[0]
        self.assertEqual(set(cleaned.segments), set(net.segments))
        self.assertTrue({"NON_ORTHOGONAL_WIRE", "OFF_GRID", "WIRE_NET_MISMATCH"}
                        <= codes([cleaned], ERROR))

    def test_same_coordinates_on_different_nets_never_dedup_membership(self):
        nets = [geometry(name, [((0, 0), (64, 0))], [(0, 0), (64, 0)], [(0, 0), (0, 0)])
                for name in ("B", "A")]
        cleaned = clean_export_geometry(nets)
        self.assertEqual([net.name for net in cleaned], ["B", "A"])
        self.assertEqual([net.segments[0].net for net in cleaned], ["B", "A"])
        self.assertEqual([net.flags for net in cleaned], [[(0, 0)], [(0, 0)]])

    def test_deterministic_under_edge_permutations_and_reversals(self):
        net = geometry("N", [((0, 0), (16, 0)), ((16, 0), (32, 0)),
                             ((32, 0), (64, 0)), ((16, 0), (0, 0))], [(0, 0), (64, 0)])
        expected = self.assert_clean_valid([net])
        for order in permutations(net.segments):
            for reverse in (False, True):
                permuted = replace(net, segments=[replace(s, start=s.end, end=s.start) if reverse else s
                                                  for s in order])
                self.assertEqual(clean_export_geometry([permuted]), expected)

    def test_purity_idempotence_and_source_pin_multiplicity(self):
        net = geometry("N", [((64, 0), (32, 0)), ((0, 0), (32, 0)), ((32, 0), (0, 0))],
                       [(64, 0), (0, 0)], [(64, 0), (0, 0), (64, 0)])
        net.pins.extend([net.pins[0], PinPoint("source_alias", "p", (0, 0))])
        original = [net]
        snapshot = copy.deepcopy(original)
        cleaned = self.assert_clean_valid(original)
        self.assertEqual(original, snapshot)
        self.assertIsNot(cleaned, original)
        self.assertIsNot(cleaned[0], net)
        for attr in ("pins", "flags", "segments"):
            self.assertIsNot(getattr(cleaned[0], attr), getattr(net, attr))
        self.assertEqual(cleaned[0].pins, net.pins)
        self.assertTrue(all(a is b for a, b in zip(cleaned[0].pins, net.pins)))
        cleaned[0].pins.clear()
        cleaned[0].flags.clear()
        cleaned[0].segments.clear()
        self.assertEqual(original, snapshot)


if __name__ == "__main__":
    unittest.main()

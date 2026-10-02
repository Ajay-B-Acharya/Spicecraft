"""Direct Phase 7 routing regressions using small, exact grid geometry.

No exporter, LTspice installation or mocked search is needed. Placed-symbol
fixtures use stock resistor geometry; synthetic wires isolate topology policy.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import replace
from itertools import permutations
from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ERROR, PinPoint, WireSegment, validate_net_geometry
from app.services.connectivity import build_connectivity, validate_connectivity
from app.services.grid_system import GridSystem
from app.services.routing.geometry import CollisionDetector, hits_box, intersection, on_segment, prepare_problem
from app.services.routing.models import RoutingOptions, RoutingProblem, SafeCrossing
from app.services.routing.optimizer import normalize_segments, path_segments
from app.services.routing.router import _Router, route_nets


def placed_resistors(placements: dict[str, tuple[int, int]], edges=()):
    source = {
        "components": [{"reference": ref, "type": "resistor"} for ref in placements],
        "wires": [{"from": start, "to": end} for start, end in edges],
    }
    layouts = {ref: {"type": "resistor", "_ltspice_anchor": point,
                     "_ltspice_rotation": "R0"} for ref, point in placements.items()}
    return source, build_connectivity(source), layouts


def detour_fixture(*, needs_search: bool):
    # R3 blocks the straight connection between R1/R2's upper escapes. R4
    # additionally blocks the simple upper lane, forcing a multi-bend A* path.
    placements = {"R1": (0, 0), "R2": (384, 0), "R3": (192, -112)}
    if needs_search:
        placements["R4"] = (0, -224)
    control_pin = "R4.1" if needs_search else "R3.1"
    # Route a labelled singleton first, so failure must discard an already
    # completed net and flag, not merely an empty initial attempt.
    return placed_resistors(placements, [("control", control_pin),
                                        ("signal", "R1.1"), ("signal", "R2.1")])


class SegmentNormalizationTests(unittest.TestCase):
    def test_empty_and_zero_only_inputs_have_no_geometry(self) -> None:
        for segments in ([], [WireSegment("N1", (16, 16), (16, 16))]):
            with self.subTest(segments=segments):
                self.assertEqual(normalize_segments(segments, {(16, 16)}, set()), ([], ()))

    def test_zero_duplicate_reversed_and_collinear_segments_are_removed(self) -> None:
        segments = [WireSegment("N1", (0, 0), (0, 0)),
                    WireSegment("N1", (0, 0), (32, 0)),
                    WireSegment("N1", (32, 0), (0, 0)),
                    WireSegment("N1", (32, 0), (64, 0)),
                    WireSegment("N1", (64, 0), (64, 0))]
        before = list(segments)
        self.assertEqual(normalize_segments(segments, {(0, 0), (64, 0)}, set()),
                         ([WireSegment("N1", (0, 0), (64, 0))], ()))
        self.assertEqual(segments, before)

    def test_overlapping_collinear_segments_become_one_wire(self) -> None:
        segments = [WireSegment("N1", (0, 0), (64, 0)),
                    WireSegment("N1", (96, 0), (32, 0)),
                    WireSegment("N1", (48, 0), (64, 0))]
        self.assertEqual(normalize_segments(segments, {(0, 0), (96, 0)}, set()),
                         ([WireSegment("N1", (0, 0), (96, 0))], ()))

    def test_interior_terminals_and_escape_ports_remain_endpoints(self) -> None:
        protected = {(0, 0), (32, 0), (64, 0), (96, 0)}
        actual, junctions = normalize_segments([WireSegment("N1", (96, 0), (0, 0))],
                                               protected, set())
        self.assertEqual(actual, [WireSegment("N1", (0, 0), (32, 0)),
                                  WireSegment("N1", (32, 0), (64, 0)),
                                  WireSegment("N1", (64, 0), (96, 0))])
        self.assertTrue(protected.issubset({p for s in actual for p in (s.start, s.end)}))
        self.assertEqual(junctions, ())

    def test_t_attachment_splits_trunk_and_preserves_real_junction(self) -> None:
        segments = [WireSegment("N1", (0, 0), (96, 0)),
                    WireSegment("N1", (48, -32), (48, 0))]
        actual, junctions = normalize_segments(segments, {(0, 0), (96, 0), (48, -32)}, set())
        self.assertEqual(actual, [WireSegment("N1", (0, 0), (48, 0)),
                                  WireSegment("N1", (48, -32), (48, 0)),
                                  WireSegment("N1", (48, 0), (96, 0))])
        self.assertEqual(junctions, ((48, 0),))
        self.assertEqual(Counter(p for s in actual for p in (s.start, s.end))[(48, 0)], 3)

    def test_same_net_x_is_split_into_a_four_way_junction(self) -> None:
        segments = [WireSegment("N1", (-64, 0), (64, 0)),
                    WireSegment("N1", (0, -64), (0, 64))]
        actual, junctions = normalize_segments(segments, set(), set())
        self.assertEqual(len(actual), 4)
        self.assertEqual(junctions, ((0, 0),))
        self.assertEqual(Counter(p for s in actual for p in (s.start, s.end))[(0, 0)], 4)

    def test_foreign_x_remains_strictly_inside_both_unsplit_wires(self) -> None:
        crossing = (0, 0)
        horizontal = WireSegment("A", (-64, 0), (64, 0))
        vertical = WireSegment("B", (0, -64), (0, 64))
        wires = []
        for segment in (horizontal, vertical):
            with self.subTest(net=segment.net):
                # Crossing reservations take precedence even if a generic
                # protected-vertex collection happens to include this point.
                actual, junctions = normalize_segments([segment], {crossing}, {crossing})
                self.assertEqual(actual, [segment])
                self.assertEqual(junctions, ())
                self.assertTrue(on_segment(crossing, actual[0].start, actual[0].end, strict=True))
                wires.extend(actual)
        self.assertEqual(intersection(*wires), ("cross", crossing))

    def test_normalization_is_deterministic_and_idempotent(self) -> None:
        segments = [WireSegment("N1", (64, 0), (0, 0)),
                    WireSegment("N1", (32, -32), (32, 0)),
                    WireSegment("N1", (32, 0), (64, 0)),
                    WireSegment("N1", (32, -32), (32, -32))]
        protected = {(0, 0), (64, 0), (32, -32)}
        expected = normalize_segments(segments, protected, set())
        for order in permutations(segments):
            with self.subTest(order=order):
                self.assertEqual(normalize_segments(list(order), protected, set()), expected)
        self.assertEqual(normalize_segments(expected[0], protected, set()), expected)

    def test_path_compaction_removes_repeats_and_collinear_nodes_not_bends(self) -> None:
        self.assertEqual(path_segments("N1", [(0, 0), (0, 0), (16, 0), (32, 0),
                                               (32, 16), (32, 32), (32, 32)]),
                         [WireSegment("N1", (0, 0), (32, 0)),
                          WireSegment("N1", (32, 0), (32, 32))])
        for points in ([], [(0, 0)], [(0, 0), (0, 0)]):
            with self.subTest(points=points):
                self.assertEqual(path_segments("N1", points), [])


class CollisionDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.problem = RoutingProblem({}, [], RoutingOptions())
        self.detector = CollisionDetector(self.problem)
        self.horizontal = WireSegment("A", (-64, 0), (64, 0))
        self.vertical = WireSegment("B", (0, -64), (0, 64))
        self.crossing = SafeCrossing(("A", "B"), (0, 0))

    def test_only_fallback_accepts_a_new_unsplit_x(self) -> None:
        self.assertEqual(self.detector.segment_allowed(self.vertical, [self.horizontal], (),
                                                        allow_crossings=False), (False, []))
        self.assertEqual(self.detector.segment_allowed(self.vertical, [self.horizontal], (),
                                                        allow_crossings=True), (True, [self.crossing]))
        self.assertEqual(self.detector.segment_allowed(self.horizontal, [self.vertical], (),
                                                        allow_crossings=True), (True, [self.crossing]))

    def test_foreign_endpoint_touches_and_overlaps_are_never_safe_crossings(self) -> None:
        candidates = [WireSegment("B", (0, -32), (0, 0)),
                      WireSegment("B", (64, -32), (64, 32)),
                      WireSegment("B", (-32, 0), (32, 0)),
                      WireSegment("B", (64, 0), (96, 0))]
        for segment in candidates:
            with self.subTest(segment=segment):
                self.assertEqual(self.detector.segment_allowed(segment, [self.horizontal], (),
                                                                allow_crossings=True), (False, []))

    def test_crossing_reservation_blocks_points_for_every_net(self) -> None:
        for net in ("A", "B", "C"):
            with self.subTest(net=net):
                self.assertFalse(self.detector.point_allowed((0, 0), net, [], [self.crossing]))
        self.assertTrue(self.detector.point_allowed((16, 0), "A", [self.horizontal], [self.crossing]))

    def test_audit_can_revisit_existing_unsplit_crossing_pair(self) -> None:
        occupied = [self.horizontal, self.vertical]
        for segment in occupied:
            for candidate in (segment, WireSegment(segment.net, segment.end, segment.start)):
                with self.subTest(segment=candidate):
                    self.assertEqual(self.detector.segment_allowed(candidate, occupied, [self.crossing],
                                                                    allow_crossings=True),
                                     (True, [self.crossing]))

    def test_later_attachment_cannot_end_at_or_change_axis_through_crossing(self) -> None:
        candidates = [WireSegment("A", (0, 96), (0, 0)),
                      WireSegment("A", (0, 0), (-96, 0)),
                      WireSegment("A", (0, -96), (0, 96)),
                      WireSegment("C", (-96, 0), (96, 0))]
        for segment in candidates:
            with self.subTest(segment=segment):
                # Omit the foreign wire deliberately: the recorded crossing
                # itself must protect later attachments to the same-net tree.
                self.assertEqual(self.detector.segment_allowed(segment, [self.horizontal], [self.crossing],
                                                                allow_crossings=True), (False, []))

    def test_real_tree_attachment_avoids_projected_crossing_goal(self) -> None:
        occupied = [self.horizontal, self.vertical]
        crossings = [self.crossing]
        before = copy.deepcopy((occupied, crossings))
        router = _Router(self.problem, Counter())
        self.assertEqual(router._goals((0, 96), [self.horizontal], occupied, crossings, "A"),
                         [(-64, 0), (64, 0)])
        answer = router.connect("A", (0, 96), [self.horizontal], occupied, crossings, True)
        self.assertIsNotNone(answer)
        branches, actual_crossings = answer
        self.assertTrue(branches)
        self.assertEqual(branches[0].start, (0, 96))
        self.assertIn(branches[-1].end, ((-64, 0), (64, 0)))
        self.assertEqual(actual_crossings, crossings)
        for segment in branches:
            self.assertFalse(on_segment((0, 0), segment.start, segment.end))
            self.assertTrue(self.detector.segment_allowed(segment, occupied, crossings,
                                                           allow_crossings=True)[0])
        normalized, junctions = normalize_segments([self.horizontal, *branches],
                                                   {(-64, 0), (64, 0), (0, 96)}, {(0, 0)})
        self.assertNotIn((0, 0), junctions)
        self.assertEqual([s for s in normalized if on_segment((0, 0), s.start, s.end)],
                         [self.horizontal])
        self.assertEqual((occupied, crossings), before)

    def test_unused_pin_and_escape_corridor_are_reserved(self) -> None:
        _, model, layouts = placed_resistors({"R1": (0, 0)}, [("signal", "R1.1")])
        problem, diagnostics = prepare_problem(model, layouts, RoutingOptions())
        self.assertEqual(diagnostics, [])
        pin = problem.pins["R1.2"]
        self.assertIsNone(pin.net)
        self.assertEqual((pin.point, pin.escape), ((16, 96), (16, 128)))
        detector = CollisionDetector(problem)
        for point in (pin.point, (16, 112), pin.escape):
            with self.subTest(point=point):
                self.assertFalse(detector.point_allowed(point, "signal", [], ()))
        # These candidates only meet the outward reservation beyond the closed
        # expanded body, so rejection cannot be explained by a body collision.
        candidates = [WireSegment("signal", (-16, 128), (48, 128)),
                      WireSegment("signal", pin.escape, (16, 160))]
        for segment in candidates:
            with self.subTest(segment=segment):
                self.assertFalse(hits_box(segment, problem.obstacles[0].expanded))
                self.assertEqual(detector.segment_allowed(segment, [], (), allow_crossings=True), (False, []))
        safe = WireSegment("signal", (0, 128), (0, 160))
        self.assertTrue(detector.point_allowed(safe.start, "signal", [], ()))
        self.assertEqual(detector.segment_allowed(safe, [], (), allow_crossings=True), (True, []))

    def test_only_designated_exact_outward_lead_can_enter_its_owner(self) -> None:
        _, model, layouts = placed_resistors({"R1": (0, 0)}, [("signal", "R1.1")])
        problem, diagnostics = prepare_problem(model, layouts, RoutingOptions())
        self.assertEqual(diagnostics, [])
        detector = CollisionDetector(problem)
        pin = problem.pins["R1.1"]
        lead = WireSegment("signal", pin.point, pin.escape)
        self.assertEqual(detector.segment_allowed(lead, [], (), allow_crossings=False), (False, []))
        self.assertEqual(detector.segment_allowed(lead, [], (), allow_crossings=False,
                                                  escape_pin=pin.key), (True, []))
        for segment, key in [(lead, "R1.2"),
                             (WireSegment("signal", pin.point, (16, -32)), pin.key),
                             (WireSegment("signal", pin.point, (16, 32)), pin.key)]:
            with self.subTest(segment=segment, key=key):
                self.assertEqual(detector.segment_allowed(segment, [], (), allow_crossings=False,
                                                          escape_pin=key), (False, []))

    def test_zero_diagonal_and_off_grid_candidates_are_rejected(self) -> None:
        for segment in [WireSegment("A", (0, 0), (0, 0)),
                        WireSegment("A", (0, 0), (16, 16)),
                        WireSegment("A", (1, 0), (16, 0))]:
            with self.subTest(segment=segment):
                self.assertEqual(self.detector.segment_allowed(segment, [], (), allow_crossings=True),
                                 (False, []))


class DirectRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.options = RoutingOptions(envelope_margins=(64,), max_order_attempts=1, allow_crossings=False)

    def assert_empty_failure(self, result, code: str) -> None:
        self.assertFalse(result.ok)
        self.assertEqual({d.code for d in result.diagnostics if d.severity == ERROR}, {code},
                         result.diagnostics)
        self.assertEqual(result.net_geometries, [])
        self.assertEqual(result.junctions, {})
        self.assertEqual(result.flags, [])
        self.assertEqual(result.crossings, ())
        for key in ("segments", "length", "crossings"):
            self.assertEqual(result.metrics[key], 0)

    def assert_safe_detour(self, model, layouts, result) -> None:
        self.assertTrue(result.ok, result.diagnostics)
        self.assertEqual(result.diagnostics, [])
        self.assertEqual(validate_connectivity(model, result.net_geometries), [])
        self.assertEqual(validate_net_geometry(result.net_geometries), [])
        self.assertEqual([n.name for n in result.net_geometries], ["control", "signal"])
        self.assertEqual({f.net for f in result.flags}, {"control", "signal"})
        self.assertEqual(result.crossings, ())
        problem, diagnostics = prepare_problem(model, layouts, self.options)
        self.assertEqual(diagnostics, [])
        detector = CollisionDetector(problem)
        occupied = [s for net in result.net_geometries for s in net.segments]
        blocker = next(o for o in problem.obstacles if o.component == "R3")
        straight = WireSegment("signal", problem.pins["R1.1"].escape, problem.pins["R2.1"].escape)
        self.assertTrue(hits_box(straight, blocker.expanded))
        self.assertFalse(detector.segment_allowed(straight, [], (), allow_crossings=False)[0])
        self.assertGreater(result.metrics["length"], 384 + 3 * 32)
        for net in result.net_geometries:
            for pin in net.pins:
                self.assertIn(pin.point, {p for s in net.segments for p in (s.start, s.end)})
            for segment in net.segments:
                self.assertIn(segment.orientation, ("horizontal", "vertical"))
                self.assertTrue(all(GridSystem.is_point_on_grid(p) for p in (segment.start, segment.end)))
                if net.name == "signal":
                    self.assertFalse(hits_box(segment, blocker.expanded))
                designated = next((pin.key for pin in problem.pins.values()
                                   if pin.net == net.name
                                   and on_segment(segment.start, pin.point, pin.escape)
                                   and on_segment(segment.end, pin.point, pin.escape)), None)
                self.assertTrue(detector.segment_allowed(segment, occupied, result.crossings,
                                                          allow_crossings=False, escape_pin=designated)[0])
                for pin in problem.pins.values():
                    if pin.net is None:
                        self.assertEqual(intersection(segment, WireSegment("@reserved", pin.point, pin.escape))[0],
                                         "none", (segment, pin))
            for flag in net.flags:
                self.assertTrue(detector.point_allowed(flag, net.name, occupied, result.crossings))

    def test_low_bend_candidate_detours_around_a_real_symbol(self) -> None:
        _, model, layouts = detour_fixture(needs_search=False)
        result = route_nets(model, layouts, options=self.options)
        self.assert_safe_detour(model, layouts, result)
        self.assertGreater(result.metrics["candidate_paths"], 0)
        self.assertEqual(result.metrics["astar_searches"], 0)
        self.assertEqual(result.metrics["budget_exhaustions"], 0)

    def test_multi_bend_astar_detour_avoids_bodies_and_unused_pins(self) -> None:
        _, model, layouts = detour_fixture(needs_search=True)
        result = route_nets(model, layouts, options=self.options)
        self.assert_safe_detour(model, layouts, result)
        self.assertEqual(result.metrics["astar_searches"], 1)
        self.assertGreater(result.metrics["astar_states"], 0)
        self.assertLess(result.metrics["astar_states"], 1000)
        self.assertLess(result.metrics["peak_grid_vertices"], 1000)
        self.assertEqual(result.metrics["budget_exhaustions"], 0)

    def test_grid_budget_exhaustion_discards_completed_net_and_flag(self) -> None:
        self.check_search_exhaustion("max_grid_vertices")

    def test_state_budget_exhaustion_discards_completed_net_and_flag(self) -> None:
        self.check_search_exhaustion("max_search_states")

    def check_search_exhaustion(self, budget: str) -> None:
        source, model, layouts = detour_fixture(needs_search=True)
        before = copy.deepcopy((source, model, layouts))
        options = replace(self.options, envelope_margins=(64, 128), **{budget: 1})
        result = route_nets(model, layouts, options=options)
        self.assert_empty_failure(result, "ROUTING_SEARCH_LIMIT")
        self.assertEqual(result.metrics["order_attempts"], 1)
        self.assertEqual(result.metrics["planar_attempts"], 1)
        self.assertEqual(result.metrics["fallback_attempts"], 0)
        self.assertEqual(result.metrics["failed_connections"], 1)
        self.assertEqual(result.metrics["astar_searches"], len(options.envelope_margins))
        self.assertEqual(result.metrics["budget_exhaustions"], len(options.envelope_margins))
        self.assertGreater(result.metrics["candidate_paths"], 0)
        if budget == "max_grid_vertices":
            self.assertGreater(result.metrics["peak_grid_vertices"], options.max_grid_vertices)
            self.assertEqual(result.metrics["astar_states"], 0)
        else:
            # The search counts the next expansion before checking the cap.
            self.assertEqual(result.metrics["astar_states"],
                             (options.max_search_states + 1) * len(options.envelope_margins))
        self.assertEqual((source, model, layouts), before)
        # The same fixed placement is routable with ordinary budgets; this is
        # genuine bounded-search exhaustion, not blocked preparation geometry.
        successful = route_nets(model, layouts, options=self.options)
        self.assert_safe_detour(model, layouts, successful)

    def test_tiny_search_budgets_do_not_disable_safe_candidate_routes(self) -> None:
        _, model, layouts = detour_fixture(needs_search=False)
        result = route_nets(model, layouts, options=replace(self.options, max_grid_vertices=1, max_search_states=1))
        self.assert_safe_detour(model, layouts, result)
        self.assertEqual(result.metrics["astar_searches"], 0)
        self.assertEqual(result.metrics["budget_exhaustions"], 0)

    def test_invalid_options_return_empty_diagnostic_result_without_search(self) -> None:
        _, model, layouts = detour_fixture(needs_search=True)
        invalid = [("clearance", -16), ("clearance", 17),
                   ("label_spacing", -16), ("label_spacing", 17),
                   ("envelope_margins", ()), ("envelope_margins", (0,)),
                   ("envelope_margins", (-16,)), ("envelope_margins", (64, 17)),
                   ("max_grid_vertices", 0), ("max_grid_vertices", -1),
                   ("max_search_states", 0), ("max_search_states", -1),
                   ("max_order_attempts", 0), ("max_order_attempts", -1),
                   ("bend_penalty", -1)]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                result = route_nets(model, layouts, options=replace(self.options, **{field: value}))
                self.assert_empty_failure(result, "INVALID_ROUTING_OPTIONS")
                self.assertTrue(all(value == 0 for value in result.metrics.values()), result.metrics)

    def test_repeated_routes_are_deterministic_and_leave_inputs_unchanged(self) -> None:
        source, model, layouts = detour_fixture(needs_search=True)
        before = copy.deepcopy((source, model, layouts))
        expected = route_nets(model, layouts, options=self.options)
        self.assert_safe_detour(model, layouts, expected)
        for _ in range(3):
            self.assertEqual(route_nets(model, layouts, options=self.options), expected)
        self.assertEqual(route_nets(model, dict(reversed(list(layouts.items()))), options=self.options), expected)
        reordered_source = copy.deepcopy(source)
        reordered_source["components"].reverse()
        self.assertEqual(route_nets(build_connectivity(reordered_source), layouts, options=self.options), expected)
        self.assertEqual((source, model, layouts), before)


if __name__ == "__main__":
    unittest.main()

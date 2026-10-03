"""Presentation-only regressions; no LTspice installation or imaging dependency."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import NetGeometry, PinPoint, WireSegment  # noqa: E402
from app.services.export_presentation import (  # noqa: E402
    Presentation,
    _text_extent,
    build_presentation,
)
from app.services.pin_maps import COMPONENT_LIBRARY  # noqa: E402

ORIENTATIONS = ("R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270")


def layout(reference="R1", kind="resistor", anchor=(0, 0), orientation="R0", value="1k"):
    result = {"_inst_name": reference, "type": kind, "value": value,
              "_ltspice_anchor": anchor, "_ltspice_rotation": orientation,
              "_ltspice_mirror": False}
    if kind in COMPONENT_LIBRARY:
        result["_ltspice_symbol"] = COMPONENT_LIBRARY[kind].symbol
    return result


def orient(x, y, token, mirror=False):
    """Independent quarter turns: no production transform calls in assertions."""
    for _ in range(int(token[1:]) // 90):
        x, y = -y, x
    return (-x if mirror or token.startswith("M") else x), y


def window_boxes(presentation, layouts):
    result = {}
    for reference, records in presentation.windows.items():
        component = layouts[reference]
        definition = COMPONENT_LIBRARY[component["type"]]
        origin = tuple(a + b for a, b in zip(component["_ltspice_anchor"], definition.anchor))
        raw_value = component.get("value")
        value = str(raw_value) if raw_value is not None else definition.default_value
        labels = {0: reference, 3: value}
        boxes = []
        for record in records:
            _, index, x, y, justification, size = record.split()
            dx, dy = orient(int(x), int(y), component["_ltspice_rotation"],
                            component["_ltspice_mirror"])
            cx, cy = origin[0] + dx, origin[1] + dy
            width, height = _text_extent(labels[int(index)], int(size))
            boxes.append((int(index), (cx - width // 2, cy - height // 2,
                                       cx + width // 2, cy + height // 2),
                          (cx, cy), justification, int(size)))
        result[reference] = boxes
    return result


def contains(outer, inner):
    return (outer[0] <= inner[0] <= inner[2] <= outer[2]
            and outer[1] <= inner[1] <= inner[3] <= outer[3])


def overlaps(a, b):
    return (max(a[0], b[0]) < min(a[2], b[2])
            and max(a[1], b[1]) < min(a[3], b[3]))


def metadata_boxes(presentation):
    boxes = []
    content = []
    for record in presentation.text:
        command, x, y, alignment, size, comment = record.split(" ", 5)
        assert (command, alignment, size, comment[0]) == ("TEXT", "Left", "1", ";")
        width, height = _text_extent(comment[1:], 1)
        x, y = int(x), int(y)
        boxes.append((x, y - height // 2, x + width, y + height // 2))
        content.append(comment[1:])
    return boxes, content


class PresentationContractTests(unittest.TestCase):
    def test_exact_interface_and_empty_input(self):
        result = build_presentation({}, [], "", "")
        self.assertIsInstance(result, Presentation)
        self.assertTrue(is_dataclass(result))
        self.assertEqual([f.name for f in fields(result)], ["windows", "text", "sheet", "bounds"])
        self.assertEqual(result, Presentation({}, [], "SHEET 1 64 64", (0, 0, 0, 0)))

    def test_no_mutation_alias_deduplication_and_determinism(self):
        r1 = layout()
        r2 = layout("R2", anchor=(256, 128), orientation="M90", value=0)
        r1["pins"] = {"1": ["source"]}
        layouts = {"source-id": r1, "R2": r2, "R1": r1}
        nets = [NetGeometry("VIN", [PinPoint("R1", "1", (16, 16))], [(16, -32)],
                            [WireSegment("VIN", (16, -32), (16, 16))]),
                NetGeometry("0", flags=[(272, 256)])]
        before = deepcopy((layouts, nets))
        first = build_presentation(layouts, nets, "Circuit", "Description")
        for _ in range(3):
            self.assertEqual(first, build_presentation(layouts, nets, "Circuit", "Description"))
        reordered = dict(reversed(list(layouts.items())))
        self.assertEqual(first, build_presentation(reordered, list(reversed(nets)), "Circuit", "Description"))
        self.assertEqual((layouts, nets), before)
        self.assertIs(layouts["source-id"], layouts["R1"])
        self.assertEqual(list(first.windows), ["R1", "R2"])
        self.assertTrue(all(line.startswith("WINDOW ") for lines in first.windows.values() for line in lines))

    def test_unknown_unwired_and_mismatched_symbols_keep_native_defaults(self):
        unknown = layout("X1", "unverified", (-800, -400), "not-an-orientation", "custom")
        unknown["_ltspice_symbol"] = "res"  # Exporter fallback is NOT verified geometry.
        mismatch = layout("R1", anchor=(320, 640))
        mismatch["_ltspice_symbol"] = "custom/res"
        result = build_presentation({"X1": unknown, "R1": mismatch}, [], "", "")
        self.assertEqual(result.windows, {})
        self.assertEqual(result.bounds, (-800, -400, 320, 640))

    def test_values_are_measured_exactly_but_never_serialized_or_rewritten(self):
        for value in ("100µF", " 10uF ", 0, "0", "PULSE(0 3.3 0 1n 1n 1m 2m)", "MWµΩ"):
            with self.subTest(value=value):
                component = layout("Cµ1", "capacitor", value=value)
                layouts = {"Cµ1": component}
                original = deepcopy(layouts)
                with patch("app.services.export_presentation._text_extent", wraps=_text_extent) as metric:
                    result = build_presentation(layouts, [], "", "")
                    measured = [call.args[0] for call in metric.call_args_list]
                self.assertIn(str(value), measured)
                self.assertIn("Cµ1", measured)
                self.assertEqual([line.split()[1] for line in result.windows["Cµ1"]], ["0", "3"])
                self.assertEqual(layouts, original)
                self.assertTrue(all(len(line.split()) == 6 for line in result.windows["Cµ1"]))

    def test_empty_value_not_replaced_and_absent_value_uses_native_default(self):
        for value in (None, ""):
            with self.subTest(value=value):
                result = build_presentation({"R1": layout(value=value)}, [], "", "")
                self.assertEqual(len(result.windows["R1"]), 1)
        diode = layout("D1", "diode", value=None)
        result = build_presentation({"D1": diode}, [], "", "")
        self.assertEqual(len(result.windows["D1"]), 2)
        diode["value"] = ""
        self.assertEqual(len(build_presentation({"D1": diode}, [], "", "").windows["D1"]), 1)


class PresentationGeometryTests(unittest.TestCase):
    def test_every_canonical_kind_rotation_and_mirror_uses_absolute_bounds(self):
        for kind, definition in COMPONENT_LIBRARY.items():
            for orientation in ORIENTATIONS:
                for mirror in (False, True):
                    with self.subTest(kind=kind, orientation=orientation, mirror=mirror):
                        component = layout("X1", kind, (-320, 192), orientation, "10µ")
                        component["_ltspice_mirror"] = mirror
                        layouts = {"X1": component}
                        result = build_presentation(layouts, [], "", "")
                        corners = [orient(x, y, orientation, mirror)
                                   for x in (definition.bounds[0], definition.bounds[2])
                                   for y in (definition.bounds[1], definition.bounds[3])]
                        body = (-320 + min(x for x, _ in corners), 192 + min(y for _, y in corners),
                                -320 + max(x for x, _ in corners), 192 + max(y for _, y in corners))
                        self.assertTrue(contains(result.bounds, body))
                        decoded = window_boxes(result, layouts)["X1"]
                        self.assertLess(decoded[0][2][1], decoded[1][2][1])
                        self.assertFalse(overlaps(decoded[0][1], decoded[1][1]))
                        for _, box, _, justification, size in decoded:
                            self.assertFalse(overlaps(body, box))
                            self.assertTrue(contains(result.bounds, box))
                            self.assertEqual(size, 2)
                            self.assertEqual(justification, "VCenter" if int(orientation[1:]) % 180 else "Center")

    def test_symbol_bounds_and_origin_come_from_canonical_library(self):
        definition = replace(COMPONENT_LIBRARY["resistor"], anchor=(32, -16), bounds=(-128, -64, 160, 96))
        with patch.dict(COMPONENT_LIBRARY, {"resistor": definition}):
            component = layout(anchor=(-64, -32), orientation="M270")
            layouts = {"R1": component}
            result = build_presentation(layouts, [], "", "")
            corners = [orient(x, y, "M270") for x in (-128, 160) for y in (-64, 96)]
            body = (-32 + min(x for x, _ in corners), -48 + min(y for _, y in corners),
                    -32 + max(x for x, _ in corners), -48 + max(y for _, y in corners))
            self.assertTrue(contains(result.bounds, body))
            for _, box, *_ in window_boxes(result, layouts)["R1"]:
                self.assertTrue(contains(result.bounds, box))
                self.assertFalse(overlaps(body, box))

    def test_invalid_orientation_does_not_silently_fabricate_geometry(self):
        with self.assertRaises(ValueError):
            build_presentation({"R1": layout(orientation="R45")}, [], "", "")

    def test_collision_scoring_avoids_wire_and_is_deterministic(self):
        layouts = {"R1": layout()}
        baseline = build_presentation(layouts, [], "", "")
        decoded = window_boxes(baseline, layouts)["R1"]
        x = decoded[0][2][0]
        net = NetGeometry("wire", segments=[WireSegment("wire", (x, -128), (x, 256))])
        result = build_presentation(layouts, [net], "", "")
        self.assertNotEqual(result.windows, baseline.windows)
        self.assertEqual(result, build_presentation(layouts, [net], "", ""))
        for _, box, *_ in window_boxes(result, layouts)["R1"]:
            self.assertFalse(overlaps(box, (x - 4, -132, x + 4, 260)))

    def test_collision_scoring_avoids_flag_text_and_ground_triangle(self):
        layouts = {"R1": layout()}
        baseline = build_presentation(layouts, [], "", "")
        x, y = window_boxes(baseline, layouts)["R1"][0][2]
        for name, point, forbidden in (
            ("LONG_SUPPLY_FLAG", (x, y + 16), (x - 4, y - 16, x + 240, y + 24)),
            ("0", (x, y - 12), (x - 16, y - 12, x + 16, y + 12)),
        ):
            with self.subTest(flag=name):
                result = build_presentation(layouts, [NetGeometry(name, flags=[point])], "", "")
                self.assertNotEqual(result.windows, baseline.windows)
                for _, box, *_ in window_boxes(result, layouts)["R1"]:
                    self.assertFalse(overlaps(box, forbidden))

    def test_previously_placed_windows_are_obstacles(self):
        layouts = {"R1": layout(), "R2": layout("R2", anchor=(64, 0))}
        result = build_presentation(layouts, [], "", "")
        windows = window_boxes(result, layouts)
        for _, a, *_ in windows["R1"]:
            for _, b, *_ in windows["R2"]:
                self.assertFalse(overlaps(a, b))
        self.assertEqual(result, build_presentation(dict(reversed(list(layouts.items()))), [], "", ""))

    def test_compact_font_fits_a_tight_wire_corridor(self):
        layouts = {"R1": layout()}
        # The short labels fit between these two buses at size 1, but not 2.
        net = NetGeometry("bus", segments=[WireSegment("bus", (-512, y), (512, y)) for y in (28, 84)])
        result = build_presentation(layouts, [net], "", "")
        decoded = window_boxes(result, layouts)["R1"]
        self.assertTrue(all(size == 1 for _, _, _, _, size in decoded))
        for _, box, *_ in decoded:
            for y in (28, 84):
                self.assertFalse(overlaps(box, (-516, y - 4, 516, y + 4)))

    def test_bbox_contains_wire_extremes_flag_text_ground_and_pin(self):
        net = NetGeometry("WIDE_NET_LABEL", pins=[PinPoint("X1", "1", (-2304, 352))],
                          flags=[(1600, -1200)],
                          segments=[WireSegment("WIDE_NET_LABEL", (-2048, 2048), (2048, 2048))])
        ground = NetGeometry("0", flags=[(-2200, 2200)])
        result = build_presentation({}, [net, ground], "Header", "Detail")
        self.assertLessEqual(result.bounds[0], -2304)
        self.assertLessEqual(result.bounds[1], -1232)
        self.assertGreaterEqual(result.bounds[2], 2048)
        self.assertGreaterEqual(result.bounds[3], 2224)
        text_boxes, _ = metadata_boxes(result)
        self.assertTrue(all(contains(result.bounds, box) for box in text_boxes))
        width, height = map(int, result.sheet.split()[2:])
        self.assertLess(width, 12000)
        self.assertGreaterEqual(width, result.bounds[2] - result.bounds[0] + 64)
        self.assertGreaterEqual(height, result.bounds[3] - result.bounds[1] + 64)
        self.assertEqual((width % 16, height % 16), (0, 0))

    def test_sheet_uses_span_not_distance_from_origin(self):
        original = {"R1": layout(anchor=(64, 128))}
        shifted = {"R1": layout(anchor=(-9936, 10128))}
        a = build_presentation(original, [], "Circuit", "Description")
        b = build_presentation(shifted, [], "Circuit", "Description")
        self.assertEqual(a.sheet, b.sheet)
        self.assertEqual(a.windows, b.windows)
        self.assertEqual(b.bounds, (a.bounds[0] - 10000, a.bounds[1] + 10000,
                                   a.bounds[2] - 10000, a.bounds[3] + 10000))


class PresentationMetadataTests(unittest.TestCase):
    def test_small_wrapped_metadata_preserves_all_words_and_never_overlaps(self):
        layouts = {"R1": layout(), "C1": layout("C1", "capacitor", (416, 160), value="µF")}
        title = "A useful circuit title that is intentionally longer than the circuit width"
        description = ("Detailed frequency response and sensor operating notes with supply limits. " * 12).strip()
        circuit = build_presentation(layouts, [], "", "")
        result = build_presentation(layouts, [], title, description)
        boxes, content = metadata_boxes(result)
        self.assertEqual(" ".join(content).split(), (title + " " + description).split())
        self.assertTrue(all(len(line) <= 80 for line in content))
        self.assertTrue(all(box[2] - box[0] <= circuit.bounds[2] - circuit.bounds[0] for box in boxes))
        self.assertLessEqual(max(b[3] for b in boxes), circuit.bounds[1] - 32)
        for previous, current in zip(boxes, boxes[1:]):
            self.assertEqual(current[1] - previous[1], 24)
            self.assertFalse(overlaps(previous, current))
        self.assertTrue(all(contains(result.bounds, box) for box in boxes))
        self.assertEqual(result.windows, circuit.windows)

    def test_metadata_record_injection_is_rendered_as_comment_words(self):
        title = "Real title\r\nWIRE 0 0 32 0\u2028FLAG 0 0 dangerous"
        description = "First\nSYMBOL res 0 0 R0\rTEXT 0 0 Left 2 !evil\tLast\vword"
        result = build_presentation({}, [], title, description)
        _, content = metadata_boxes(result)
        self.assertEqual(" ".join(content).split(), (title + " " + description).split())
        for record in result.text:
            self.assertEqual(len(record.splitlines()), 1)
            self.assertTrue(record.startswith("TEXT "))
            self.assertIn(" Left 1 ;", record)

    def test_overlong_word_is_not_truncated_or_broken(self):
        token = "https://example.invalid/" + "identifier" * 20
        result = build_presentation({}, [], "Title", f"Read {token} for full metadata")
        boxes, content = metadata_boxes(result)
        self.assertIn(token, content)
        self.assertEqual(" ".join(content).split(), f"Title Read {token} for full metadata".split())
        self.assertGreater(result.bounds[2] - result.bounds[0], 800)
        self.assertTrue(all(contains(result.bounds, b) for b in boxes))

    def test_metadata_char_limit_applies_even_for_wide_circuits(self):
        description = " ".join(f"word{i}" for i in range(150))
        net = NetGeometry("wide", segments=[WireSegment("wide", (-16000, 0), (16000, 0))])
        result = build_presentation({}, [net], "", description)
        _, content = metadata_boxes(result)
        self.assertTrue(all(len(line) <= 80 for line in content))
        self.assertEqual(" ".join(content), description)

    def test_unicode_widths_and_combining_marks_use_documented_metrics(self):
        self.assertEqual(_text_extent("0", 1), (12, 18))
        self.assertEqual(_text_extent("0", 2), (16, 28))
        self.assertEqual(_text_extent("µ", 2), _text_extent("u", 2))
        self.assertEqual(_text_extent("e\u0301", 1), _text_extent("e", 1))
        self.assertGreater(_text_extent("界", 1)[0], _text_extent("a", 1)[0])
        self.assertGreater(_text_extent("W", 1)[0], _text_extent("a", 1)[0])


if __name__ == "__main__":
    unittest.main()

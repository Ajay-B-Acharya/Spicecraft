"""Deterministic, presentation-only LTspice annotations for an existing layout.

``build_presentation`` never edits layouts or routed geometry. Insert each
``windows[inst]`` immediately after its SYMBOL record, before the unchanged
SYMATTR records; use ``sheet`` instead of the fixed sheet and append ``text``.
WINDOW 0/3 refer to the original InstName/Value: their strings are not rewritten.

Font metrics are deliberately conservative, dependency-free estimates in ASC
units, not platform/font measurements: size 1 has 18-unit height and 9-unit
ordinary glyph advance; size 2 has 28-unit height and 14-unit advance. Wide
Latin glyphs use 1.5 advances, East Asian wide/fullwidth glyphs two, combining
marks zero. Widths round upward to four units. Native font substitution can
still differ. Named FLAGs reserve their size-2 text above/right of the anchor;
ground reserves a 32-by-24 triangle envelope. Collision clearance is four units.

WINDOW positions are symbol-local, but placement and scoring are absolute.
Center/VCenter justification avoids the orientation-dependent edge meanings of
Left/Right and VLeft/VRight. Odd symbol rotations need VCenter to make their
text horizontal; native LTspice keeps the resulting text upright, including
180-degree rotations. Mirroring and inverse positions use PinResolver alone.
The shared resolver's M90/M270 native-geometry caveat also applies here.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any

from app.services.asc_validation import NetGeometry
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, resolve_component_kind

Bounds = tuple[int, int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True)
class Presentation:
    """Native records and unpadded absolute content bounds (left, top, right, bottom).

    SHEET dimensions are the bounding *span* plus 32 units on each side,
    rounded up to 16 units. They do not translate coordinates or introduce an
    artificial origin into the bounds. Unknown symbols keep their default
    windows; only their anchor is included because their drawing is unverified.
    """

    windows: dict[str, list[str]]
    text: list[str]
    sheet: str
    bounds: Bounds


@dataclass(frozen=True)
class _Symbol:
    reference: str
    origin: Point
    degrees: int
    mirrored: bool
    bounds: Bounds
    labels: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class _Window:
    index: int
    center: Point
    size: int
    bounds: Bounds


def _ceil(value: int, grid: int = 4) -> int:
    return -(-value // grid) * grid


def _text_extent(text: str, size: int) -> Point:
    """Conservative single-line width/height; inspect but never normalize values."""
    advance, height = (9, 18) if size == 1 else (14, 28)
    # Two half-advances per ordinary glyph avoid floating-point differences.
    units = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in {"W", "F"}:
            units += 4
        elif char in "MWmw@%&":
            units += 3
        elif char == "\t":
            units += 8
        else:
            units += 2
    return _ceil((units * advance + 1) // 2), height


def _union(boxes: list[Bounds]) -> Bounds:
    if not boxes:
        return (0, 0, 0, 0)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _expand(box: Bounds, amount: int) -> Bounds:
    return (box[0] - amount, box[1] - amount,
            box[2] + amount, box[3] + amount)


def _overlap(a: Bounds, b: Bounds) -> int:
    return (max(0, min(a[2], b[2]) - max(a[0], b[0]))
            * max(0, min(a[3], b[3]) - max(a[1], b[1])))


def _inverse_offset(point: Point, degrees: int, mirrored: bool) -> Point:
    """Invert mirror-after-rotation without maintaining another transform table."""
    unmirrored = PinResolver.transform_offset(*point, 0, mirrored)
    return PinResolver.transform_offset(*unmirrored, (-degrees) % 360, False)


def _symbols(layouts: dict) -> tuple[list[_Symbol], list[Bounds]]:
    # place_components also indexes layouts by source id. Emit each InstName
    # once, with a stable order independent of dictionary insertion or aliases.
    unique: dict[str, dict[str, Any]] = {}
    for key in sorted(layouts, key=str):
        layout = layouts[key]
        reference = str(layout.get("_inst_name", key))
        if reference not in unique or str(key) == reference:
            unique[reference] = layout

    symbols: list[_Symbol] = []
    boxes: list[Bounds] = []
    for reference in sorted(unique):
        layout = unique[reference]
        anchor = tuple(layout["_ltspice_anchor"])
        definition = COMPONENT_LIBRARY.get(resolve_component_kind(layout))
        symbol_name = layout.get("_ltspice_symbol")
        if (definition is None or (symbol_name is not None
                and str(symbol_name).casefold() != definition.symbol.casefold())):
            boxes.append((*anchor, *anchor))
            continue
        degrees, mirrored = PinResolver.parse_orientation(
            str(layout.get("_ltspice_rotation", "R0")),
            bool(layout.get("_ltspice_mirror", False)),
        )
        if f"R{degrees}" not in definition.supported_rotations:
            raise ValueError(f"Rotation R{degrees} is not supported by '{definition.kind}'")
        if mirrored and not definition.supports_mirror:
            raise ValueError(f"Mirroring is not supported by '{definition.kind}'")
        origin = (anchor[0] + definition.anchor[0], anchor[1] + definition.anchor[1])
        x0, y0, x1, y1 = definition.bounds
        corners = [PinResolver.transform_offset(x, y, degrees, mirrored)
                   for x in (x0, x1) for y in (y0, y1)]
        bounds = (origin[0] + min(x for x, _ in corners),
                  origin[1] + min(y for _, y in corners),
                  origin[0] + max(x for x, _ in corners),
                  origin[1] + max(y for _, y in corners))
        labels = [(0, reference)]
        raw_value = layout.get("value")
        value = str(raw_value) if raw_value is not None else definition.default_value
        if value is not None and value != "":
            labels.append((3, value))
        symbols.append(_Symbol(reference, origin, degrees, mirrored, bounds, tuple(labels)))
        boxes.append(bounds)
    return symbols, boxes


def _net_boxes(nets: list[NetGeometry]) -> tuple[list[Bounds], list[tuple[Bounds, int]]]:
    bounds: list[Bounds] = []
    obstacles: list[tuple[Bounds, int]] = []
    for net in nets:
        for segment in net.segments:
            x0, y0 = segment.start
            x1, y1 = segment.end
            box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            bounds.append(box)
            obstacles.append((_expand(box, 4), 4))
        for pin in net.pins:
            x, y = pin.point
            bounds.append((x, y, x, y))
            obstacles.append(((x - 4, y - 4, x + 4, y + 4), 4))
        for x, y in net.flags:
            if str(net.name) == "0":
                box = (x - 16, y, x + 16, y + 24)
            else:
                width, height = _text_extent(str(net.name), 2)
                box = (x - 4, y - height - 4, x + width + 8, y + 8)
            bounds.append(box)
            obstacles.append((_expand(box, 4), 12))
    return bounds, obstacles


def _choose_windows(symbol: _Symbol, obstacles: list[tuple[Bounds, int]]) -> list[_Window]:
    """Score fixed, finite candidates; collisions outrank compactness/font size.

    Preferred order is right, left, above, below, then displaced alternatives.
    Reference is always physically above value, even for inverted symbols.
    A smaller font costs 40 distance units: use size 2 nearby if it fits, but
    prefer size 1 over a distant full-size pair or an actual collision.
    """
    best_score: tuple[int, int, int] | None = None
    best: list[_Window] = []
    x0, y0, x1, y1 = symbol.bounds
    for size in (2, 1):
        extents = [_text_extent(label, size) for _, label in symbol.labels]
        width = max(w for w, _ in extents)
        height = extents[0][1]
        pitch = 32 if size == 2 else 24
        stack_height = height + pitch * (len(extents) - 1)
        for gap in (8, 24, 48, 80):
            for shift in (0, -32, 32, -64, 64):
                # These are top-left corners of the complete stacked block.
                starts = ((x1 + gap, (y0 + y1 - stack_height) // 2 + shift),
                          (x0 - gap - width, (y0 + y1 - stack_height) // 2 + shift),
                          ((x0 + x1 - width) // 2 + shift, y0 - gap - stack_height),
                          ((x0 + x1 - width) // 2 + shift, y1 + gap))
                for left, top in starts:
                    cx = _ceil(left + width // 2)
                    cy = _ceil(top + height // 2)
                    windows = []
                    for row, ((index, _), (w, h)) in enumerate(zip(symbol.labels, extents)):
                        center = (cx, cy + row * pitch)
                        box = (center[0] - w // 2, center[1] - h // 2,
                               center[0] + w // 2, center[1] + h // 2)
                        windows.append(_Window(index, center, size, box))
                    collision = sum(_overlap(window.bounds, box) * weight
                                    for window in windows for box, weight in obstacles)
                    # Twice the Manhattan distance between symbol and label
                    # block centres favours the genuinely nearby side, not a
                    # nominally small gap on the far end of a long symbol.
                    distance = (abs(2 * cx - x0 - x1)
                                + abs(2 * cy + pitch * (len(extents) - 1) - y0 - y1))
                    score = (collision, distance + (40 if size == 1 else 0),
                             0 if size == 2 else 1)
                    # Strict comparison preserves enumeration order for ties.
                    if best_score is None or score < best_score:
                        best_score, best = score, windows
    return best


def _wrap_metadata(text: str, width: int) -> list[str]:
    """Collapse all newline/whitespace separators; never split or lose words.

    Each ordinary line fits the circuit width and an 80-character limit.
    An indivisible overlong word is retained in full and expands the bbox.
    """
    lines: list[str] = []
    line = ""
    for word in str(text).split():
        candidate = f"{line} {word}" if line else word
        if line and (len(candidate) > 80 or _text_extent(candidate, 1)[0] > width):
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def build_presentation(
    layouts: dict, nets: list[NetGeometry], title: str, description: str,
) -> Presentation:
    """Return annotations without moving components, pins, wires, or flags.

    Metadata uses size 1, separate native comment TEXT records at 24-unit
    vertical spacing, ending at least 32 units above all circuit annotations.
    Very narrow/empty circuits get a 480-unit wrapping width to avoid an
    impractically tall single-word column. There is no metadata truncation.
    """
    symbols, boxes = _symbols(layouts)
    net_boxes, obstacles = _net_boxes(nets)
    obstacles.extend((_expand(box, 4), 12) for box in boxes)
    boxes.extend(net_boxes)
    windows: dict[str, list[str]] = {}
    for symbol in symbols:
        chosen = _choose_windows(symbol, obstacles)
        records = []
        justification = "VCenter" if symbol.degrees % 180 else "Center"
        for window in chosen:
            offset = (window.center[0] - symbol.origin[0],
                      window.center[1] - symbol.origin[1])
            x, y = _inverse_offset(offset, symbol.degrees, symbol.mirrored)
            records.append(f"WINDOW {window.index} {x} {y} {justification} {window.size}")
            boxes.append(window.bounds)
            obstacles.append((_expand(window.bounds, 4), 12))
        windows[symbol.reference] = records

    circuit_bounds = _union(boxes)
    wrap_width = max(480, circuit_bounds[2] - circuit_bounds[0])
    metadata = _wrap_metadata(title, wrap_width) + _wrap_metadata(description, wrap_width)
    text: list[str] = []
    if metadata:
        x = circuit_bounds[0]
        # TEXT Left anchors the left edge and vertical centre, not the top.
        y = (circuit_bounds[1] - 32 - 9 - 24 * (len(metadata) - 1)) // 4 * 4
        for line in metadata:
            width, height = _text_extent(line, 1)
            text.append(f"TEXT {x} {y} Left 1 ;{line}")
            boxes.append((x, y - height // 2, x + width, y + height // 2))
            y += 24

    bounds = _union(boxes)
    sheet_width = _ceil(bounds[2] - bounds[0] + 64, 16)
    sheet_height = _ceil(bounds[3] - bounds[1] + 64, 16)
    return Presentation(windows, text, f"SHEET 1 {sheet_width} {sheet_height}", bounds)

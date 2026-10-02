"""Render an exported LTspice ASC using installed ASY geometry, not exporter data.

Inspection-only; imports no exporter, router, or connectivity implementation.
The only shared geometry operation is PinResolver.transform_offset. Symbols are
resolved strictly below the installed symbol root: no local/custom fallback and
no guessed bodies or pin positions. Instance WINDOW overrides are respected.

CLI (from any working directory)::

    python backend/tools/render_asc.py input.asc output.png --heading "Phase 7"

API (put backend on sys.path; tools is a namespace package)::

    from tools.render_asc import render_asc
    result = render_asc(input_path, output_path, heading="Phase 7")

This is not LTspice itself: text remains upright for inspection, pin connection
points are shown as hollow blue rings, and filled green junctions require a wire
endpoint with at least three distinct incident directions. An unsplit X never
gets a junction. Leading ASC comment headers are omitted by default, with a
separate heading above the cropped drawing; --include-description restores them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import sys
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

# Support direct invocation without requiring an __init__.py in backend/tools.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.pin_maps import PinResolver

Point = tuple[float, float]
Bounds = tuple[float, float, float, float]
BACKGROUND = (250, 250, 245)
BLUE = (32, 57, 155)
GREEN = (24, 125, 65)
TEXT_BLUE = (28, 47, 108)
GRID_COLOR = (222, 228, 220)


@dataclass(frozen=True)
class Primitive:
    kind: str
    coordinates: tuple[int, ...]
    style: int = 0


@dataclass(frozen=True)
class Window:
    number: int
    x: int
    y: int
    alignment: str
    size: int


@dataclass(frozen=True)
class Text:
    x: int
    y: int
    alignment: str
    size: int
    value: str
    description: bool = False


@dataclass
class Pin:
    x: int
    y: int
    alignment: str
    offset: int
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Symbol:
    path: Path
    primitives: list[Primitive] = field(default_factory=list)
    windows: dict[int, Window] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    pins: list[Pin] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)


@dataclass
class Instance:
    name: str
    x: int
    y: int
    orientation: str
    attributes: dict[str, str] = field(default_factory=dict)
    windows: dict[int, Window] = field(default_factory=dict)

    def transform(self, x: float, y: float) -> Point:
        degrees, mirrored = PinResolver.parse_orientation(self.orientation)
        ox, oy = PinResolver.transform_offset(x, y, degrees, mirrored)
        return self.x + ox, self.y + oy


@dataclass
class Schematic:
    path: Path
    instances: list[Instance] = field(default_factory=list)
    wires: list[tuple[Point, Point]] = field(default_factory=list)
    flags: list[tuple[Point, str]] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    primitives: list[Primitive] = field(default_factory=list)


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    width: int
    height: int
    instances: int
    wires: int
    pins: int
    junctions: int
    omitted_descriptions: int
    symbol_root: Path
    symbol_paths: tuple[Path, ...]


@dataclass(frozen=True)
class Stroke:
    points: tuple[Point, ...]
    color: tuple[int, int, int]
    style: int = 0


@dataclass(frozen=True)
class Label:
    point: Point
    text: str
    alignment: str = "Left"
    size: int = 2
    color: tuple[int, int, int] = TEXT_BLUE


@dataclass
class Scene:
    strokes: list[Stroke] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    pins: list[Point] = field(default_factory=list)
    junctions: list[Point] = field(default_factory=list)


@dataclass(frozen=True)
class PlacedLabel:
    label: Label
    xy: Point
    font_size: int
    bounds: Bounds


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if b"\x00" in data[:128]:
        return data.decode("utf-16-le")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _primitive(tokens: list[str]) -> Primitive:
    count = 8 if tokens[0] == "ARC" else 4
    if tokens[1] != "Normal" or len(tokens) not in (count + 2, count + 3):
        raise ValueError(f"Unsupported drawing record: {' '.join(tokens)}")
    coordinates = tuple(int(value) for value in tokens[2:count + 2])
    style = int(tokens[-1]) if len(tokens) == count + 3 else 0
    if style not in (0, 1, 2):
        raise ValueError(f"Unsupported drawing line style {style}")
    return Primitive(tokens[0], coordinates, style)


def _window(tokens: list[str]) -> Window:
    if len(tokens) != 6:
        raise ValueError("WINDOW requires number, x, y, alignment, size")
    return Window(int(tokens[1]), int(tokens[2]), int(tokens[3]),
                  tokens[4], int(tokens[5]))


def _text(line: str, description: bool = False) -> Text:
    tokens = line.split(maxsplit=5)
    if len(tokens) != 6:
        raise ValueError("TEXT requires x, y, alignment, size, text")
    return Text(int(tokens[1]), int(tokens[2]), tokens[3], int(tokens[4]),
                tokens[5].replace("\\n", "\n"), description)


def parse_asc(path: str | Path) -> Schematic:
    """Parse actual ASC records, associating SYMATTR/WINDOW with their SYMBOL."""
    path = Path(path).resolve()
    schematic = Schematic(path)
    current: Instance | None = None
    drawing_seen = False
    sheets = 0
    for number, raw in enumerate(_read_text(path).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        tokens = line.split()
        record = tokens[0]
        try:
            if record == "SYMBOL":
                if len(tokens) != 5:
                    raise ValueError("SYMBOL requires name, x, y, orientation")
                PinResolver.parse_orientation(tokens[4])
                current = Instance(tokens[1], int(tokens[2]), int(tokens[3]), tokens[4])
                schematic.instances.append(current)
                drawing_seen = True
            elif record == "SYMATTR":
                parts = line.split(maxsplit=2)
                if current is None or len(parts) != 3:
                    raise ValueError("SYMATTR without an associated SYMBOL or value")
                current.attributes[parts[1]] = parts[2]
            elif record == "WINDOW":
                if current is None:
                    raise ValueError("WINDOW without an associated SYMBOL")
                window = _window(tokens)
                current.windows[window.number] = window
            elif record == "WIRE":
                if len(tokens) != 5:
                    raise ValueError("WIRE requires four coordinates")
                x1, y1, x2, y2 = map(int, tokens[1:])
                schematic.wires.append(((x1, y1), (x2, y2)))
                current = None
                drawing_seen = True
            elif record == "FLAG":
                parts = line.split(maxsplit=3)
                if len(parts) != 4:
                    raise ValueError("FLAG requires x, y, name")
                schematic.flags.append(((int(parts[1]), int(parts[2])), parts[3]))
                current = None
                drawing_seen = True
            elif record == "TEXT":
                text = _text(line)
                text = Text(text.x, text.y, text.alignment, text.size,
                            text.value, not drawing_seen and text.value.startswith(";"))
                schematic.texts.append(text)
                current = None
            elif record in {"LINE", "RECTANGLE", "CIRCLE", "ARC"}:
                schematic.primitives.append(_primitive(tokens))
                drawing_seen = True
                current = None
            elif record == "SHEET":
                sheets += 1
                if sheets > 1:
                    raise ValueError("Multiple ASC sheets are not supported")
            elif record in {"Version", "IOPIN"}:
                # IOPIN is port metadata; the associated FLAG is drawn by name.
                pass
            else:
                raise ValueError(f"Unsupported ASC record {record!r}")
        except (ValueError, IndexError) as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    if not drawing_seen:
        raise ValueError(f"{path}: no schematic drawing records")
    return schematic


def detect_symbol_root(explicit: str | Path | None = None) -> Path:
    """Find installed LTspice symbols; an explicit installed root wins."""
    if explicit is not None:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Symbol root is not a directory: {root}")
        return root
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    candidates = [
        local / "LTspice" / "lib" / "sym",
        local / "LTspiceXVII" / "lib" / "sym",
        home / "Documents" / "LTspiceXVII" / "lib" / "sym",
        home / "Documents" / "LTspice" / "lib" / "sym",
    ]
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = Path(os.environ.get(variable, "C:/Program Files"))
        candidates.extend((base / "ADI" / "LTspice" / "lib" / "sym",
                           base / "LTC" / "LTspiceXVII" / "lib" / "sym"))
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "res.asy").is_file():
            return candidate.resolve()
    raise FileNotFoundError("Installed LTspice symbol root not found; use --symbol-root")


def _symbol_path(root: Path, name: str) -> Path:
    relative = Path(name.replace("\\", "/"))
    if relative.is_absolute() or ":" in name or ".." in relative.parts:
        raise ValueError(f"Symbol must be relative to installed root: {name!r}")
    if relative.suffix.lower() != ".asy":
        relative = Path(f"{relative}.asy")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError(f"Installed symbol not found: {path}")
    return path


def load_symbol(path: str | Path) -> Symbol:
    """Read installed ASY primitives, reference/value windows, and exact pins."""
    path = Path(path).resolve()
    symbol = Symbol(path)
    current_pin: Pin | None = None
    for number, raw in enumerate(_read_text(path).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        tokens = line.split()
        record = tokens[0]
        try:
            if record in {"LINE", "RECTANGLE", "CIRCLE", "ARC"}:
                symbol.primitives.append(_primitive(tokens))
                current_pin = None
            elif record == "WINDOW":
                window = _window(tokens)
                symbol.windows[window.number] = window
            elif record == "PIN":
                if len(tokens) != 5:
                    raise ValueError("PIN requires x, y, alignment, offset")
                current_pin = Pin(int(tokens[1]), int(tokens[2]), tokens[3], int(tokens[4]))
                symbol.pins.append(current_pin)
            elif record == "PINATTR":
                parts = line.split(maxsplit=2)
                if current_pin is None or len(parts) != 3:
                    raise ValueError("PINATTR without an associated PIN or value")
                current_pin.attributes[parts[1]] = parts[2]
            elif record == "SYMATTR":
                parts = line.split(maxsplit=2)
                if len(parts) != 3:
                    raise ValueError("SYMATTR requires name and value")
                symbol.attributes[parts[1]] = parts[2]
            elif record == "TEXT":
                symbol.texts.append(_text(line))
            elif record in {"Version", "SymbolType"}:
                pass
            else:
                raise ValueError(f"Unsupported ASY record {record!r}")
        except (ValueError, IndexError) as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    if not symbol.primitives:
        raise ValueError(f"{path}: symbol has no supported drawing geometry")
    return symbol


def _primitive_points(primitive: Primitive) -> tuple[Point, ...]:
    """Use exact ASY geometry; tessellate curves only for rasterization."""
    c = primitive.coordinates
    if primitive.kind == "LINE":
        return ((c[0], c[1]), (c[2], c[3]))
    left, right = sorted((c[0], c[2]))
    top, bottom = sorted((c[1], c[3]))
    if primitive.kind == "RECTANGLE":
        return ((left, top), (right, top), (right, bottom), (left, bottom), (left, top))
    cx, cy = (left + right) / 2, (top + bottom) / 2
    rx, ry = (right - left) / 2, (bottom - top) / 2
    if not rx or not ry:
        raise ValueError(f"Degenerate ellipse in {primitive}")
    start, sweep = 0.0, math.tau
    if primitive.kind == "ARC":
        # LTspice arcs proceed counterclockwise from the start ray to the end
        # ray. Screen Y points down, unlike atan2's mathematical Y coordinate.
        start = math.atan2(-(c[5] - cy) / ry, (c[4] - cx) / rx)
        end = math.atan2(-(c[7] - cy) / ry, (c[6] - cx) / rx)
        sweep = (end - start) % math.tau
        if math.isclose(sweep, 0.0):
            sweep = math.tau
    # Dense source-space tessellation; no estimated symbol dimensions/anchors.
    steps = max(16, math.ceil(sweep * max(rx, ry) * 2))
    return tuple((cx + rx * math.cos(start + sweep * i / steps),
                  cy - ry * math.sin(start + sweep * i / steps)) for i in range(steps + 1))


def _on_segment(point: Point, start: Point, end: Point) -> bool:
    px, py = point
    ax, ay = start
    bx, by = end
    return ((px - ax) * (by - ay) == (py - ay) * (bx - ax)
            and min(ax, bx) <= px <= max(ax, bx)
            and min(ay, by) <= py <= max(ay, by))


def junction_points(wires: Iterable[tuple[Point, Point]]) -> list[Point]:
    """T/shared endpoint branches only; never create a node at an unsplit X."""
    wires = list(wires)
    candidates = {point for wire in wires for point in wire}
    result = []
    for point in sorted(candidates):
        rays = set()
        for start, end in wires:
            if start == end or not _on_segment(point, start, end):
                continue
            for target in (start, end):
                dx, dy = int(target[0] - point[0]), int(target[1] - point[1])
                divisor = math.gcd(abs(dx), abs(dy))
                if divisor:
                    rays.add((dx // divisor, dy // divisor))
        if len(rays) >= 3:
            result.append(point)
    return result


def _alignment(alignment: str, instance: Instance | None = None) -> str:
    # Keep glyphs upright but transform the window's anchoring side with the body.
    alignment = alignment.title()
    if alignment.startswith("V"):
        alignment = alignment[1:]
    vectors = {"Left": (1, 0), "Right": (-1, 0), "Top": (0, 1), "Bottom": (0, -1)}
    if alignment == "Center":
        return alignment
    if alignment not in vectors:
        raise ValueError(f"Unsupported text alignment {alignment!r}")
    if instance is None:
        return alignment
    degrees, mirrored = PinResolver.parse_orientation(instance.orientation)
    vector = PinResolver.transform_offset(*vectors[alignment], degrees, mirrored)
    return next(key for key, value in vectors.items() if value == vector)


def _add_primitive(scene: Scene, primitive: Primitive, instance: Instance | None = None) -> None:
    points = _primitive_points(primitive)
    if instance:
        points = tuple(instance.transform(x, y) for x, y in points)
    scene.strokes.append(Stroke(points, BLUE, primitive.style))


def _build_scene(schematic: Schematic, symbols: dict[str, Symbol],
                 include_description: bool) -> tuple[Scene, int]:
    scene = Scene()
    for wire in schematic.wires:
        scene.strokes.append(Stroke(wire, GREEN))
    for primitive in schematic.primitives:
        _add_primitive(scene, primitive)
    for instance in schematic.instances:
        symbol = symbols[instance.name]
        for primitive in symbol.primitives:
            _add_primitive(scene, primitive, instance)
        attributes = symbol.attributes | instance.attributes
        windows = symbol.windows | instance.windows
        for number, name in ((0, "InstName"), (3, "Value")):
            value = attributes.get(name)
            window = windows.get(number)
            if value and window and window.size > 0:
                scene.labels.append(Label(instance.transform(window.x, window.y), value,
                                          _alignment(window.alignment, instance), window.size))
            elif value and window is None:
                raise ValueError(f"{instance.name}: {name} has no ASY/ASC WINDOW {number}; "
                                 "refusing to guess a label position")
        for text in symbol.texts:
            if text.size > 0:
                scene.labels.append(Label(instance.transform(text.x, text.y), text.value,
                                          _alignment(text.alignment, instance), text.size))
        for pin in symbol.pins:
            scene.pins.append(instance.transform(pin.x, pin.y))
            if pin.alignment.upper() != "NONE" and pin.attributes.get("PinName"):
                alignment = _alignment(pin.alignment)
                # ASY PIN's offset is measured toward the symbol's interior.
                direction = {"Left": (1, 0), "Right": (-1, 0),
                             "Top": (0, 1), "Bottom": (0, -1), "Center": (0, 0)}[alignment]
                point = instance.transform(pin.x + direction[0] * pin.offset,
                                           pin.y + direction[1] * pin.offset)
                scene.labels.append(Label(point, pin.attributes["PinName"],
                                          _alignment(pin.alignment, instance), 1))
    for point, name in schematic.flags:
        x, y = point
        if name == "0":
            scene.strokes.append(Stroke(((x - 8, y), (x + 8, y), (x, y + 16), (x - 8, y)), GREEN))
            scene.labels.append(Label((x + 14, y + 8), "0", "Left", 1, GREEN))
        else:
            scene.labels.append(Label((x + 6, y - 7), name, "Bottom", 2, GREEN))
    omitted = 0
    for text in schematic.texts:
        if text.description and not include_description:
            omitted += 1
            continue
        value = text.value[1:] if text.value.startswith((";", "!")) else text.value
        if value and text.size > 0:
            scene.labels.append(Label((text.x, text.y), value, _alignment(text.alignment), text.size))
    scene.junctions = junction_points(schematic.wires)
    return scene, omitted


class _Fonts:
    def __init__(self) -> None:
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        candidates = (windir / "Fonts" / "segoeui.ttf", windir / "Fonts" / "arial.ttf",
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        self.path = next((str(path) for path in candidates if path.is_file()), "DejaVuSans.ttf")
        self.cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def get(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if size not in self.cache:
            try:
                self.cache[size] = ImageFont.truetype(self.path, size)
            except OSError:
                self.cache[size] = ImageFont.load_default(size=size)
        return self.cache[size]


def _union(bounds: Iterable[Bounds]) -> Bounds:
    values = list(bounds)
    if not values:
        raise ValueError("Empty drawing")
    return (min(b[0] for b in values), min(b[1] for b in values),
            max(b[2] for b in values), max(b[3] for b in values))


def _layout(scene: Scene, scale: float, fonts: _Fonts) -> tuple[Bounds, list[PlacedLabel]]:
    points = [point for stroke in scene.strokes for point in stroke.points] + scene.pins
    bounds: list[Bounds] = [(x * scale - 4, y * scale - 4, x * scale + 4, y * scale + 4)
                            for x, y in points]
    labels = []
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for label in scene.labels:
        size = max(16, min(36, round((14 + 3 * label.size) * scale)))
        box = measure.multiline_textbbox((0, 0), label.text, font=fonts.get(size), spacing=4)
        width, height = box[2] - box[0], box[3] - box[1]
        x, y = label.point[0] * scale, label.point[1] * scale
        if label.alignment in {"Center", "Top", "Bottom"}:
            x -= width / 2
        elif label.alignment == "Right":
            x -= width
        if label.alignment in {"Left", "Right", "Center"}:
            y -= height / 2
        elif label.alignment == "Bottom":
            y -= height
        placed = (x, y, x + width, y + height)
        labels.append(PlacedLabel(label, (x - box[0], y - box[1]), size, placed))
        bounds.append(placed)
    return _union(bounds), labels


def _draw_stroke(draw: ImageDraw.ImageDraw, points: list[Point], color: tuple[int, int, int],
                 width: int, style: int, factor: int) -> None:
    if style == 0:
        draw.line(points, fill=color, width=width, joint="curve")
        return
    # ASY style 1 = dashed, style 2 = dotted, with continuous phase around curves.
    on, off = (6 * factor, 4 * factor) if style == 1 else (factor, 3 * factor)
    phase = 0.0
    for start, end in zip(points, points[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        position = 0.0
        while position < length:
            period = on + off
            in_dash = phase % period < on
            remaining = (on if in_dash else period) - phase % period
            step = min(remaining, length - position)
            if in_dash:
                a = (start[0] + dx * position / length, start[1] + dy * position / length)
                b = (start[0] + dx * (position + step) / length,
                     start[1] + dy * (position + step) / length)
                draw.line((a, b), fill=color, width=width)
            position += step
            phase += step


def _wrap_heading(text: str, width: int, fonts: _Fonts) -> list[str]:
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for character in paragraph:
            if line and measure.textlength(line + character, font=fonts.get(30)) > width:
                lines.append(line.rstrip())
                line = ""
            line += character
        lines.append(line.rstrip())
    return lines


def render_asc(asc_path: str | Path, output_path: str | Path, *,
               symbol_root: str | Path | None = None, heading: str | None = None,
               width: int = 1800, grid: bool = False,
               include_description: bool = False) -> RenderResult:
    """Write an aspect-preserving, label-inclusive cropped PNG inspection image.

    Width is constrained to 1500..2000 pixels. Height follows the schematic's
    aspect ratio, with separate heading space and 48px crop padding. Errors are
    raised before saving if a required installed symbol/window is unavailable.
    """
    if not 1500 <= width <= 2000:
        raise ValueError("Inspection image width must be between 1500 and 2000")
    output = Path(output_path).resolve()
    if output.suffix.lower() != ".png":
        raise ValueError("Output path must have a .png extension")
    schematic = parse_asc(asc_path)
    root = detect_symbol_root(symbol_root)
    symbols = {name: load_symbol(_symbol_path(root, name))
               for name in dict.fromkeys(instance.name for instance in schematic.instances)}
    scene, omitted = _build_scene(schematic, symbols, include_description)
    fonts = _Fonts()
    padding = 48
    available = width - padding * 2
    bounds, _ = _layout(scene, 1.0, fonts)
    scale = available / max(1, bounds[2] - bounds[0])
    for _ in range(16):
        bounds, labels = _layout(scene, scale, fonts)
        span = bounds[2] - bounds[0]
        if abs(span - available) < 0.25:
            break
        scale *= available / max(1, span)
    bounds, labels = _layout(scene, scale, fonts)
    title = heading or schematic.path.stem.replace("_", " ")
    title_lines = _wrap_heading(title, available, fonts)
    header_height = 34 + 38 * len(title_lines) + 36
    height = math.ceil(bounds[3] - bounds[1]) + padding * 2 + header_height
    # Supersampling changes raster quality, never schematic geometry/aspect.
    factor = 2
    image = Image.new("RGB", (width * factor, height * factor), BACKGROUND)
    draw = ImageDraw.Draw(image)
    tx = padding + (available - (bounds[2] - bounds[0])) / 2 - bounds[0]
    ty = header_height + padding - bounds[1]

    def pixel(point: Point) -> Point:
        return ((point[0] * scale + tx) * factor, (point[1] * scale + ty) * factor)

    if grid:
        world_left, world_right = bounds[0] / scale, bounds[2] / scale
        world_top, world_bottom = bounds[1] / scale, bounds[3] / scale
        for x in range(math.ceil(world_left / 16) * 16, math.floor(world_right / 16) * 16 + 1, 16):
            for y in range(math.ceil(world_top / 16) * 16, math.floor(world_bottom / 16) * 16 + 1, 16):
                px, py = pixel((x, y))
                draw.ellipse((px, py, px + factor, py + factor), fill=GRID_COLOR)
    for stroke in scene.strokes:
        _draw_stroke(draw, [pixel(point) for point in stroke.points], stroke.color,
                     2 * factor, stroke.style, factor)
    for point in scene.pins:
        x, y = pixel(point)
        radius = 2.5 * factor
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     outline=BLUE, width=factor)
    for point in scene.junctions:
        x, y = pixel(point)
        radius = 3.4 * factor
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=GREEN)
    for placed in labels:
        xy = ((placed.xy[0] + tx) * factor, (placed.xy[1] + ty) * factor)
        draw.multiline_text(xy, placed.label.text, font=fonts.get(placed.font_size * factor),
                            fill=placed.label.color, spacing=4 * factor)
    for index, line in enumerate(title_lines):
        draw.text((padding * factor, (22 + index * 38) * factor), line,
                  font=fonts.get(30 * factor), fill=TEXT_BLUE)
    caption = (f"{schematic.path.name}   |   {len(schematic.instances)} symbols / "
               f"{len(schematic.wires)} wires   |   pins: hollow blue; junctions: solid green")
    caption_size = 16
    while caption_size > 10 and draw.textlength(caption, font=fonts.get(caption_size * factor)) > available * factor:
        caption_size -= 1
    draw.text((padding * factor, (28 + len(title_lines) * 38) * factor), caption,
              font=fonts.get(caption_size * factor), fill=(82, 94, 105))
    line_y = (header_height - 8) * factor
    draw.line((padding * factor, line_y, (width - padding) * factor, line_y),
              fill=(211, 218, 208), width=factor)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width, height), Image.Resampling.LANCZOS).save(output, format="PNG")
    return RenderResult(output, width, height, len(schematic.instances), len(schematic.wires),
                        len(scene.pins), len(scene.junctions), omitted, root,
                        tuple(symbol.path for symbol in symbols.values()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("asc", type=Path, help="Actual exported LTspice .asc file")
    parser.add_argument("png", type=Path, help="Output PNG path (not added to git)")
    parser.add_argument("--symbol-root", type=Path, help="Explicit installed LTspice lib/sym root")
    parser.add_argument("--heading", "--title", dest="heading", help="Separate heading above the drawing")
    parser.add_argument("--width", type=int, default=1800, help="1500..2000 pixels (default: 1800)")
    parser.add_argument("--grid", action="store_true", help="Show a subtle 16-unit dot grid")
    parser.add_argument("--include-description", action="store_true", help="Draw leading ASC comment headers too")
    args = parser.parse_args(argv)
    try:
        result = render_asc(args.asc, args.png, symbol_root=args.symbol_root,
                            heading=args.heading, width=args.width, grid=args.grid,
                            include_description=args.include_description)
    except (OSError, ValueError) as error:
        parser.exit(2, f"render_asc: {error}\n")
    print(f"Wrote {result.output_path} ({result.width}x{result.height}); "
          f"{result.instances} symbols, {result.wires} wires, {result.pins} pins, "
          f"{result.junctions} junctions; omitted {result.omitted_descriptions} descriptive headers")
    print(f"Installed symbols: {result.symbol_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

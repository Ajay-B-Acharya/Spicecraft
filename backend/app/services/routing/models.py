"""Router data only; ASC serialization and logical connectivity stay elsewhere."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.asc_validation import ExportDiagnostic, NetGeometry, PinPoint, WireSegment
from app.services.grid_system import Point
from app.services.pin_maps import PinOrientation


@dataclass(frozen=True)
class RoutingOptions:
    """Bounded deterministic search, not a promise of arbitrary planar routability.

    Clearance/label spacing are LTspice units. A compressed grid has at most
    |X|*|Y| vertices (quadratic in feature count, independent of coordinate span).
    Each visibility edge checks O(bodies + pins + occupied segments) geometry.
    Directional A* has at most four states per vertex. Limits bound each search;
    route-order/envelope retries multiply that cost. Only measured fixture scale
    is supported by tests; no 500-component scalability claim is made.
    """
    clearance: int = 16
    bend_penalty: int = 64
    label_spacing: int = 32
    max_grid_vertices: int = 120_000
    max_search_states: int = 80_000
    envelope_margins: tuple[int, ...] = (64, 160, 320)
    max_order_attempts: int = 4
    allow_crossings: bool = True


@dataclass(frozen=True)
class RoutingPin:
    terminal: PinPoint
    facing: PinOrientation
    net: str | None
    escape: Point

    @property
    def key(self) -> str:
        return f"{self.terminal.component}.{self.terminal.pin}"

    @property
    def point(self) -> Point:
        return self.terminal.point


@dataclass(frozen=True)
class ComponentObstacle:
    component: str
    bounds: tuple[int, int, int, int]
    expanded: tuple[int, int, int, int]


@dataclass(frozen=True)
class RoutedFlag:
    net: str
    point: Point
    name: str


@dataclass(frozen=True)
class SafeCrossing:
    nets: tuple[str, str]
    point: Point


@dataclass
class RoutingProblem:
    pins: dict[str, RoutingPin]
    obstacles: list[ComponentObstacle]
    options: RoutingOptions


@dataclass
class RoutingResult:
    net_geometries: list[NetGeometry] = field(default_factory=list)
    junctions: dict[str, tuple[Point, ...]] = field(default_factory=dict)
    diagnostics: list[ExportDiagnostic] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)
    flags: list[RoutedFlag] = field(default_factory=list)
    crossings: tuple[SafeCrossing, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)


# Reuse NetGeometry/PinPoint/WireSegment throughout: no parallel wire model.
__all__ = ["RoutingOptions", "RoutingResult", "RoutedFlag", "SafeCrossing",
           "RoutingPin", "RoutingProblem", "ComponentObstacle", "WireSegment"]

"""Single grid utility for everything written into an LTspice ``.asc`` file.

LTspice snaps schematic coordinates to a 16-unit grid. Component anchors, pin
coordinates, wire vertices, junctions and flags all live in this one coordinate
space, so they all go through this module. Do not re-implement snapping elsewhere.

Note: this is the *LTspice* grid. The browser schematic canvas has its own,
unrelated grid; canvas coordinates are never written into a ``.asc`` file.
"""

from __future__ import annotations

Point = tuple[int, int]

GRID_SIZE = 16


class GridSystem:
    """Deterministic snapping and on-grid checks for LTspice coordinates."""

    SIZE = GRID_SIZE

    @classmethod
    def snap(cls, value: float) -> int:
        """Snap a single coordinate to the nearest grid line."""
        return int(round(value / cls.SIZE) * cls.SIZE)

    @classmethod
    def snap_point(cls, point: tuple[float, float]) -> Point:
        """Snap an (x, y) pair to the grid."""
        return cls.snap(point[0]), cls.snap(point[1])

    @classmethod
    def is_on_grid(cls, value: int) -> bool:
        """True when ``value`` sits exactly on a grid line."""
        return value % cls.SIZE == 0

    @classmethod
    def is_point_on_grid(cls, point: Point) -> bool:
        """True when both coordinates of ``point`` sit exactly on grid lines."""
        return cls.is_on_grid(point[0]) and cls.is_on_grid(point[1])

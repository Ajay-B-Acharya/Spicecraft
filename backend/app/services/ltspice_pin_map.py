"""Compatibility exports for the LTspice pin-map helpers.

New exporter code should import from app.services.pin_maps. This module remains
so older imports continue to resolve while pin mapping lives in one place.
"""

from app.services.pin_maps import (
    PIN_MAPS,
    PinCoordinate,
    get_pin_coordinate,
    resolve_component_kind,
    resolve_symbol_name,
)

__all__ = [
    "PIN_MAPS",
    "PinCoordinate",
    "get_pin_coordinate",
    "resolve_component_kind",
    "resolve_symbol_name",
]

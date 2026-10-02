# Phase 7.5 — Work-in-progress checkpoint

This checkpoint was committed at the user's request before Phase 7.5 was complete.

## Implemented

- Topology-aware physical layout hints for supported two-component chains, active-device neighbourhoods, and the four-diode bridge. The layout changes anchors and rotations; it does not change circuit definitions, electrical net membership, canonical pin identities, or symbol pin offsets.
- Exporter and circuit geometry debugger share the bulk placement path.
- Measurement-only routing metrics helper and 24 hand-computable metric tests. The helper is not yet integrated into every export/report.
- Seven layout-probe exports, renderings, and actual LTspice netlists under `backend/tests/artifacts/phase_7_5/layout_probe/`.

## Verification at this checkpoint

Actual LTspice verification passed for Common Emitter, RC low-pass, RC high-pass, voltage divider, bridge rectifier, NE555, and LED blinker: 60 canonical component pins, 32 electrical groups, no shorts, opens, missing pins, or unexpected pins. All seven current routes have zero crossings.

| Circuit | Phase 7 wire length | Current wire length |
| --- | ---: | ---: |
| Common Emitter | 5008 | 1536 |
| RC low-pass | 544 | 224 |
| RC high-pass | 496 | 224 |
| Voltage divider | 528 | 160 |
| Bridge rectifier | 4016 | 1648 |
| NE555 | 4320 | 2400 |
| LED blinker | 3008 | 1472 |

The complete backend suite ran **196 tests in 26.541 seconds and reported 20 assertion failures**:

- Five subcases freeze the old Phase 6 symbol/header bytes, including old placement.
- One assertion requires all Common Emitter symbols to remain R0.
- Thirteen subcases reconstruct old index-based placement instead of the new shared bulk placement when comparing pin coordinates.
- One debugger assertion unconditionally expects a nonconductive crossing, although the new Common Emitter route has none.

These failures have not been fixed or suppressed in this checkpoint. Independent serialized-pin and real-LTspice electrical checks passed. Frontend tests were not rerun for this push-only checkpoint; no frontend source was changed.

## Incomplete work

- Routing candidate cost, detour penalties, and shared-junction selection refinements are not implemented; the existing Phase 7 router remains in use.
- Text/label-clearance improvements, layout regression tests, and a complete before/after metric report remain incomplete.
- Existing physical-layout assertions need deliberate updates while preserving independent electrical and pin-coordinate oracles.
- Final native screenshot capture and image-capable visual acceptance remain incomplete. No professional-appearance or visual-pass claim is made.

Phase 7.5 acceptance criteria are **not met yet**. This commit is an intermediate checkpoint, not a release approval.

Unrelated pre-existing `frontend/tsconfig.tsbuildinfo` and `backend/_probe_geo.py` were excluded.

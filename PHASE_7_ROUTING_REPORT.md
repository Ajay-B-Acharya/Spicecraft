# Phase 7 — Manhattan Wire Routing

## Scope and architecture

Phase 6.5 was pushed separately as `e8bb314`. Phase 7 replaces the existing exporter’s unsafe centroid/single-elbow wire geometry with a dedicated backend routing layer. It does not change any bundled circuit definition, electrical net membership, component position, symbol definition, pin coordinate, or canonical grid.

The implemented pipeline is:

```text
Source circuit
  -> existing canonical pin mapping and validated electrical nets
  -> existing component placement and exact PinResolver coordinates
  -> dedicated Manhattan router
  -> shared-net optimization and intentional junctions
  -> existing ASC serializer
  -> independent geometry validation
  -> real LTspice netlist partition comparison
```

Python modules follow the backend architecture because the existing LTspice exporter operates there. No second TypeScript routing engine or React Flow-derived electrical system is introduced.

## Existing routing discovered

The previous exporter routed each pin horizontally first to a centroid or special-label hub. It did not avoid component bodies, foreign pins, collinear foreign wires, or conductive T contacts. Common Emitter produced 23 WIRE statements and 22 geometry warnings. Actual LTspice netlisting merged VCC, bias, collector, emitter, and ground onto `0`; only VOUT remained separate. Baseline artifacts are preserved in `backend/tests/artifacts/phase_6_5/`.

## Routing strategy

The routing engine consumes the validated source partition and immutable placed layouts. Exact pin endpoints and all library-defined pin regions are reserved, including unconnected pins. Straight outward escapes follow each pin’s transformed facing direction; only the owning net may use them, and unused reservations are not serialized.

Path finding is deterministic. Low-bend Manhattan candidates are tested before a compressed orthogonal visibility-grid search with length, bends, and crossing penalties. Multi-pin nets grow one shared tree by attaching the next pin to a valid existing tree point rather than generating all pairwise connections. Stable ordering and tie-breaking make repeated exports reproducible.

Component obstacles use the existing symbol bounds transformed by the existing PinResolver orientation convention and canonical grid clearance. Routing does not move components to make a path fit.

Unrelated conductive contacts are forbidden. A fallback perpendicular crossing is allowed only strictly inside both unsplit wires, with no endpoint, pin, FLAG, or junction at that coordinate. This rule was independently measured using LTspice 24.1.9; crossing coordinates must remain protected during subsequent tree attachment and optimization.

Optimization removes zero-length and duplicate segments, unions collinear coverage, and retains exact protected pin/junction endpoints. Junctions are intentional same-net branch coordinates, not unrelated intersections. No unsafe direct-wire fallback is emitted on failure; an ERROR diagnostic identifies the net and reason.

## Verification and evidence

Verified on 2026-10-02 using Python 3.13.7, Windows 11 build 26200, and installed LTspice 24.1.9. All five unchanged bundled circuits and two genuine supported-symbol regression fixtures produced deterministic exports with **zero diagnostics, shorts, opens, missing pins, or unexpected pins**. Independent real-netlist comparison covers **60 canonical component pins in 32 electrical groups**, including each unwired pin as a separate singleton.

### Real LTspice results and routing metrics

| Circuit | Components | Pins | Electrical groups | WIRE segments | Wire length | Safe crossings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Common Emitter | 6 | 13 | 6 | 36 | 5008 | 2 |
| NE555 astable | 4 | 14 | 7 | 36 | 4320 | 3 |
| LED blinker | 5 | 11 | 6 | 24 | 3008 | 0 |
| RC high-pass | 2 | 4 | 3 | 7 | 496 | 0 |
| RC low-pass | 2 | 4 | 3 | 7 | 544 | 0 |
| Voltage divider regression | 2 | 4 | 3 | 7 | 528 | 0 |
| Diode bridge regression | 5 | 10 | 4 | 24 | 4016 | 0 |

Lengths are summed Manhattan lengths in LTspice coordinate units. Electrical group counts include NE555's three unwired pins and LED Q1.E. These singleton groups are not serialized as invented wires or labels.

The real Common Emitter netlist now contains:

```text
Q1 N002 N001 N003 0 BC547
R1 VCC N001 100k
R2 N001 0 10k
R3 N002 VCC 1k
C1 N003 0 10µF
C2 N002 VOUT 100µF
```

Unlike the frozen Phase 6.5 negative control, VCC, base, collector, emitter, ground, and VOUT remain six separate intended nets. Q1's fourth node is the stock LTspice substrate/default node, not an added source pin. The netlist is a connectivity result, not a transient/DC simulation claim.

The router tries all four distinct deterministic planar orders for Common Emitter and NE555 before accepting an audited fallback with two and three unsplit interior crossings. No search budget is exhausted for these exports; planar failure is not proof that a crossing-free solution cannot exist. LED and both filters succeed in the first planar attempt. The bridge succeeds in the second planar order without crossings.

### Regression checks

- The initial complete backend run passed **137 tests**, including installed-LTspice junction microfixtures, negative-baseline detection, all bundled output partitions, source immutability, exact pin geometry, and blocked malformed/injected routes.
- Added `backend/tests/test_routing.py`: **25 focused direct regressions** for normalization, preserved pin/escape endpoints and junctions, protected crossings during later attachment, unused-pin reservations, real-symbol detours, bounded search exhaustion, invalid options, and determinism. Both grid and state exhaustion must discard previously completed net geometry and flags.
- Added `backend/tests/test_routing_fixtures.py`: **10 regressions**, including actual LTspice divider/bridge tests. Fixture definitions live only in `backend/tests/fixtures/routing/`; the five bundled definitions are unchanged.
- Frontend: **28 tests passed, zero skips**. Independent `npm --prefix frontend run typecheck` passed. `npm --prefix frontend run build` passed; the build itself skips types, so independent checking was run separately and repeated after restoring its generated `next-env.d.ts` side effect.
- **Final expanded backend suite: 172 tests passed in 50.554 seconds, zero failures/errors/skips**, including all actual LTspice tests. An earlier full-suite run started before the direct-test helper correction and reported two failures caused by treating a legitimate owner escape lead as an obstacle collision. Only that test assertion was corrected; the successful complete rerun is preserved in `backend_tests_final.log`, with the earlier result retained in `backend_tests.log`. No production defect was found during this continuation.

### Evidence artifacts

`backend/tests/artifacts/phase_7/` contains each bundled circuit's `.asc`, actual LTspice `.net`, routing/partition JSON, and inspection `.png`, plus `routing_summary.json`, `performance.json`, the initial expanded-suite `backend_tests.log`, and the successful final `backend_tests_final.log`. `fixtures/` contains the same export/netlist/JSON/PNG evidence for the divider and diode bridge. Both routing summaries report `all_verified: true` and `all_deterministic: true`.

Inspection images load installed ASY primitives and show pin positions and intentional junctions; they are not screenshots of LTspice. Rendering succeeded for all seven exports. **Visual acceptance is not claimed:** the current session's image input is unavailable, so readability/label overlap could not be visually assessed. Programmatic geometry checks and actual electrical netlisting passed independently of this limitation.

The backend virtual environment lacks Pillow. The first `--render` attempt therefore failed with `ModuleNotFoundError: No module named 'PIL'`; electrical verification was rerun successfully in that environment, and the complete render/export command succeeded using the existing system Python with Pillow 12.3.0. No dependency or environment configuration was changed.

### Measured performance

Three sequential strict exports per bundled circuit measured the complete connectivity/placement/routing/validation/serialization pipeline, excluding LTspice invocation and image rendering. Recorded minimum–maximum times: Common Emitter **328.7–332.5 ms**, NE555 **272.6–300.3 ms**, LED **5.2–5.9 ms**, RC high-pass **0.72–0.81 ms**, and RC low-pass **0.79–1.44 ms**. Raw samples and environment details are in `performance.json`. This tests only 2–6 components, not large-scale production routing.

### Reproduction and repository state

```bash
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -v
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
python -B backend/tools/export_routing_report.py --output backend/tests/artifacts/phase_7 --render --require-ltspice
python -B backend/tools/export_routing_report.py --output backend/tests/artifacts/phase_7/fixtures --render --require-ltspice --circuit backend/tests/fixtures/routing/voltage_divider.json --circuit backend/tests/fixtures/routing/bridge_rectifier.json
```

The render commands require Pillow in the selected Python and installed LTspice/symbols. Tests may skip real-LTspice checks on other hosts without those dependencies; no such skips are counted as electrical verification here.

No circuit JSON under `backend/circuits/`, canonical pin-map coordinate, placement constant, or grid utility changed. The pre-existing unrelated `frontend/tsconfig.tsbuildinfo` and `backend/_probe_geo.py` remain preserved. Build-generated `frontend/next-env.d.ts` was restored to its original contents. **No commit or push was performed**; Phase 7 remains in the working tree on `phase/7-manhattan-routing`.

## Known source/library constraints

- The unchanged Common Emitter source has no emitter DC return and is not a complete simulation-ready amplifier. Routing correctness preserves its actual six-net topology; it does not add a resistor or input/source/load.
- The unchanged LED template leaves Q1.E floating. The unchanged NE555 template leaves RESET/output/control pins unconnected. These pins must remain separate and protected from foreign wires.
- The repository contains five unchanged bundled circuit definitions: Common Emitter, RC low-pass, RC high-pass, LED blinker, and NE555 astable. Voltage divider and diode bridge coverage was added through genuine supported-symbol regression fixtures because no equivalent bundled definitions exist.
- The current canonical backend symbol/pin library has no op-amp definition. Substituting a resistor or NE555 would falsify coverage and violate the requested architectural constraints. Op-amp production export coverage is therefore an explicit limitation, not a claimed pass.
- Compressed-grid search has bounded deterministic budgets and is not claimed to have been proven at 500 components. Performance measurements below report tested scale only.

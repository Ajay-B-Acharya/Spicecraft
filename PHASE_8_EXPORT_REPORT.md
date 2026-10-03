# Phase 8 — LTspice export optimization and schematic polish

## Result

The incremental exporter changes pass **259 backend tests**, **28 frontend tests**, independent TypeScript checks, and the production build. All seven regression circuits pass actual LTspice netlisting and native schematic opening. Their **60 canonical pins and 32 electrical groups** are preserved, including intentionally unwired singleton pins. No shorts, opens, missing pins, unexpected pins, duplicate wires, or zero-length exported wires were found.

Wire records decreased **105 → 83 (21.0%)** without changing any occupied wire path: total length remains **7,664 LTspice units**, bends remain 35, and junctions remain 8. All seven remain crossing-free. Common Emitter retains its compact bias, collector, emitter/capacitor, and output paths.

**Scope qualification:** this validates the existing six-kind backend component library and seven requested circuits. The backend did not previously support wired voltage-source components. That capability was not added because it requires extending the canonical pin/library system, outside the requested exporter-only boundary. These results are connectivity/export acceptance, not circuit simulation acceptance.

## 1. Files changed

### Production

- `backend/app/services/ltspice_exporter.py`: serialization order, safe cleanup integration, presentation integration, export-record preflight, circuit-qualified diagnostics.
- `backend/app/services/asc_validation.py`: unique valid edge incidence, malformed-record exclusion, duplicate diagnostics, optional circuit context.
- `backend/app/services/export_cleanup.py` (new): conservative serialization-only wire/flag cleanup.
- `backend/app/services/export_presentation.py` (new): deterministic WINDOW placement, compact metadata, presentation bounds and SHEET dimensions.

### Tools

- `backend/tools/export_polish_report.py` (new): independent before/after measurements, occupied-path comparisons, installed-symbol pin checks, actual netlist comparisons, JSON/Markdown evidence.
- `backend/tools/render_asc.py`: fixes vertical WINDOW alignment parsing (`VCenter`, `VLeft`, etc.).

### Tests

- New: `backend/tests/test_export_cleanup.py`, `test_export_polish.py`, `test_export_polish_metrics.py`, `test_export_presentation.py` — **63 additional tests**.
- Updated: `backend/tests/test_connectivity.py`, `test_pin_geometry.py`, `test_routing_integration.py` — correct stale pre-7.5 physical expectations while retaining independent frozen coordinates, canonical pins, source partitions, exact emitted/returned geometry, and real-LTspice checks.

### Evidence

- This report.
- `backend/tests/artifacts/phase_8/before/` and `after/`: seven ASC files, real LTspice netlists, full-metadata inspection renderings, and routing reports each.
- `before_native/` and `after_native/`: isolated native schematic copies, seven screenshots each, and capture metadata.
- `metrics/polish_report.json` and `.md`: complete before/after metrics and invariant results.
- `determinism.json`, `visual_results.json`, and `logs/`: process-repeatability, visual inspection, baseline/final test and build evidence.

No circuit JSON, routing-engine module, schematic-layout module, pin-map module, frontend source, or dependency configuration changed. The pre-existing `frontend/tsconfig.tsbuildinfo` and untracked `backend/_probe_geo.py` are preserved and excluded. The build-generated `next-env.d.ts` import change was restored.

## 2. Exporter audit and structure

### Before

- `Version 4` and fixed `SHEET 1 1200 800`.
- Title and description appeared first as size-2 TEXT at fixed coordinates, irrespective of circuit extent.
- SYMBOL blocks followed source order, each with InstName then optional Value.
- No WINDOW overrides; stock symbol attributes rotated with symbols, including vertical capacitor labels.
- Each routed net interleaved FLAG and WIRE records. Labels and ground were ordinary LTspice FLAG records; junctions were represented by conductive wire endpoints, not a separate invented record.
- The router already eliminated many duplicates, but retained protected escape subdivisions that were unnecessary in final ASC serialization.
- Duplicate wire records could inflate validator endpoint degree and disguise a dangling spur. Case-insensitive instance-name collisions were not blocked at export preflight.

### After

The native Version-4 structure is:

```text
Version
Sheet
Symbol
  Window overrides
  InstName
  Value (when provided)
...remaining complete symbol blocks...
Wires
Flags / electrical labels / ground
Title and description comment text
```

WINDOW and SYMATTR remain attached to their own SYMBOL, rather than being globally sorted away from it. Components use natural reference sorting only **after** placement and routing. Wires have canonical endpoint direction and coordinate ordering; flags are unique and sorted. Attribute order is fixed. No random reference generation was introduced.

The same seven inputs produced identical SHA-256 ASC hashes in **five separate Python processes with different hash seeds**: 35 exports. Existing repeated-export regression checks also pass. Reordering a source component array is not promised to retain placement; Phase 8 deliberately does not reorder layout inputs.

Canonical symbol selection, identity-conflict rejection, source values, orientation, position, and pin resolution remain unchanged. Zero-valued attributes and source spellings such as `10uF`, `100uF`, and `10µF` are preserved. Invalid reference tokens, case-insensitive duplicate references, and embedded ASC record separators in attributes block export rather than renaming components or emitting injected records.

## 3. Cleanup and validation algorithms

1. Validate immutable source membership, all canonical symbol pins, routed pin coordinates, flags, and raw geometry.
2. Count endpoint incidence from **distinct, valid undirected edges**. Duplicate/reversed copies do not make a dangling endpoint valid. Diagonal, off-grid, zero-length, and wrong-net records cannot supply connectivity.
3. Copy net containers; retain source pin identities and membership. Deduplicate undirected same-net edges and same-coordinate flags.
4. Remove a fully covered collinear edge only when its removal preserves required terminal/contact endpoints.
5. Merge adjacent collinear segments only at an unprotected degree-two boundary with opposite directions.
6. Protect every pin, flag, and existing conductive T/X boundary, including contacts to perpendicular interiors. Never split an unsplit crossing or infer connectivity from coincident appearance.
7. Validate cleaned geometry and source membership again before serialization. Return this exact cleaned geometry to the debugger and update its wire count/length metrics; no second route is computed.

The cleanup helper can discard zero-length records, but the public exporter intentionally **rejects invalid raw zero-length routes first**, preserving existing fail-closed tests. It does not silently repair broken router output, snap endpoints, prune dangling stubs, add wires, or change topology. Arbitrary partially overlapping runs are conservatively retained rather than union-normalized if safe endpoint preservation is not established.

Duplicate *source components* are rejected rather than merged: discarding one could change topology or identity. Exported symbol blocks, attribute keys, windows, and flags are unique by construction.

Failures report the circuit and error code, with net/component/pin and expected/actual coordinates where applicable. Non-pin record errors identify their relevant reference/net rather than inventing a pin. `strict=False` does not bypass electrical safety.

## 4. Labels, references, values, title and description

- Deterministic finite candidate scoring places reference/value WINDOW pairs around canonical transformed symbol bounds. Component graphics, wire corridors, electrical labels, and already placed attributes are obstacles.
- Native Center/VCenter overrides keep reference/value text horizontal and place the reference physically above its value even for rotated symbols. Confirmed in LTspice for the actual R180 and R270 regression symbols.
- Text stays size 2 where practical; size 1 is available in constrained corridors. Values are measured but never rewritten.
- Electrical FLAG anchors and names do not move. LTspice chooses their native orientation; some labels on vertical runs remain vertical and readable. Ground remains a native `FLAG ... 0` triangle, not a renamed electrical net or an added ground wire.
- Title/description use size-1 comment TEXT above all circuit annotations, with 24-unit line pitch and at least a 32-unit modeled gap. Metadata wraps without dropping words; narrow circuits use a 480-unit minimum wrapping width to avoid a tall narrow title block.
- Metadata newlines become comment whitespace, not additional ASC commands. Long indivisible words remain intact and expand bounds rather than being truncated.

## 5. Bounding boxes

SHEET dimensions are computed from the final content span, including transformed canonical component bounds, wire endpoints, pins, flag labels/ground glyphs, reference/value windows, and metadata, with 32-unit margins rounded outward to the 16-unit grid. No physical circuit translation occurs; negative text coordinates are legal and were accepted by LTspice.

The independent evidence tool also measures installed ASY artwork and all rendered text. Its presentation bounds are font-based **estimates**, not native ink/crop guarantees. Native zoom-to-fit screenshots provide the separate visual check. Estimated occupied presentation area decreased **18.8%–50.2%** across the seven circuits; actual circuit-only bounding boxes remain exactly unchanged.

| Circuit | Original SHEET | Final SHEET |
| --- | --- | --- |
| Common Emitter | 1200 × 800 | 736 × 720 |
| RC low-pass | 1200 × 800 | 512 × 368 |
| RC high-pass | 1200 × 800 | 528 × 368 |
| Voltage divider | 1200 × 800 | 512 × 544 |
| Bridge rectifier | 1200 × 800 | 752 × 512 |
| NE555 | 1200 × 800 | 752 × 576 |
| LED blinker | 1200 × 800 | 720 × 608 |

## 6. Before/after metrics

Each WIRE record is one segment. Length is summed Manhattan length. Bends are orthogonal degree-two turns; junctions are degree-three-or-higher conductive graph vertices, not unrelated crossings. Labels below mean electrical FLAG records, including ground. All full bounds, label categories, file hashes, pin maps, and per-net measurements are in `metrics/polish_report.json`.

| Circuit | Components | Wires/segments | Length | Bends | Junctions | Flags | File bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Common Emitter | 6 → 6 | 23 → 14 | 1536 → 1536 | 4 → 4 | 2 → 2 | 3 → 3 | 1128 → 1257 |
| RC low-pass | 2 → 2 | 6 → 6 | 224 → 224 | 3 → 3 | 0 → 0 | 3 → 3 | 485 → 609 |
| RC high-pass | 2 → 2 | 6 → 6 | 224 → 224 | 3 → 3 | 0 → 0 | 3 → 3 | 486 → 614 |
| Voltage divider | 2 → 2 | 5 → 4 | 160 → 160 | 0 → 0 | 0 → 0 | 3 → 3 | 461 → 562 |
| Bridge rectifier | 5 → 5 | 18 → 15 | 1648 → 1648 | 4 → 4 | 2 → 2 | 4 → 4 | 1002 → 1213 |
| NE555 | 4 → 4 | 29 → 25 | 2400 → 2400 | 15 → 15 | 3 → 3 | 2 → 2 | 1096 → 1216 |
| LED blinker | 5 → 5 | 18 → 13 | 1472 → 1472 | 6 → 6 | 1 → 1 | 2 → 2 | 904 → 1077 |
| **Total** | **26 → 26** | **105 → 83** | **7664 → 7664** | **35 → 35** | **8 → 8** | **20 → 20** | **5562 → 6548** |

**File size increased by 986 bytes (17.7%)** because explicit readable WINDOW overrides and wrapped metadata add presentation records. This is not a file-compression result. The improvement is fewer redundant wire records and clearer, smaller occupied presentation without changing physical routes.

## 7. Regression circuits and electrical results

| Circuit | Canonical pins | Electrical groups, including unwired pins | LTspice |
| --- | ---: | ---: | --- |
| Common Emitter Amplifier | 13 | 6 | PASS |
| RC low-pass | 4 | 3 | PASS |
| RC high-pass | 4 | 3 | PASS |
| Voltage divider fixture | 4 | 3 | PASS |
| Bridge rectifier fixture | 10 | 4 | PASS |
| NE555 astable | 14 | 7 | PASS |
| LED blinker | 11 | 6 | PASS |

Installed executable: `C:/Users/ASUS/AppData/Local/Programs/ADI/LTspice/LTspice.exe`. Installed ASY geometry and SpiceOrder are checked independently of exporter serialization. Real `-netlist` output is compared to source-derived canonical pin partitions and to the baseline partition, allowing harmless internal node-token renaming.

All seven exported successfully, opened as native schematics, and netlisted successfully. Export diagnostics were empty. Real LTspice junction microfixtures and the known-shorted negative baseline remain in the backend suite and pass their expected positive/negative checks.

## 8. Backend, frontend and build results

- Baseline backend: **196 tests; 20 failing subcase assertions**, matching the recorded Phase 7.5 checkpoint. Failures were old symbol/header hashes, old index-based pin placement, an all-R0 expectation, and a mandatory-crossing expectation for now-planar Common Emitter.
- Final backend: **259 tests in 32.274 seconds; zero failures, errors, or skips**. Includes exporter, cleanup, routing, geometry, connectivity, presentation, metrics, and installed-LTspice integration tests.
- Frontend: **28 passed; zero failures/skips**.
- Independent `npm --prefix frontend run typecheck`: passed before build and again after restoring the build-generated import.
- `npm --prefix frontend run build`: passed; Next.js production pages generated successfully. Build itself skips TypeScript errors by existing configuration, so the separate typecheck is the relevant type gate.
- `git diff --check`: passed.

An intermediate integrated run reported six assertions: five order-sensitive frozen test comparisons and one new label-corridor scoring regression. Those were fixed and the full suite rerun. A metrics run exposed the inspection renderer's VCenter case-normalization bug; it was fixed with a regression test and all seven measurements rerun successfully. Earlier logs are retained rather than represented as passing runs.

## 9. Visual regression results

All seven final **native LTspice screenshots were directly inspected**; the screenshots are not inferred from text parsing or a clean test log. Native capture uses isolated, unsaved schematic copies, discovers the application's zoom-to-fit command, and never targets existing user windows. Capture hashes confirm the copies remain unchanged.

- **Common Emitter: PASS.** R1/R2 bias remains compact; R3 collector route, Q1, C1 and C2/VOUT remain clean. C2 reference/value are horizontal. VCC and ground are visible, the two intentional junctions are unobscured, and no large loop was introduced.
- **RC low-pass: PASS.** Compact chain, separated horizontal resistor annotations, readable VIN/VOUT and ground; title/description do not overlap components.
- **RC high-pass: PASS.** C1 annotations sit below the horizontal symbol, R1 text is clear, VIN/VOUT and ground remain visible.
- **Voltage divider: PASS.** Compact vertical chain with readable references/values; native vertical VIN/VOUT labels retained; metadata no longer forms a narrow five-line column.
- **Bridge rectifier: PASS.** Four diode identities/values are legible, all branches and intentional junctions remain visible, AC+/AC−/OUT+ and ground remain distinct.
- **NE555: PASS within unchanged routing scope.** IC name, pin labels, resistor/capacitor values, VCC, ground and junctions are readable. Existing bottom and side routes are retained, not optimized further or redrawn.
- **LED blinker: PASS.** LED and transistor identities are clear, VCC/ground readable, annotations do not obscure the route. The visibly unwired transistor emitter is intentional source content, not an export open.

Seven baseline and seven final native screenshots are retained. Fourteen supplementary installed-symbol inspection renders include all metadata; these are explicitly not native screenshots and have approximate font/flag layout. `visual_results.json` records final screenshot hashes and circuit-specific findings. No functional-simulation or universal typography guarantee is implied.

## 10. Remaining limitations and compatibility

1. **Voltage source:** no canonical backend voltage/current symbol pin definition existed at baseline. Unknown completely unwired components retain the existing warning-only fallback; wired unsupported components fail. A real voltage-source feature requires a separate library/pin-system extension. Ground is supported through validated explicit net labels, not a separate ground component type.
2. **Source circuit limitations remain:** Common Emitter has no emitter DC return; LED Q1.E is floating; NE555 output/reset/control pins are unwired. They remain separate singleton groups where appropriate. No topology was invented to make these examples simulate.
3. **Typography:** presentation bounds use conservative dependency-free estimates; native LTspice font choice/orientation can differ. All seven actual schematics were checked on this host. Long indivisible metadata tokens can legitimately expand the sheet.
4. **Routing:** no search, layout, power distribution, or pin mapping redesign occurred. Only proven serialization redundancy is removed. Partially overlapping segments and arbitrary large-circuit typography are not claimed globally optimal.
5. **Reproducibility boundary:** identical source order is deterministic across tested processes; semantically equivalent reordered component arrays may retain the existing different placement. M90/M270 geometry retains the canonical resolver's documented native-verification caveat and is not emitted by these seven circuits.
6. **Optional tooling:** full backend tests need no Pillow. Inspection rendering/measurement uses system Python with installed Pillow and LTspice symbols; these optional tools are not new production dependencies.

## Reproduction

From the repository root:

```bash
backend/venv/Scripts/python.exe -B -m unittest discover -s backend/tests -v
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build

python -B backend/tools/export_routing_report.py \
  --output backend/tests/artifacts/phase_8/after --require-ltspice \
  --circuit backend/circuits/common_emitter_amplifier.json \
  --circuit backend/circuits/rc_low_pass_filter.json \
  --circuit backend/circuits/rc_high_pass_filter.json \
  --circuit backend/tests/fixtures/routing/voltage_divider.json \
  --circuit backend/tests/fixtures/routing/bridge_rectifier.json \
  --circuit backend/circuits/555_astable_multivibrator.json \
  --circuit backend/circuits/led_blinker.json

python -B backend/tools/export_polish_report.py \
  --output backend/tests/artifacts/phase_8/metrics
python -B backend/tools/capture_ltspice.py \
  backend/tests/artifacts/phase_8/after/*.asc \
  --artifacts backend/tests/artifacts/phase_8/after_native
```

The `before/` ASC files are captured baseline evidence, not regenerated using the new exporter. The metrics report refuses changed physical symbols, pins, flags, per-net wire coverage, or electrical partitions. No force push is required or intended.

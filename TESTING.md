# SpiceCraft validation commands

Run from the repository root with Python, Node, installed frontend dependencies, and the backend environment described in SETUP.md. Verification never installs packages or contacts a live AI service.

## Commands

| Command | Coverage |
| --- | --- |
| `npm test` | All backend unittest modules, then all frontend Node tests |
| `npm run test:backend` | Backend tests using the existing Windows/Linux backend virtualenv when available |
| `npm run test:frontend` | Frontend compiler, connectivity, adapters, and compiler bridge |
| `npm run test:regression` | All seven compiler-derived circuit exports, semantic/electrical/routing checks, available LTspice |
| `npm run test:export` | Same source circuit export validation without claiming compiler-chain coverage |
| `npm run verify` | Backend + frontend + independent TypeScript + production build + post-build typecheck + circuit regression |
| `npm run verify:full` | Full verification plus required LTspice, installed-symbol renders, and native screenshot comparisons |

Each regression/verification command creates a fresh timestamped artifact directory. Commands can be repeated without deleting evidence. Supply a new or empty output directory for a controlled location:

```bash
npm run verify:full -- --output backend/tests/artifacts/my-verification --samples 5
npm run test:regression -- --require-ltspice --output backend/tests/artifacts/my-regression
```

Equivalent direct commands:

```bash
python -B backend/tools/verify_project.py --require-ltspice --visual
python -B backend/tools/run_regression.py --require-ltspice --samples 5
python -B backend/tools/run_regression.py --export-only
```

`--samples` accepts 1–20 backend generation measurements per circuit. `verify_project.py --timeout` sets a per-command timeout (default 900 seconds). Full verification runs independent gates sequentially and records their stdout/stderr and exit codes even when a previous gate fails. Existing build-generated `next-env.d.ts` and TypeScript cache changes are restored only when recognized; unexpected changes are preserved and reported as conflicts.

## Test categories

- **Unit:** grid/pin transforms, canonical topology, parser grammar, duplicates, metric thresholds, orchestration failures/timeouts.
- **Integration:** compiler normalization/identity mapping, source nets, layout/resolver/router agreement, exact serialized geometry.
- **End-to-end:** existing fixture → actual frontend `CircuitCompiler` → test-only compiled-connection adapter → backend connectivity/layout/routing/cleanup/export → independent serialized pin partition → real LTspice.
- **Export:** Version/SHEET, scoped symbol attributes/windows, references/values, wires/flags/text, unknown/malformed records, duplicate detection.
- **Electrical:** all required and optional singleton pins, source/golden partitions, names and memberships of electrical labels, shorts/opens.
- **Routing:** geometry, exact grid, endpoints, body/corridor collisions, intended crossing declarations, determinism and review thresholds.
- **Visual:** installed-symbol renderings, native LTspice opening/capture, old/current comparison images, explicit image-bound inspection verdicts.

The compiler bridge is a **test adapter**, not a change to the application architecture. Production still exports persisted circuit JSON. The adapter exports actual compiler components/connections; it does not substitute original fixture wires. Frontend symbol coordinates and LTspice ASY offsets intentionally differ; logical pin IDs must agree, while each coordinate system is validated independently.

## Reports and status meanings

- `verification_report.json` / `.md`: backend/frontend/TypeScript/build and circuit evidence summary.
- `regression/regression_report.json` / `.md`: per-circuit components, pin metadata/coordinates, net membership, topology, metrics, timings, diagnostics, ASC and real netlist hashes.
- `regression/*_comparison.png`: Phase 8 native baseline above current native schematic.
- `regression/visual_review.json`: explicit reviewed verdicts tied to current ASC/native screenshot hashes.
- `logs/`: full stdout/stderr for every executed command.

**PASS** means the requested evidence passed. **FAIL** exits nonzero. **REVIEW** exits zero but explicitly means incomplete or unreviewed evidence; it is never called a validation pass. Automation consumers requiring all evidence should assert `overall == "PASS"` in the JSON.

Without LTspice, portable checks still run and LTspice is REVIEW. `--require-ltspice` turns unavailable native validation into FAIL. Without native screenshot inspection, Visual remains REVIEW, including on `verify:full`; the command cannot honestly automate visual acceptance. Rendering requires optional Pillow in the selected Python; native capture additionally requires Windows and installed LTspice. Missing requested rendering/capture dependencies produce explicit failure/review evidence, not a fake pass.

## Visual review

Inspect each comparison for spacing, wire clarity, labels, title, junctions, VCC/ground, cropping, loops, and empty space. The tool does not apply an image-difference threshold. Record evidence for every circuit with `tools.run_regression.accept_visual_review(output, verdicts, reviewer)`, where `output` is the regression directory and `verdicts` maps each circuit key to `{"status": "PASS"|"REVIEW"|"FAIL", "evidence": "specific observation"}`. This function rejects missing cases and stale ASC/native image hashes.

After that explicit review, `tools.verify_project.refresh_report(verification_output)` refreshes the aggregate report without rerunning builds or clearing previous command failures. Do not manufacture PASS verdicts from matching image hashes alone.

## Reference and support boundaries

See `backend/tests/fixtures/regression/README.md` for controlled golden-update policy. No ASC byte equality is required against historical snapshots; repeatability for the same current input is still tested.

Six backend kinds are covered: resistor, capacitor, diode, LED, BC547/NPN, and NE555. Ground/VCC/custom labels are validated electrical labels. Frontend-only inductor, PNP, voltage/current sources, and ground components are explicitly rejected by the shared-export adapter and listed as unsupported backend coverage. No simulation, live AI-provider integration, or large-fixture scalability is claimed.

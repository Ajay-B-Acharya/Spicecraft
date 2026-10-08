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

Six backend kinds are covered: resistor, capacitor, diode, LED, BC547/NPN, and NE555. Ground/VCC/custom labels are validated electrical labels. Frontend-only inductor, PNP, voltage/current sources, and ground components are explicitly rejected by the shared-export adapter and listed as unsupported backend coverage. No simulation or live AI-provider integration is claimed. The Phase 10 corpus and profiling commands below measure larger inputs separately; see the current report rather than extrapolating from the seven Phase 9 fixtures.

## Phase 10 corpus collection and scalability

Use the installed backend environment. From the repository root on Windows:

```powershell
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py collect-circuits --output backend/tests/corpus/runs/collection
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py test-corpus --catalog backend/tests/corpus/runs/collection/catalog.json --output backend/tests/corpus/runs/test --samples 2 --timeout 30
```

The equivalent module entry point from `backend/` is `python -B -m tools.circuit_corpus collect-circuits` or `python -B -m tools.circuit_corpus test-corpus --catalog <catalog.json>`. On other systems, substitute the existing backend Python environment executable. Output folders must be new or empty; omit `--output` for fresh timestamped directories. Preserve the printed path for the next command.

Collection inventories source files first, snapshots extractable JSON/Python/TypeScript/documentation inputs without modifying originals, and keeps provenance and unresolved expressions. Identical content is deduplicated, not counted as multiple designs. Existing generated artifacts are inventoried as evidence rather than inflated into original circuits. Conservative static snapshots do not imply that a test branch actually executes; dynamic/non-JSON cases remain explicit unresolved evidence.

By default, collection also adds twelve explicitly marked, deterministic scale cases: connected series-resistor networks and cascaded RC filters at exactly 10, 25, 50, 100, 250, and 500 components. These are repeated meaningful structures, not random designs. `--no-synthetic` collects repository inputs only.

Testing uses the actual TypeScript compiler and bridge, backend connectivity, layout, exact pin resolution, routing, optimization, export, and independent serialized electrical checks. Each circuit runs in isolated compiler/backend processes with a deadline. Reports preserve stage success and diagnostics; compiled, routed, serialized, and fully validated are separate counts. Negative cases and legitimate routing failures are retained. Non-PASS circuit outcomes produce a nonzero command exit rather than being silently skipped. This is different from unit tests, where an expected rejection can pass its assertion.

Each collection contains `inventory.json`, `catalog.json`, `inputs/<circuit-id>.json`, extraction evidence, and `indexes/`. The category index files are `small.json`, `medium.json`, `large.json`, `extreme.json`, `regression.json`, `unsupported.json`, `malformed.json`, and `failing.json`, plus `all.json`. These overlapping views reference the original collected snapshots rather than copying or rewriting topology. Execution adds `validated_catalog.json`, `corpus_report.json` / `.txt`, and per-case/per-sample compiler, backend, diagnostics, and successful ASC evidence. Unknown or untested component eligibility stays explicitly unknown; supported/unsupported lists describe observed compiler/shared-export kind eligibility, not complete backend model or circuit validity.

Native LTspice and browser rendering are separate gates; corpus success alone does not prove either. Repeated samples check deterministic artifacts only when implementation hashes remain stable. Do not edit pipeline code while producing final benchmark evidence.

## Profiling and memory retention

```powershell
backend/venv/Scripts/python.exe -B backend/tools/profile_pipeline.py backend/circuits/common_emitter_amplifier.json --output backend/tests/artifacts/profile-run --samples 5 --memory-samples 20
```

This records uninstrumented per-stage backend timings, a separate cumulative-call profile, repeated ASC hashes, source immutability, and a warmed single-process `tracemalloc` retention series after garbage collection. Tracing changes runtime and measures Python allocation, not whole-process resident memory. The corpus records child-process resident-memory observations separately. Neither measurement is a long-duration leak proof.

## Browser recovery checks

Start the existing webpack development server, then run the installed Chrome checks:

```powershell
npm --prefix frontend run dev -- --hostname 127.0.0.1
# In a second terminal:
node frontend/tools/verify-production-browser.cjs backend/tests/artifacts/browser-run
```

The script uses Node's native WebSocket support and the Chrome DevTools Protocol, with no browser-package installation. Set `CHROME_PATH` to an installed Chrome executable and `BROWSER_TEST_URL` if the app is not at `http://127.0.0.1:3000`. It uses the existing public Firebase API configuration from `frontend/.env.local`, seeds an isolated temporary browser session, blocks external network requests, and mocks API transport. No live authentication credential is submitted and no backend circuit file is edited.

Checks include click-through library navigation, structured export errors, unsupported/timeout/gateway/offline states, editing, failed-save draft retention, retry, download, saved-value reload, mobile overflow, unsupported source rejection, missing/empty/library-error states, shared project/source pages, and surrounding routes. Runtime exceptions, including hydration mismatches, fail the test. Reports and screenshots remain in the output directory. This verifies browser behavior against controlled responses; live Firebase and persisted HTTP round trips remain separate deployment checks.

See [Phase 10 results](PHASE_10_PRODUCTION_REPORT.md), [production operation](docs/PRODUCTION.md), and [component development](docs/ADDING_COMPONENTS.md).

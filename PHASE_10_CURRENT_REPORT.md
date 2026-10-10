# Phase 10 — current hardening, corpus, and scalability report

Date: **2026-10-10**. This report supersedes the measurements in [the historical Phase 10 report](PHASE_10_PRODUCTION_REPORT.md). Earlier runs remain preserved as evidence.

## 1. Acceptance and scope

**Incremental hardening and the verification work are delivered; unrestricted production acceptance remains REVIEW.** The existing compiler, layout, Manhattan router, optimizer, and exporter were retained. No valid source topology was redesigned to make a test pass, unsupported symbols were not substituted, and no simulation, commit, or push was introduced.

| Evidence | Current result |
| --- | --- |
| Backend unit/integration suite | **451 tests passed** |
| Frontend suite | **83 tests passed**, zero failures |
| Independent TypeScript checks and production build | **PASS** |
| Seven compiler-derived regression circuits | Electrical, routing, export, real LTspice, and explicitly inspected native visuals **PASS** |
| Browser recovery/navigation checks | **33 PASS**, zero recorded runtime errors; real Chrome with mocked authentication/API transport |
| Complete collected corpus, two attempts each | **245 cases / 490 attempts**: 93 PASS, 106 INVALID, 32 UNSUPPORTED, 14 FAIL |
| Repeat outcomes | 244 cases OBSERVED stable; **one DIFFERENT** because of a routing deadline |
| Largest routed successful input | **250 components**, connected resistor chain, both corpus samples passed |
| Largest successful input regardless of routing | **500 components**, unwired case; not a connected-capacity claim |
| Largest attempted input | **501 components** |
| Supplemental native scale checks | All **seven** scale cases with at least one successful corpus sample passed native pin-partition comparison |

The corpus command correctly exited **1**. Expected malformed/unsupported definitions remain negative circuit outcomes even though unit tests asserting their rejection pass. The 14 FAIL cases also remain visible. Neither a passing build nor a successful 500-component unwired export means every medium/large topology is reliable.

## 2. Architecture audit and changes

The [pipeline audit](docs/PIPELINE_AUDIT.md) covers input normalization, compiler, component library, pin resolution, net building, validation, frontend and backend layout, routing, optimization, export, debug tools, API/frontend integration, and tests. The [production guide](docs/PRODUCTION.md) includes the architecture diagram, responsibility map, support table, budgets, transaction boundaries, logging, and deployment constraints. [Adding components](docs/ADDING_COMPONENTS.md) documents the component-definition, pin, compiler, backend-symbol, layout/routing, export, test, and documentation steps.

**Actual production boundary:** the browser compiler prepares editor data; the Python export endpoint exports persisted JSON independently. The actual TypeScript compiler is chained into backend execution by the **test-only** `frontend/tools/compile-regression.cjs` adapter. Compiler-derived corpus results therefore exercise both implementations, but do not prove that production calls the frontend compiler on each export. The React Flow editor also uses its display adapter rather than the reusable frontend LayoutEngine; display coordinates and stock LTspice coordinates are intentionally distinct.

### Changes in this continuation

- **Measured presentation optimization:** `export_presentation.py` filters obstacles once per symbol against an envelope containing every possible label-window candidate. Candidate enumeration, scoring, obstacle ordering, and tie-breaking are unchanged. Tests compare exhaustive and filtered results for long/Unicode labels, geometry, all supported rotations/mirrors, and five bundled exports. No mutable topology cache or alternate router was added.
- **Independent diagnostic validation:** recoverable source warnings keep their severity. `NET_SHORT` and `WIRE_CROSSES_PIN` always remain fatal. Historical failures caused by promoting duplicate-wire and label warnings to errors were corrected without weakening conductive-contact validation; tests include a complete duplicate-wire export and independent audit.
- **Corpus evidence safety:** malformed credible definitions and unresolved expressions remain recorded; frontend configuration aliases are not misidentified as circuits. Missing, corrupt, nonfinite, or escaping inputs become explicit case failures. Case IDs reject traversal, reserved Windows names, and case-insensitive duplicates. Compiled evidence with invalid paths, identities, or digests cannot supply support claims. Worker timeouts must be finite and positive, and sample counts are bounded. Invocation records capture only recognized pipeline-limit environment variables.
- **Frontend/API recovery:** API diagnostics preserve backend location fields; body-read aborts/timeouts are distinguished from HTTP errors. Extension metadata survives circuit load/save. HTTP 200 downloads with the wrong media type, empty content, or malformed ASC header are rejected. Object URLs are cleaned up on anchor-creation failure. Project/source hooks guard stale responses after navigation, unmount, and sign-out, and rows update only after successful mutations.
- **Documentation and reproducibility:** current benchmarks, corpus provenance, stage counts, implementation fingerprints, browser checks, and limitations are documented rather than replacing earlier evidence with a favorable subset.

### Existing safeguards retained and audited

Input validation bounds nesting, collections, strings, finite numbers, identifiers, coordinates, and component/pin support. Ambiguous electrical identity and multiline ASC attribute injection are rejected. The exporter validates connectivity and geometry before serialization, then checks serialized components, symbols, attributes, wires, flags, and pins against the validated representation. Fatal generation returns no successful ASC attachment. File-backed saves use atomic replacement; this does not provide concurrent-edit conflict detection.

Structured pipeline logs retain circuit identity, component/pin/net/wire counts, stage/total times, iteration counts, and diagnostic counts without dumping full input JSON. Production export does not run discovery, rendering, native screenshots, or debug-file generation.

Only six backend kinds have verified export definitions: resistor, capacitor, diode, LED, BC547/NPN, and NE555. Frontend library availability is broader and does not imply export support. Connected label aliases use the existing canonical label; label-only groups without component pins warn and are not drawn. **Component-pin connectivity is preserved, not every secondary source-label spelling.**

## 3. Resource limits and remaining complexity

`PipelineLimits` defaults are 500 components; 4,000 pins and nets each; 10,000 input wires; 20,000 routing segments; 1,000,000 layout iterations; 2,000,000 routing and optimization iterations each; 2 MB input and 4 MB export; depth 32; 100,000 input items; strings of 4,096 characters; and coordinate magnitude 10,000,000. Body/layout/routing/optimization deadlines are 10/5/10/5 seconds; total backend deadline is 30 seconds. Overrides use `SPICECRAFT_<FIELD>`. The current corpus recorded **no overrides**.

The existing router additionally bounds grid vertices, search states, order attempts, and envelope retries. Production checks are cooperative, not hard process isolation. Corpus compiler/backend workers are separately isolated with a 30-second process deadline. Raising a budget is not a capacity improvement.

Size classes use actual input counts: small 1–20, medium 21–100, large 101–500, extreme 501+. Missing/invalid/empty counts remain unknown. The current corpus contains 216 small, 6 medium, 6 large, 1 extreme, and 16 unknown cases.

The audit still identifies repeated geometry validation, pairwise segment/obstacle scans, route-search work, and large presentation/layout extent. The label filter reduces observed work but leaves superlinear worst cases. The 250-resistor case spends substantially more time routing and validating routes than laying out components. No general linear-time or arbitrary-topology scalability claim is made.

## 4. Inventory before synthetic generation

Collection inventories repository source/evidence paths before adding scale fixtures. It preserves content snapshots and source hashes, deduplicates identical inputs while retaining every origin, and never turns generated ASC/net/image evidence into new circuit definitions.

Current collection: [catalog](backend/tests/corpus/runs/current-collection-final/catalog.json) and [inventory](backend/tests/corpus/runs/current-collection-final/inventory.json).

| Inventory observation | Count |
| --- | ---: |
| Repository-derived unique cases | **233** |
| Added deterministic scale cases | **12** |
| Total cases | **245** |
| Provenance entries, including synthetic entries | 494 |
| JSON / Python static / frontend static / frontend runtime / synthetic origins | 7 / 226 / 59 / 190 / 12 |
| Source files supplying collected cases | 22 |
| Inventory entries: source / generated evidence / corpus tooling / excluded directory | 287 / 657 / 6 / 20 |
| Extraction records: complete / partial | 227 / 43 |
| Unresolved expressions | **111** |
| Frontend runtime capture errors | **6** |
| Candidate sources lacking an extractor | 0 |

These counts describe the catalog's inventory entries, not 970 distinct circuit designs. Static extraction is conservative: dynamic expressions, non-JSON fences, accessors/cycles, and unexecuted branches cannot all become runnable JSON. Some Python exception/finalization branches remain unresolved. **Every collected case was attempted; exhaustive execution of every possible repository definition is NOT VERIFIED.** Original negative definitions and unresolved evidence were preserved rather than silently repaired or discarded.

Case-level support results are 112 supported, 32 unsupported, and 101 invalid-or-unknown. These describe compiler/shared-export kind eligibility, not routing success, backend model validity, or simulation support. Per-component support evidence and unknown counts are in `validated_catalog.json`.

### Corpus structure

```text
current-collection-final/
  invocation.json, inventory.json, catalog.json
  inputs/<circuit-id>.json
  indexes/{all,small,medium,large,extreme,regression,unsupported,malformed,failing}.json
  extraction/capture evidence
current-execution/
  invocation.json, implementation.json
  validated_catalog.json, corpus_report.json, corpus_report.txt
  scalability_summary.json
  indexes/
  <circuit-id>/sample-1/, sample-2/
    compiler/backend results, diagnostics, compiled.json, successful ASC evidence
```

Indexes are overlapping views referencing preserved definitions, not copies with modified topology. Counts of absent pins/nets remain unknown until actual compilation. The implementation fingerprint is `64012f11da6471eec0a9e3a12e9d69fc7f0fad62162229e8b2c6e14ed3c8c4d0`; every recorded case reports stable implementation, and a final comparison found no changed fingerprinted source file.

## 5. Full pipeline results

Evidence: [corpus report](backend/tests/corpus/runs/current-execution/corpus_report.json), [invocation and stage totals](backend/tests/corpus/runs/current-execution/invocation.json), and [scale summary](backend/tests/corpus/runs/current-execution/scalability_summary.json).

Every one of 245 cases was submitted to the real compiler/backend pipeline twice. Invalid or unsupported inputs stop at the appropriate boundary; later stages are explicitly blocked or not run, not fabricated as successful executions. The run took approximately 1,103 seconds.

| Stage | Cases attempted | Cases passing both samples | Successful attempts | Other attempt statuses |
| --- | ---: | ---: | ---: | --- |
| Compile | 245 | 134 | 268 | 222 FAIL |
| Shared export bridge | 245 | 115 | 230 | 260 FAIL, including compile-blocked |
| Connectivity | 115 | 109 | 218 | 12 FAIL; 260 NOT_RUN |
| Route | 83 | 72 | 145 | 8 FAIL; 13 TIMEOUT; 42 NOT_REQUIRED; 282 NOT_RUN |
| Export | 109 | 93 | 187 | 31 FAIL; 272 NOT_RUN |
| Independent serialized validation | 94 | 93 | 187 | 303 NOT_RUN |

Across attempts: 187 PASS, 212 INVALID, 64 UNSUPPORTED, 27 FAIL. First actual failure stage totals are compile 222, bridge 38, connectivity 12, route 21, and export 10. These sum to 303 unsuccessful attempts; propagated downstream failures must not be counted as additional independent failures.

Failures include ambiguous source identities, conflicting component definitions, duplicate compiled IDs, instance/net-label collisions, missing/unexpected/unresolved pins, unsupported shared-export kinds, blocked pin escapes, no safe route, and pipeline timeouts. Complete codes and per-case provenance remain in the report. The 14 FAIL cases comprise eight repository-derived cases and six synthetic scale cases; some repository failures are deliberate definition conflicts, not unhandled crashes.

Repeated samples use different backend `PYTHONHASHSEED` values. **244 cases had observed stable results, including stable rejection.** The 25-component filter (`circuit-011da72b4d779fc1e919`) passed once and timed out once, so its outcome is DIFFERENT and its case remains FAIL. A later successful native rerun does not change that original result. Stable rejection is not successful export, and two matching runs are not a proof of determinism for all inputs.

## 6. Scale families, timings, and memory

The twelve synthetic inputs are explicitly tagged: resistor chains from VIN through series resistors to ground, and repeated series-resistor/shunt-capacitor filter sections with shared ground and VOUT. The odd 25-component filter includes a load resistor. Sizes are exactly 10, 25, 50, 100, 250, and 500; no random components, disconnected count inflation, or simulation sources were inserted.

Environment: Windows 11, Python 3.13.7, installed frontend dependencies and backend virtual environment, development-machine scheduling. Times below are observed medians in milliseconds over two attempts; stages not reached are shown as —. Compiler times are compiler-reported work, excluding process startup. Export here means the backend presentation/serialization stage, **not** inclusive export wall time. Whole-process times and all backend stages are retained in the JSON.

| Family | Components | Attempts | Compiler ms | Routing ms | Export ms | Peak backend MiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Filter | 10 | PASS/PASS | 12.905 | 901.284 | 17.260 | 32.727 |
| Resistor | 10 | PASS/PASS | 15.183 | 19.606 | 17.663 | 31.559 |
| Filter | 25 | PASS/FAIL | 19.442 | 9054.111 | 94.686* | 34.371 |
| Resistor | 25 | PASS/PASS | 14.169 | 68.916 | 38.340 | 31.887 |
| Filter | 50 | FAIL/FAIL | 15.007 | 10004.816 | — | 35.852 |
| Resistor | 50 | PASS/PASS | 15.441 | 268.189 | 79.520 | 32.750 |
| Filter | 100 | FAIL/FAIL | 21.119 | 10003.870 | — | 44.871 |
| Resistor | 100 | PASS/PASS | 17.764 | 879.503 | 153.519 | 33.988 |
| Filter | 250 | FAIL/FAIL | 19.864 | 10007.648 | — | 49.879 |
| Resistor | 250 | PASS/PASS | 23.985 | 6001.809 | 543.651 | 37.445 |
| Filter | 500 | FAIL/FAIL | 32.854 | 10009.979 | — | 54.848 |
| Resistor | 500 | FAIL/FAIL | 38.606 | 10004.350 | — | 38.867 |

*Only the successful 25-filter attempt reached export, so 94.686 ms is one observed value, not two successful measurements. Larger filters and the 500-resistor chain hit the default 10-second routing deadline. Small deadline overshoot reflects cooperative checkpoints, not successful completion.

Selected 250-resistor stage medians: input validation 11.738 ms; net building 3.651; validation 1.523; layout 3.513; pin resolution 1.708; routing 6001.809; routing validation 2501.704; optimization 369.499; final validation 1973.310; export 543.651; post-export validation 26.940. At 100 resistors, routing validation was 341.385 ms and final validation 282.186 ms. Independent medians and inclusive timers must not be summed as an exact median request latency.

Maximum observed corpus process memory was **54.848 MiB backend** and **103.188 MiB compiler**. These are 20 ms samples of Windows child-tree working sets, including virtualenv launcher descendants and excluding the harness. Short-lived peaks can be missed; this is not a memory cap or leak proof.

### Native geometry and visual scale evidence

[Supplemental report](backend/tests/artifacts/phase_10/current-scale-native-final/report.json): each selected source was regenerated, its ASC hash matched a successful corpus sample, and real LTspice netlisting preserved the expected component-pin partition, including singleton pins. No simulation was run.

| Family / size | Segments | Bends | Junctions | Crossings | Geometry bounding box | Native partition |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Resistor 10 | 43 | 32 | 0 | 0 | [64,112,864,768] | PASS |
| Filter 10 | 56 | 35 | 7 | 3 | [32,80,912,784] | PASS |
| Filter 25 | 146 | 86 | 23 | 29 | [16,80,912,1824] | PASS |
| Resistor 25 | 110 | 84 | 0 | 0 | [64,112,864,1792] | PASS |
| Resistor 50 | 223 | 172 | 0 | 0 | [64,112,864,3328] | PASS |
| Resistor 100 | 449 | 348 | 0 | 0 | [64,112,864,6400] | PASS |
| Resistor 250 | 1123 | 872 | 0 | 0 | [64,112,864,16128] | PASS |

Crossings are not automatically electrical junctions; the native comparisons independently checked pin membership. The installed-symbol 100/250 images were opened, and top/middle/bottom 250-component crops were inspected. Names/values and terminal wires are separated in the inspected regions, but the 250 rendering is **1800 × 30102 pixels**, with excessive vertical extent and repeated routing loops. **Compact large-layout visual quality remains REVIEW.** These supplemental images are inspection-renderer output, not native GUI screenshots; [inspection notes](backend/tests/artifacts/phase_10/current-scale-native-final/visual_review.md) describe the precise scope.

The initial supplemental run in `current-scale-native/` failed while serializing the renderer's dataclass result. Its artifacts remain preserved. The metadata serialization was repaired and all seven cases reran successfully into the fresh `current-scale-native-final/` directory.

## 7. Measured optimization and retention

[Alternating benchmark](backend/tests/artifacts/phase_10/current-presentation-100/benchmark.json), three samples per mode, full backend export of the same 100-resistor source:

| Median | Exhaustive candidate obstacle scan | Conservative obstacle filter |
| --- | ---: | ---: |
| Presentation/serialization | 3102.720 ms | 233.331 ms |
| Complete backend export | 5117.403 ms | 2125.890 ms |

All six outputs had the same ASC hash; the source was unchanged. This is about 92.5% less presentation-stage time in this observation, not a universal speedup. Other stages varied with scheduling. The comparison runs actual full backend exports, not a standalone overlap microbenchmark, but does not include the TypeScript compiler or native startup.

For the six-component common-emitter source, [before](backend/tests/artifacts/phase_10/current-profile-before/profile_report.json) and [after](backend/tests/artifacts/phase_10/current-profile-after/profile_report.json) each contain **five uninstrumented timing samples**. Median total decreased from 25.021 ms to 16.837 ms; after min/max were 16.655/20.895 ms. Source and ASC hashes remained unchanged. These separate runs also include ordinary host variation.

A separate warmed-process retention pass took **20 samples** with outputs discarded and garbage collection after each export. After-change retained traced Python bytes rose from 34,345 to 45,336 (maximum 45,385), with peak traced allocation 169,239 bytes. The earlier pass ended at 38,454 retained bytes. This short series shows retained allocation growth and does **not** establish leak freedom or a memory reduction. Tracemalloc excludes native/RSS memory and changes runtime; its samples are not the uninstrumented timing samples.

## 8. Verification evidence and browser behavior

- [Full project verification](backend/tests/artifacts/phase_10/current-verification/verification_report.md): 451 backend tests, 83 frontend tests, independent TypeScript checks before/after the production build, build, electrical/routing/export, and native LTspice passed. The aggregate remains **REVIEW** because this invocation did not request visual evidence; its exit 0 is not mislabeled as an all-evidence PASS.
- [Separate current native/visual regression](backend/tests/artifacts/phase_10/current-regression-visual/regression_report.md): all seven cases PASS after actual inspection of every current native screenshot and recording image-bound review verdicts. This supplies separate visual evidence rather than rewriting the nonvisual aggregate.
- [Browser report](frontend/test-artifacts/phase10-api-audit-warm/browser_report.json): 33 PASS, zero runtime errors. Checked library/editor navigation, structured routing/unsupported/timeout/offline/malformed/invalid-success export errors, failed-save draft retention and retry, download, saved-value reload, mobile error/retry and overflow, missing/empty/error states, dashboard/project/source creation/deletion failure/retry, and surrounding editor/exports/favorites/assistant routes.

Browser checks use real Chrome interactions with isolated Firebase session state and mocked API responses; they are not live Firebase or deployed-backend acceptance. Earlier failed browser runs, including a transient Next.js development manifest error, remain present. The successful evidence is specifically `phase10-api-audit-warm`, not a failed directory whose name happens to include “release” or “final”. Owned test-server processes were stopped; unrelated user servers were left alone.

The first requested render run under the backend virtual environment failed because Pillow was unavailable. That evidence remains in `current-regression/`. The separate successful visual run used existing system Python with Pillow; no dependency installation was needed.

## 9. Reproduction commands

Run from the repository root. Use fresh output directories; the paths shown for completed evidence already exist and must not be overwritten. A new collection can legitimately change provenance inventory after documentation/artifact additions. To reproduce the tested inputs exactly, use the preserved `current-collection-final/catalog.json`.

```powershell
# Inventory existing definitions first, then append the twelve marked scale fixtures.
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py collect-circuits --output backend/tests/corpus/runs/recheck-collection
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py test-corpus --catalog backend/tests/corpus/runs/current-collection-final/catalog.json --output backend/tests/corpus/runs/recheck-execution --samples 2 --timeout 30

# Full project checks; visual inspection is a separate explicit acceptance step.
python -B backend/tools/verify_project.py --output backend/tests/artifacts/phase_10/recheck-verification --require-ltspice --samples 3
python -B backend/tools/run_regression.py --output backend/tests/artifacts/phase_10/recheck-visual --samples 3 --require-ltspice --render --native

# Backend source profiling and alternating exact-output presentation comparison.
backend/venv/Scripts/python.exe -B backend/tools/profile_pipeline.py backend/circuits/common_emitter_amplifier.json --output backend/tests/artifacts/phase_10/recheck-profile --samples 5 --memory-samples 20
backend/venv/Scripts/python.exe -B backend/tools/benchmark_presentation.py backend/tests/corpus/runs/current-collection-final/inputs/circuit-bf177d289f65b1ff63fb.json --output backend/tests/artifacts/phase_10/recheck-presentation --samples 3

# Supplemental checks explicitly read the preserved current-execution evidence.
python -B backend/tests/artifacts/phase_10/verify_current_scale.py --output backend/tests/artifacts/phase_10/recheck-scale-native

# With the local app already running; see TESTING.md for URL/Chrome configuration.
node frontend/tools/verify-production-browser.cjs frontend/test-artifacts/recheck-browser
```

The equivalent corpus module entry point is `python -B -m tools.circuit_corpus` from `backend/`. `--no-synthetic` collects repository definitions only; repeated `--id` selects preserved cases for targeted reruns. [TESTING.md](TESTING.md) documents prerequisites, command semantics, native inspection acceptance, and browser setup.

## 10. Explicit remaining limitations

**VERIFIED:** observed test/build results, preserved corpus execution and rejection evidence, exact-output presentation equivalence on measured/tested cases, successful connected routing through 250 resistors, native pin partitions for seven regressions plus seven selected scale cases, and mocked-transport browser recovery.

**NOT VERIFIED or not achieved:**

1. Universal medium/large routing reliability: the 25-filter mixed outcome and larger timeouts directly prevent this claim. Reliable 500-component connected export is not achieved.
2. Compact large-circuit layout quality: tall four-column drawings remain a usability limitation; representative scale-image inspection is not exhaustive native GUI review.
3. Native LTspice validation of every corpus case: native checks cover the explicitly listed subsets only.
4. Exhaustive dynamic repository-definition extraction: unresolved expressions/capture errors remain recorded.
5. Leak freedom, hard production CPU/RAM isolation, global concurrency bounds, and long-duration load behavior.
6. Live Firebase authentication, deployed API persistence/transport, public multi-user security, and concurrent-edit conflict handling.
7. Lossless secondary-label spelling preservation, unsupported backend component families, live AI generation, and simulation.

Further work should target the observed routing/validation bottlenecks, large-layout usability, deployment isolation/admission limits, and real-service acceptance tests. Failures must remain in the corpus while those changes are assessed; increasing limits, deleting fixtures, or relabeling REVIEW as PASS would not satisfy the remaining acceptance conditions.

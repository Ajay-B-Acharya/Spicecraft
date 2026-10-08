# Phase 10 — production hardening and circuit corpus report

## Acceptance statement

The existing compiler, layout, routing, and export engines have been hardened incrementally. Valid fixture topology was not redesigned, unsupported symbols are not substituted, and failed transactions do not return successful ASC attachments. No simulation requirement, commit, or push was introduced.

**Safety hardening and regression verification are delivered; unrestricted production acceptance remains REVIEW.** The complete regression/build/browser checks passed, and every collected case was attempted. The corpus deliberately retains invalid/unsupported inputs and also exposes real routing deadlines, support-contract differences, and large-layout limitations. Arbitrary small/medium-circuit reliability, reliable connected 250/500-component completion, and public multi-user hosting are not established.

This report distinguishes **VERIFIED**, **PASS**, controlled **FAIL**, **INVALID**, **UNSUPPORTED**, **REVIEW**, and **NOT VERIFIED**. A 500-component count limit is not a routing-capacity guarantee. No simulation functionality, commit, or push was introduced.

## 1. Complete architecture audit

The [pipeline audit](docs/PIPELINE_AUDIT.md) covers every requested subsystem: AI-style input, normalization, compiler, component library, pin resolver, net builder, validation, both layout paths, Manhattan routing, optimization, exporter, debug tools, frontend/backend integration, and tests. It records repeated calculations, representation duplication, superlinear scans, memory growth, blocking work, recursion risks, failure propagation, and missing deployment boundaries.

The [production guide](docs/PRODUCTION.md) contains the architecture diagram, actual production/test boundaries, supported components, error behavior, configuration, and export transaction. The production Python endpoint exports persisted JSON; the real frontend compiler is chained into Python by the **test-only** bridge. A source-only backend benchmark is not a compiler benchmark.

Core responsibilities remain separated. Existing component-specific small-layout preferences remain localized in layout/presentation; no router or exporter was replaced. Frontend display geometry and canonical native geometry remain separate and are checked through canonical pin identities and electrical partitions.

## 2. Performance baselines and measured optimization

Environment: Windows 11, Python 3.13.7, installed Node/frontend dependencies and backend virtual environment. Runs occurred on a development machine with other verification processes; these are observations, not dedicated-host latency guarantees. Process startup, TypeScript transpilation, native LTspice startup, visual capture, tracing, and profiling are separate costs.

### Six-component common-emitter source export

Evidence: `backend/tests/artifacts/phase_10/profile-initial/`, `profile-overlap/`, and `profile-release/`.

| Observation | Initial run | After overlap fast rejection | Current-code run |
| --- | ---: | ---: | ---: |
| Uninstrumented backend median, five samples | 47.574 ms | 28.384 ms | 30.643 ms |
| Minimum / maximum | 42.973 / 52.732 ms | 26.374 / 30.779 ms | 26.137 / 35.005 ms |
| Identical ASC across samples | Yes | Yes | Yes |
| Source unchanged | Yes | Yes | Yes |

The initial cProfile pass recorded 78,720 rectangle-overlap calls, taking 149 ms cumulatively under profiling; label-window selection accounted for 199 ms of a 245 ms profiled export. After disjoint-rectangle fast rejection, the overlap calls took 14 ms and label selection 59 ms of a 101 ms profiled export. Profiling overhead is substantial: those are **not** uninstrumented application times.

Only the measured rectangle rejection was changed; candidate order, exact overlap score, routing, and topology were preserved. A deterministic 10,000-pair equivalence test protects the score. No general speedup or new asymptotic complexity is claimed. The independently run before/after measurements also contain normal system load and other safety-check differences.

Current source-export stage medians (five samples, six components / 13 pins / six nets / 14 final wires):

| Stage | Median ms |
| --- | ---: |
| Input validation | 0.867 |
| Net building | 0.324 |
| Electrical validation | 0.101 |
| Layout | 0.215 |
| Exact pin resolution | 0.096 |
| Routing | 7.630 |
| Routing validation | 1.341 |
| Optimization | 0.753 |
| Final geometry validation | 0.698 |
| Presentation / serialization | 15.662 |
| Post-export validation | 0.671 |
| Total backend pipeline | 30.643 |

Independent stage medians need not sum to the median total. The TypeScript compiler is not included in this source-export measurement; the complete corpus separately measures its actual execution and process startup. Presentation remains the largest stage for this small fixture; routing and later presentation/validation dominate different scale cases.

## 3. Circuit corpus collection

The collector inventories repository source and evidence paths first. It extracts JSON, conservative Python/TypeScript expressions, actual frontend compiler-boundary inputs, and parseable documentation examples. Content-identical inputs are deduplicated while all provenance is retained. Generated ASC/net/image artifacts are evidence, not additional source designs. Original circuit definitions are not rewritten.

Collection deliberately records unresolved dynamic expressions, accessor/cyclic/non-JSON cases, and capture errors. Therefore **all inventoried paths** does not mean **every possible execution of every test expression was extracted**. Unknown pin/net/support counts remain explicitly unknown until compilation, rather than guessed.

Only after inventory, twelve tagged scale cases are added: connected resistor chains and cascaded RC sections at exactly 10, 25, 50, 100, 250, and 500 components. These are deterministic repeated meaningful structures, not random count inflation or replicas of disconnected complete designs.

Size classes use actual counts: small 1–20; medium 21–100; large 101–500; extreme 501+. Empty/malformed collections are not counted as valid small circuits.

### Commands created

From the repository root:

```powershell
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py collect-circuits --output backend/tests/corpus/runs/collection
backend/venv/Scripts/python.exe -B backend/tools/circuit_corpus.py test-corpus --catalog backend/tests/corpus/runs/collection/catalog.json --output backend/tests/corpus/runs/test --samples 2 --timeout 30
backend/venv/Scripts/python.exe -B backend/tools/profile_pipeline.py backend/circuits/common_emitter_amplifier.json --output backend/tests/artifacts/profile-run --samples 5 --memory-samples 20
```

Equivalent module commands work from `backend/`: `python -B -m tools.circuit_corpus collect-circuits` and `python -B -m tools.circuit_corpus test-corpus --catalog <catalog.json>`. Output directories must be fresh. `--no-synthetic` restricts collection to repository-derived inputs; repeated `--id` selects preserved cases for explicit reruns.

The corpus records compiler, bridge, connectivity, route, export, and serialized-validation outcomes separately. Backend pipeline telemetry additionally records normalization/input validation, net building, electrical validation, layout, exact pin resolution, routing, optimization, presentation/serialization, and final serialized validation. Export wall time includes routing and must not be added to route wall time.

A case is PASS only after every required stage succeeds. UNSUPPORTED and INVALID are rejections, not successful exports. FAIL covers routing, deadlines, resource exhaustion, internal contract failures, and independent validation failures. Non-PASS corpus outcomes produce a nonzero command exit; this is expected for a corpus containing deliberate negative tests and differs from a passing unit test that asserts rejection.

### Final corpus census and results

- **233 distinct repository inputs discovered and collected**, from **482 source occurrences in 22 source files**. Twelve explicitly tagged repeated-structure scale cases bring the collected total to **245** and the provenance total to **494**.
- Final size classification: **216 small, six medium, six large, one extreme, and 16 empty/invalid/unknown-count inputs**. Counts use actual decoded input arrays, not benchmark target names. Malformed entries retain their observed array count without being considered valid circuits.
- **84 unresolved expressions and six non-JSON/accessor/cyclic runtime capture failures** remain recorded. They are not fabricated runnable circuits or claimed successes. The source inventory is comprehensive within the documented scan rules; exhaustive dynamic-expression extraction is NOT VERIFIED.
- The complete acceptance run executed **490 attempts** (245 cases twice). Four cases crossed an earlier implementation change; **eight additional final-code attempts** replaced only those four cases in the consolidated view. All **498 attempts** remain available in their original evidence directories.
- Consolidated results: **85 PASS, 22 FAIL, 106 INVALID, 32 UNSUPPORTED**. Both samples agree for each consolidated case; all 245 have stable per-case implementation evidence. An observed repeated rejection is not deterministic ASC evidence. Successful ASC and compiler hashes are recorded separately.

| Successful stage, both samples | Cases |
| --- | ---: |
| Frontend compilation | 134 |
| Shared-export compiler bridge | 115 |
| Connectivity validation | 109 |
| Routing actually performed and passed | 71 |
| Routing legitimately not required | 21 |
| Export produced and passed its internal checks | 92 |
| Complete pipeline including independent serialized validation | 85 |

Seven exported cases fail the stricter independent validation gate; they remain FAIL rather than being counted as complete successes. Of the 85 complete passes, 64 actually required routing and 21 had no electrical nets to route.

| First unsuccessful stage, including invalid/unsupported rejections | Cases | Selected attempts |
| --- | ---: | ---: |
| Compilation | 111 | 222 |
| Compiler bridge | 19 | 38 |
| Connectivity | 6 | 12 |
| Export | 5 | 10 |
| Routing | 12 | 24 |
| Independent serialized validation | 7 | 14 |

**Largest complete case: 500 unwired resistors**, an existing repository test input, with zero nets and routing explicitly NOT_REQUIRED. Its two backend-process times were 29.12 and 20.00 seconds; it had previously timed out. This is layout/export evidence, not meaningful 500-component routing capacity. **Largest connected complete case: the 100-component resistor chain. Largest attempted input: 501 components**, rejected by the configured input boundary.

Evidence: [complete consolidated report](backend/tests/corpus/runs/phase10-final/corpus_report.md), [machine-readable attempts and diagnostics](backend/tests/corpus/runs/phase10-final/corpus_report.json), [executed catalog](backend/tests/corpus/runs/phase10-final/validated_catalog.json), and [benchmarks](backend/tests/corpus/runs/phase10-final/benchmarks.json). Original full and drift-recheck reports remain in `phase10-acceptance/` and `phase10-drift-recheck/`. `backend/tests/artifacts/phase_10/consolidate_corpus.py` reproduces the consolidation into a fresh `phase10-final/` directory; it does not rerun or infer any passes.

The final collector generated byte-identical catalogs and all nine index files in `phase10-indexed-collection-a/` and `phase10-indexed-collection-b/`, retaining exactly the same 245 input IDs/hashes as the executed collection. Earlier 247-case historical evidence and the intermediate recheck remain preserved, including cases removed from their originating source tests during development; they are not substituted for this 245-case census.

### Corpus directory structure

```text
backend/tests/corpus/
  fixture_generator.py
  capture_frontend.cjs
  runs/
    <collection>/
      inventory.json
      catalog.json
      inputs/<circuit-id>.json
      extraction/
      indexes/{all,small,medium,large,extreme,regression,unsupported,malformed,failing}.json
    <execution>/
      corpus_report.json
      corpus_report.txt
      validated_catalog.json
      indexes/
      <circuit-id>/sample-1/  # compiled input, diagnostics, logs, successful ASC
      <circuit-id>/sample-2/
    phase10-final/           # consolidated report, catalog, benchmarks, index views
```

Index views overlap and reference preserved inputs; they do not duplicate or alter topology. Per-record metadata includes IDs, names, sources, actual component/pin/net counts where observed, validation state, and attributed supported/unsupported/unknown component lists. Eligibility lists describe the actual frontend/shared-export kind boundary; full backend model acceptance remains an additional gate. Missing or ambiguous evidence stays unknown.

## 4. Circuit-size and routing scalability results

The following is the **final complete-run matrix**. All twelve scale cases compiled, built validated nets, completed layout and exact pin resolution. PASS means both complete samples passed. A routing timeout is a measured FAIL with no successful ASC, not an untested size.

| Components | Resistor compile / layout / route / export / final validation | RC filter compile / layout / route / export / final validation |
| --- | --- | --- |
| 10 | PASS / PASS / PASS / PASS / PASS | PASS / PASS / PASS / PASS / PASS |
| 25 | PASS / PASS / PASS / PASS / PASS | PASS / PASS / TIMEOUT / STOPPED / NOT RUN |
| 50 | PASS / PASS / PASS / PASS / PASS | PASS / PASS / TIMEOUT / STOPPED / NOT RUN |
| 100 | PASS / PASS / PASS / PASS / PASS | PASS / PASS / TIMEOUT / STOPPED / NOT RUN |
| 250 | PASS / PASS / TIMEOUT / STOPPED / NOT RUN | PASS / PASS / TIMEOUT / STOPPED / NOT RUN |
| 500 | PASS / PASS / TIMEOUT / STOPPED / NOT RUN | PASS / PASS / TIMEOUT / STOPPED / NOT RUN |

### Measured timing and resident memory

Medians of two attempts, milliseconds unless marked otherwise. Compiler time is the real compiler-reported duration; backend process time includes startup, routing, serialization, and independent validation. Routing and presentation are included inside backend time and must not be added to it. A dash means the stage was never reached.

| Family / components | Compiler | Layout | Routing | Presentation / serialization | Backend process seconds | Peak backend MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Resistor / 10 | 29.42 | 2.56 | 48.08 | 100.19 | 0.89 | 31.13 |
| RC / 10 | 33.96 | 2.83 | 2,479.19 | 135.62 | 3.36 | 32.16 |
| Resistor / 25 | 31.67 | 2.90 | 220.36 | 592.89 | 1.80 | 31.41 |
| RC / 25 | 30.28 | 3.55 | 10,009.52 timeout | — | 10.71 | 33.26 |
| Resistor / 50 | 36.08 | 3.70 | 797.41 | 2,251.96 | 4.77 | 32.14 |
| RC / 50 | 38.59 | 4.05 | 10,010.07 timeout | — | 10.69 | 35.30 |
| Resistor / 100 | 46.47 | 7.95 | 3,335.00 | 10,302.24 | 19.30 | 33.62 |
| RC / 100 | 49.04 | 4.66 | 10,011.18 timeout | — | 10.72 | 41.42 |
| Resistor / 250 | 70.61 | 8.08 | 10,013.62 timeout | — | 10.92 | 34.73 |
| RC / 250 | 72.49 | 6.55 | 10,012.98 timeout | — | 10.82 | 44.26 |
| Resistor / 500 | 102.42 | 12.40 | 10,066.87 timeout | — | 11.23 | 37.23 |
| RC / 500 | 118.22 | 15.83 | 10,016.78 timeout | — | 10.97 | 48.02 |

The principal bottleneck for the successful 100-resistor chain is **presentation/serialization**, followed by routing and repeated geometry validation: net building 5.59 ms, pin resolution 3.21 ms, initial validation 2.59 ms, optimization 195.38 ms, routing validation 1,573.43 ms, final geometry validation 1,202.89 ms, and serialized validation 31.89 ms within the backend transaction. For RC ladders, **routing** reaches its budget first. No universal bottleneck is assumed.

### Wire growth and geometry

| Successful scale case | Pins / nets | Initial route segments | Final wires | Bends | Junctions | Declared unsplit crossings |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Resistor / 10 | 20 / 11 | 47 | 43 | 32 | 0 | 0 |
| RC / 10 | 20 / 7 | 61 | 56 | 35 | 7 | 3 |
| Resistor / 25 | 50 / 26 | 121 | 110 | 84 | 0 | 0 |
| Resistor / 50 | 100 / 51 | 247 | 223 | 172 | 0 | 0 |
| Resistor / 100 | 200 / 101 | 497 | 449 | 348 | 0 | 0 |

Bend/junction counts use the existing geometry measurement code on the validated serialized wires/flags; unsplit interior crossings remain unjoined. See `phase10-final/routing_geometry_metrics.json`. The 10-component filter needed 20 A* searches, 12,231 expanded states, 15,872 collision checks and an allowed crossing fallback; its internal failed candidate attempts are not missing final connections. Successful resistor cases used low-bend candidates without A*. No explosive final wire growth was observed for those successful topologies; timed-out cases have no validated final wire count.

Historical variability is retained: the 25-component filter completed in an earlier run but timed out in later runs; the 100-resistor chain completed earlier and in this final run but hit the total budget in an intermediate recheck. Those facts prevent a general latency or reliable-capacity guarantee. No connected 250/500-component complete export is claimed. The fixed-column large layout and native usability limits are discussed below.

## 5. Memory observations

Current warmed single-process profiling performed twenty exports, discarded the ASC, and called garbage collection after each. Traced retained Python allocation rose from 30,606 bytes to approximately 46,364 bytes and settled around 45–46 KB over the final samples. Peak traced allocation was 170,502 bytes. Source input was unchanged and repeated ASC hashes matched.

This short run found no obvious continued linear accumulation for that six-component fixture. It is **not** a leak proof, whole-process measurement, concurrent-load soak, or measurement of native allocations.

Corpus processes separately sample resident memory every 20 ms. Across the consolidated corpus, the maximum observed backend child-tree working set was **48.02 MiB** and compiler process memory was **94.88 MiB**. Windows reports observed child-tree working set, including virtual-environment launcher descendants; Linux uses available process high-water data. Sampling can miss short-lived peaks and excludes the harness. A memory-test failure exposed the invalid assumption that zero-filled allocated pages must be resident; the probe now fills the allocation and holds it across multiple sampling intervals instead of weakening the expected bound.

## 6. Timeouts and resource limits

`backend/app/services/production.py` centralizes `PipelineLimits`, request-local `Execution`, stage timers, cumulative repeated-stage budgets, counters, and structured `PipelineError`. Environment overrides use `SPICECRAFT_` plus the uppercase field name and must be finite and positive.

Defaults: 500 components; 4,000 pins/nets; 10,000 input wires; 20,000 routing segments; 1,000,000 layout and 2,000,000 routing/optimization iterations; 2 MB input and 4 MB export; depth 32; 100,000 input items; 4,096-character strings; coordinate magnitude 10,000,000. Body/layout/routing/optimization budgets are 10/5/10/5 seconds; total backend budget is 30 seconds.

The existing router retains 120,000 compressed-grid vertices, 80,000 expanded states, four order attempts, and three envelope margins. Frontend representation limits are centralized separately, including 500 components, 4,000 pins, 2,000 wires, and bounded depth/strings/coordinates.

These are cooperative in-process checks, not hard operating-system preemption. Corpus workers additionally have process deadlines and terminate timed-out children. A diagnostic timeout does not authorize a partial successful ASC. Hosted deployment still needs bounded concurrency, worker/process isolation, CPU/memory controls, and admission/rate limiting.

## 7. Error-handling architecture and export transaction

`ExportDiagnostic` and `AscExportError` preserve code, severity, stage, circuit, and known component/pin/net. Unknown pins/components, invalid nets, unsupported models, missing geometry, route failure, budgets, and serialized drift are fatal. Optional presentation metadata can use existing defaults; ambiguous electrical identities cannot be guessed or silently renamed.

The transaction validates input and connectivity, lays out and resolves exact pins, routes, optimizes/cleans, validates electrical geometry again, serializes, then validates records. Production only sends the final ASC after all fatal checks pass. Diagnostic APIs may retain failed geometry for inspection but return empty text on failure.

The post-export verifier compares expected component/reference/symbol/value/anchor/orientation data, canonical pins including unwired pins, exact wire multisets, and electrical flags. Independent corpus/native checks remain an additional gate rather than being bypassed to make a case pass.

## 8. Invalid-input test results

Coverage includes absent/empty components, invalid types/values, nonfinite numbers, invalid or partial coordinates, oversized/nested/cyclic inputs, accessors, sparse arrays, duplicate identities/references, missing components/pins, unknown pin IDs, contradictory endpoints, malformed/self/duplicate connections, conflicting labels, malformed request JSON, invalid UTF-8/surrogates, ASC record injection, and corrupted serialized records.

Tests assert that fatal electrical/input errors do not reach placement/routing or persistence, corrupted serialization returns no successful ASC, and a failed atomic save preserves the original file. Final aggregate counts and individual corpus rejection counts are recorded in the verification sections below; a negative case is never counted as successfully exported.

## 9. Unsupported-component results

Verified backend kinds are resistor, capacitor, diode, LED, BC547/NPN, and NE555. Frontend library availability is broader. LM358, incompatible IC/transistor models, PNP, inductors, voltage/current sources, and other unverified native kinds must reject rather than become another symbol or disappear.

Explicit `ic/LM358`, `transistor/PNP`, `bjt/BC557`, and incompatible `ic/resistor` boundaries are tested before routing. Omitted legacy IC/transistor model values retain existing library defaults for compatibility; that does not permit replacing an explicitly requested unsupported model. Unknown frontend types and frontend-only shared-export kinds are catalogued as UNSUPPORTED rather than generic invalid JSON.

## 10. Production logging and diagnostics

Structured JSON start/completion/failure events contain circuit ID, count-based classification, available component/pin/net/wire/export counts, per-stage milliseconds, total time, iteration counters, and warning/error counts. INFO/WARNING/ERROR reflect diagnostic severity; DEBUG exposes detailed diagnostics explicitly. Normal events omit raw circuit objects.

Normal export disables verbose debugging, visual analysis, native subprocesses, and intermediate image/file dumps while retaining electrical validation. Request-local state and caches do not retain mutable topology across requests.

## 11. Frontend changes and browser evidence

Structured backend diagnostics, HTTP status failures, malformed/non-JSON responses, network failures, cancellation, and deadlines remain understandable. Failed saves preserve drafts and enable explicit retry; stale fetch/save responses and duplicate submits are guarded. Export is disabled for dirty/saving state. Download failures clean up anchors, object URLs, and stale timers.

A real browser run against final application code passed **26 checks** at desktop 1440×1000 and mobile 390×844. It clicked, edited R1 to 22k, failed and retried save/export, downloaded an ASC response, navigated away and reloaded saved state, and exercised unsupported/missing/empty/network/timeout/error states. `/search`, circuit detail, dashboard/projects, and surrounding `/editor`, `/exports`, `/favorites`, and `/assistant` routes were visited. Desktop/mobile screenshots were inspected; no horizontal mobile overflow or recorded runtime exception occurred. A shared top-bar hydration mismatch found earlier was fixed by deferring initial authenticated-user display to the existing effect.

Evidence: `backend/tests/artifacts/phase_10/browser-release/browser_report.json` and adjacent screenshots. The browser uses isolated authentication and mocked API transport; it does not prove live Firebase, native LTspice, or real persisted HTTP round trips. Draft recovery is in-memory and does not survive a full reload of unsaved work.

## 12. Backend API changes

Circuit routes return structured validation/unsupported/routing responses (422), ID mismatch (400), missing circuit (404), body deadline (408), pipeline timeout (504), input resource rejection (413), later resource exhaustion (503), and sanitized unexpected failure (500). Detailed diagnostics retain known electrical context. Attachment filenames are sanitized and length-bounded.

Streamed request bytes, encoding, nesting, and body deadlines are checked before framework JSON decoding. Circuit updates validate before repository write. Repository replacement is atomic using a temporary file, flush/fsync, and replace; no circuit ID becomes an arbitrary path. Existing circuit routes remain unauthenticated and file-backed updates have no optimistic conflict detection.

## 13. Security and input-safety review

Untrusted circuit strings are never executed as shell commands. Input traversal/identities/values/coordinates/metadata and ASC record separators are checked, hidden accessors are not invoked, cycles and oversized structures reject, and normal API exceptions exclude stack traces/internal paths. Independent native test commands use argument arrays, not circuit-provided shell fragments.

**NOT VERIFIED / not implemented as hosted-service controls:** authenticated circuit ownership, public deployment authorization, rate limiting, concurrent export admission, process isolation, persistence conflict resolution, production TLS/origin policy, external-provider safety, and long-duration adversarial load. Reverse-proxy and operating-system resource limits are still required. These are explicit deployment blockers, not capabilities implied by this phase.

## 14. Documentation updates

- [README.md](README.md): Phase 10 entry points and evidence links.
- [TESTING.md](TESTING.md): regression, full verification, corpus, profiling, browser, status semantics, and reproducibility.
- [docs/PRODUCTION.md](docs/PRODUCTION.md): architecture diagram, support, limits, transaction, errors, logging/debug mode, and deployment limitations.
- [docs/PIPELINE_AUDIT.md](docs/PIPELINE_AUDIT.md): complete subsystem/complexity/responsibility audit.
- [docs/ADDING_COMPONENTS.md](docs/ADDING_COMPONENTS.md): all nine component-extension steps, exact symbol/pin/rotation/mapping requirements, fixture/regression/native/browser validation, and prohibition on unrelated router changes.
- This report: measured evidence, acceptance scope, limitations, and follow-up priorities.

## 15. Regression results

The first complete release pass verified frontend tests, TypeScript, build, all seven compiler-derived circuit exports, and native LTspice. Its only backend failure was the resident-memory test assumption described above. All seven native comparisons were then explicitly inspected and accepted with image-bound evidence. The earlier failed aggregate report remains preserved.

The fresh complete verification **PASS** is recorded in `backend/tests/artifacts/phase_10/final-verification/verification_report.md`: **409 backend tests**, **77 frontend tests**, independent TypeScript checks before and after the production build, the production build itself, and all seven compiler-derived electrical/routing/native-LTspice regression cases passed. All seven current native comparison images were inspected, with image-bound visual verdicts applied to that fresh report. The full command completed in 143.50 seconds.

A subsequent complete backend-only run passed **412 tests in 93.199 seconds**, including final cooperative-routing timeout accounting (`latest-backend/backend.log`). After integrating catalog/index metadata and correcting empty/missing count logging, the final complete backend suite **PASS: 433 tests in 39.515 seconds, exit 0**. Evidence: `backend/tests/artifacts/phase_10/latest-backend/final-direct.log`. The added catalog tests exercise actual compiler evidence, exact size boundaries, deterministic reference indexes, preserved IDs/hashes, and unknown/unsupported cases. An earlier PowerShell-redirected invocation reported command exit 1 despite the test log saying all 433 passed; its log is preserved separately, and the direct invocation confirmed exit 0. Historical Phase 9 reports are not substituted for current tests. Whitespace validation with `git diff --check` passed; Windows line-ending notices are not test failures.

## 16. LTspice validation

Seven existing circuits were compiled through the real frontend bridge, exported, independently compared electrically, and netlisted by installed LTspice. All six shared component kinds and 60 fixture pins are covered. Source/golden partitions, references, symbols, values, labels, exact pin geometry, routing, and serialized structure passed in the release verification.

Native visual comparisons for the 555, common-emitter amplifier, LED blinker, both RC filters, voltage divider, and bridge rectifier were inspected. Labels, symbol separation, junctions, routing, title/description, ground/supply flags, and cropping were checked. Existing optional unconnected pins remain unconnected; visual/export validity is not a claim that those examples are fully simulated functional devices.

A previously successful **100-component resistor chain** was also netlisted by installed LTspice: all expected pin groups matched, with no shorts, opens, missing pins, or unexpected pins. Both final complete-run ASC samples have the identical SHA-256 `f2b829de018d7802054a74f9ca71c64db8199ee338c59f33e8660c9372ac82f2` as that native-inspected ASC. Evidence is in `backend/tests/artifacts/phase_10/native-100/native_report.json`. Installed-symbol rendering reported 100 symbols, 200 pins, 449 wires, and zero junctions; native opening/capture succeeded.

Its visual usability remains **REVIEW**: the render is 1800×12300 pixels, local top/middle/bottom sections have separated bodies and readable labels at zoom, but the native fit-to-window view is a tall narrow strip with unreadable labels and excessive side whitespace. This is an observed limitation, not an uninspected visual PASS. See adjacent `visual_review.json` and screenshots.

Corpus PASS alone does not establish native LTspice validity for every collected case. Successful native completion for 250/500 components remains **NOT VERIFIED**.

## 17. Known limitations and acceptance boundaries

- Routability and time depend strongly on topology; 500 is a rejection limit, not a guaranteed usable circuit size.
- Small-fixture timing does not establish latency for arbitrary AI output. Medium filter sections can approach/exceed the routing deadline.
- The fixed-column fallback can be tall/sparse; compact, visually usable arbitrary large layouts are NOT VERIFIED.
- Linear collision scans, candidate materialization, pairwise geometry audits, and label-window scoring remain measurable bottlenecks.
- Bounded greedy route failure does not prove that a different layout could not route successfully.
- Compiler/backend support, identity/value normalization, and conservative diagnostic policies are explicit boundaries; independent corpus failures remain preserved. In particular, the independent Phase 9 routing validator promotes source warnings such as `DUPLICATE_WIRE`, `CONFLICTING_NET_LABELS`, and `LABEL_ONLY_NET` to errors. Those cases can have an ASC from the production exporter and still fail the complete corpus gate; they are not counted as complete successes. This policy mismatch is distinct from a demonstrated short or missing component.
- Identical-input determinism is tested; permutation-invariant net numbering is not promised. Implementation changes invalidate comparisons rather than being hidden.
- Full extraction of dynamic/non-JSON test expressions, live AI/Firebase flows, long-duration memory behavior, public-service security, and multi-user write conflicts remain NOT VERIFIED.

### Final production checklist

| Requirement | Evidence / status |
| --- | --- |
| Responsibilities remain separated | VERIFIED by subsystem audit; existing engines retained |
| Extensible component definitions and centralized pins | VERIFIED for the existing library and rotation/mirror tests; unsupported kinds reject |
| Validated nets and transactional export | VERIFIED by unit, integration, serialized, and native regression tests |
| Deterministic layout/routing/export | VERIFIED for repeated successful fixtures; timeout outcomes remain workload-sensitive |
| Malformed and unsupported input fails safely | VERIFIED rejection and no-successful-attachment tests |
| Bounded operations and resource limits | VERIFIED cooperative checks and isolated corpus process deadlines; hosted hard isolation NOT VERIFIED |
| Small and medium performance | MEASURED selected circuits, not guaranteed for arbitrary topology |
| Large circuits | ATTEMPTED through 500; successful completion and usable layout are topology-dependent |
| Memory | MEASURED short retention series and sampled child-process memory; long-duration/concurrent soak NOT VERIFIED |
| Frontend failure/retry handling | VERIFIED in real desktop/mobile Chrome with controlled transport |
| Backend structured errors and safe input | VERIFIED tests; public-service authentication/admission remains a deployment limitation |
| Phase 9 regression and existing LTspice exports | PASS, including seven native visual reviews |
| Simulation | Outside scope; no simulation requirement introduced |

The tests establish the documented safety and regression behavior. They do not establish that every valid small/medium AI circuit will route, that arbitrary large layouts are usable, or that the application is ready for public multi-user hosting.

## 18. Recommended future improvements

1. Use failing corpus topologies to improve existing deterministic placement and route ordering without changing nets; retain all negative fixtures.
2. Profile label-window candidate scans and collision/audit hotspots at the successful 50/100-component sizes before considering selective spatial indexing. Keep the simple small-circuit path.
3. Add deployed-service authorization, bounded worker admission, isolated resource enforcement, and versioned persistence before public hosting.
4. Extend component support only through real symbol definitions, canonical pins/rotations, cross-language fixtures, and native LTspice verification.
5. Add production-browser responsiveness measurements, concurrent-load/long-duration memory tests, and native/visual checks for the largest newly successful topologies.
6. Improve structured frontend compiler diagnostics and conservative dynamic-corpus extraction while preserving unknown/unresolved evidence instead of inventing circuits.

# Phase 10 pipeline architecture audit

This audit covers the existing implementation, including its remaining limitations. It does not propose replacing the circuit engine, layout engine, router, or exporter. Current verification results belong in [the production report](../PHASE_10_PRODUCTION_REPORT.md). The architecture diagram and operating limits are in [PRODUCTION.md](PRODUCTION.md).

## Actual execution paths

1. AI-style JSON is normalized by the frontend `CircuitBuilder`, instantiated through `ComponentLibrary`, resolved through `PinResolver`, grouped by `NetBuilder`, and checked by `CircuitValidator` under `CircuitCompiler`.
2. The active React Flow editor uses `circuitFlowAdapter.ts`. It does **not** invoke the reusable frontend `LayoutEngine`. That engine is separately tested and retains its existing analyzer, placement, optimization, and orientation responsibilities.
3. The API persists source JSON. Backend export independently validates that source, builds canonical connectivity, places verified symbols, resolves native pins, routes, optimizes, validates, serializes, and validates serialized records.
4. The regression/corpus bridge is test-only. It sends actual TypeScript compiler components/connections to Python and compares electrical partitions. Source-only Python export is not evidence that the frontend compiler ran.
5. Real LTspice netlisting and screenshot capture are independent verification tools, not production export dependencies. Simulation is outside this phase.

## Audit by subsystem

| Subsystem | Findings and incremental changes | Remaining cost or boundary |
| --- | --- | --- |
| AI input / normalization | Explicit limits precede traversal; reject accessors, cycles, nonfinite numbers, malformed coordinates, oversized sparse arrays, conflicting identities/endpoints, and unknown types. API source is checked before display normalization. | No live AI-provider generation is verified. JavaScript and Python limits protect different representations and are not identical. |
| Circuit compiler | Continues orchestrating existing builder/resolver/net/validator stages. Fatal diagnostics prevent accepted bridge output. Canonicalization no longer relies on inherited alias properties. | Compiler errors are primarily strings; some test-adapter diagnostics consequently have less component/pin context than backend diagnostics. |
| Component library | Central definitions own symbols, pins, local geometry, rotations, and mappings. Instance construction clones caller geometry. Every frontend definition has rotation/mirror tests. Explicit incompatible generic IC/transistor models reject rather than select another family. | Eleven frontend definitions do not mean eleven native export kinds. The backend supports six. Legacy omitted IC/transistor models retain established library defaults. |
| Pin resolver | Exact backend positions come from canonical stock-symbol geometry. Unwired pins also reserve escape corridors and participate in serialized pin checks. Finite coordinate and orientation boundaries reject invalid geometry. | Frontend display coordinates intentionally differ from native ASY coordinates. Four-direction UI handles do not express every arbitrary-angle pin direction. |
| Net builder | Iterative disjoint-set avoids recursive find chains in the frontend. Endpoint keys avoid collisions. Backend indexes group wire membership instead of repeatedly rebuilding it. Membership derives only from explicit connectivity. | Encounter order can influence net numbering. Identical-input determinism does not imply permutation-invariant output. |
| Electrical validation | Checks identities, canonical/reciprocal membership, missing pins/components, malformed/self/duplicate connections, source partitions, geometry contacts, and serialized partitions. Fatal errors stop the transaction. | Validation is conservative schematic/connectivity checking, not complete electrical-rule checking, device-model verification, or simulation. |
| Frontend layout | Corrected signed supply labels, B/C/E identifiers, grid units, hint priorities, preserved user positions, finite geometry, collision bounds, and post-transform pin refresh. Removed unused group detection from orchestration. | Some grouping/signal-flow helpers remain unused. Large React Flow rendering is unit-tested, not a browser performance guarantee. |
| Backend layout | Retains deterministic grid placement and existing small-circuit topology-aware hints; adds execution checkpoints. Canonical pin offsets determine anchors. Source nets remain read-only. | Fixed four-column fallback can be tall and sparse. Existing BC547/rectifier presentation preferences are localized here; this is not a fully generic large-schematic placer. |
| Manhattan router | Retains low-bend candidates, compressed visibility-grid A*, net trees, deterministic order retries, and verified unsplit-X fallback. Adds deadline/iteration/segment checks and malformed-option diagnostics. | Candidate generation, obstacle scans, tree attachments, and audits can be superlinear. A bounded greedy failure is not proof that no possible layout/route exists. |
| Routing optimizer / cleanup | Geometry-only subdivision, collinear cleanup, and junction protection remain intact. Segment and iteration checks bound intermediate work. No electrical partition is inferred or repaired. | Pairwise subdivision/contact work can be quadratic in segment count; success is topology-dependent. |
| Export presentation | Profiling identified label-window overlap scoring as the largest cost on the six-component amplifier. Disjoint rectangle comparisons now return zero early; a 10,000-pair equivalence test protects the exact score. Candidate loops check the execution deadline. | The candidate/obstacle scan remains superlinear. This is a measured local optimization, not a spatial-index rewrite or a general complexity improvement. |
| LTspice exporter | Remains the transaction orchestrator and serializer. Failure yields no successful ASC. Record validation compares symbols, references, values, anchors/orientations, flags, wire multisets, and all canonical pins. | Serialization and its safety verifier retain bounded duplicate representations. Normal exports do not launch native LTspice; that gate is tested separately. |
| Debug utilities | Normal export disables detailed diagnostics and intermediate images/files. ASCII layout diagnostics are bounded. Native verifier imports are lazy. | Debug/corpus/profile modes intentionally retain extra evidence and impose overhead; their memory/time is not normal export cost. |
| Frontend integration | Structured errors survive API parsing. Requests have deadlines; aborted callers and network/non-JSON failures remain understandable. Failed saves preserve drafts; stale responses and duplicate submissions are guarded; failed downloads clean up browser resources. | Drafts are in memory, not durable across reloads. No server-version conflict resolution or streaming response-byte cap. |
| Backend integration | Synchronous FastAPI routes run CPU work off the event loop in its worker pool. Streamed request bytes/depth/encoding/time are checked before schema decoding. Circuit errors have structured statuses; unexpected failures are sanitized. Atomic replace protects existing files on save failure. | CPU workers still consume shared resources. No global export admission control, circuit-route authorization, optimistic write locking, or process-level isolation is added. |
| Tests and corpus | Existing Phase 9 fixtures stay unchanged. Collection inventories sources before adding explicitly tagged meaningful repeated structures. Stage results, provenance, unresolved extraction, negative cases, implementation hashes, and failures are retained. | Static extraction is conservative, not execution of arbitrary code. Dynamic/non-JSON expressions cannot all become standalone JSON cases. Native/browser acceptance is separate from corpus PASS. |

## Complexity and repeated work

Let C be components, P pins, S wire segments, X and Y compressed search lanes, G candidate attachment points, and K expanded search states.

- Component/pin instantiation and basic traversal scale with input size, subject to configured limits.
- Disjoint-set net construction avoids a recursion-depth dependency. Sorting for deterministic output adds ordinary sorting costs.
- Router collision predicates scan obstacles, reserved pin corridors, and occupied segments: approximately O(C + P + S) per candidate edge, plus declared-crossing checks.
- Low-bend path candidates grow with G(X + Y); they are materialized and sorted. Search uses at most the configured X×Y grid and K expanded states; it does not rasterize the entire coordinate range.
- A* heuristic and goal checks scan goals/tree segments. Per-search point/edge caches avoid repeating immutable checks **only while the occupied geometry is fixed**.
- Net attachment selection scans remaining pins and tree ports. Contact audits and geometry subdivision include pairwise segment comparisons.
- Label-window scoring scans candidate rectangles against wires, component bodies, flags, and previously placed text. The measured fast rejection reduces arithmetic/function calls but does not change this complexity.
- The backend repeats critical validation at source, routed, cleaned, and serialized boundaries. These checks protect different representations and were not removed as allegedly redundant work.

No new general-purpose spatial index was added without evidence that its construction/maintenance pays off. The corpus identifies the next real bottlenecks and failing sizes; bounded failure is preferable to silently changing connectivity.

## Memory, caching, recursion, and blocking

- Immutable component definitions and request-local prepared pin corridors are safe reuse candidates. The router already caches point/edge predicates inside a single search. No cross-request mutable topology cache was introduced.
- Source, compiled, canonical-net, geometry, and parsed-ASC forms coexist at validation boundaries. Input/count/segment/export limits bound these representations; they are not a proof of constant memory usage.
- Candidate arrays, A* heaps/parent maps, geometry subdivisions, and debug evidence are the main growth risks. Grid/state limits, segment limits, checkpoints, and disabled normal debug output address them incrementally.
- Untrusted nested objects are checked before recursive downstream processing. Frontend net union/find is iterative; bounded debug rendering avoids accidentally allocating huge coordinate grids.
- Backend Python computation is synchronous CPU work in worker threads. Timeouts are cooperative checkpoints, not hard preemption. A deployment must additionally bound worker concurrency, memory, CPU, and requests.
- Browser compiler/layout work is synchronous and input-bounded. Medium-circuit responsiveness should be measured in a production browser before making a no-freeze guarantee; maximum-size adapter unit timing is not that measurement.

## Failure propagation and recovery

Validation failures stop before routing; routing/optimization failures stop before successful serialization; post-serialization failures suppress the attachment. Diagnostics retain stage and known circuit/component/pin/net context. Unexpected API exceptions are logged internally while the response excludes stack traces and filesystem paths.

Optional metadata and existing defaults can be preserved safely. Ambiguous duplicate identities, unknown electrical pins, unsupported model families, and malformed connections cannot be guessed away. Retries are explicit rather than automatic, particularly because a timed-out save may already have reached persistence.

## Architecture quality conclusion

Core responsibilities remain separated, and no engine or exporter was replaced. Existing special-case small-circuit placement/presentation logic remains localized rather than being spread into routing collision rules. The frontend and backend retain separate geometry libraries and an explicit support mapping, which requires cross-language tests when adding components. Large-circuit placement quality, generic symbol support, hosted-service security, aggregate resource management, and exhaustive corpus extraction remain documented limitations rather than claimed completed capabilities.

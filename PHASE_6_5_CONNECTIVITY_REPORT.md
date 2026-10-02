# Phase 6.5 — Electrical Net and Pin Connectivity Validation

## Scope

This phase validates the existing circuit definition, canonical pin mapping, electrical nets, React Flow mappings, and exporter inputs. It introduces no wire-routing algorithm and changes no component placement, symbol definition, or pin coordinate. Phase 7 is a separate commit.

## Audit

Inspected:

- `frontend/lib/circuit/models/{Circuit,Component,Pin,Net}.ts` and `types.ts`.
- `frontend/lib/circuit/engine/{CircuitBuilder,CircuitCompiler,ComponentLibrary,PinResolver,NetBuilder,CircuitValidator,CircuitDebugger,PinSystemDebugger}.ts`.
- Component library definitions, layout net lookups, `components/circuits/circuitFlowAdapter.ts`, `nodes/UnifiedCircuitNode.tsx`, `CircuitSchematic.tsx`, and `hooks/useCircuitEditor.ts`.
- `backend/app/services/{ltspice_exporter,pin_maps,grid_system,asc_validation,exporter_debugger}.py`, circuit API/schema, and circuit repository.
- All five bundled circuit definitions and existing frontend/backend tests.
- Installed LTspice 24.1.9 symbols and netlist-only command.

## Electrical source of truth

The source circuit contains explicit endpoint pairs. Each component endpoint is normalized to an unambiguous component instance and canonical library pin. Existing union-find net construction groups only these explicit connections and named-label identities. Component coordinates, bounding boxes, proximity, alignment, React Flow positions, and wire intersections are not inputs to electrical net construction.

React Flow represents these same canonical pins with node IDs and handle IDs. The backend independently validates saved circuit definitions before the exporter resolves their pin coordinates. There is no geometry-derived logical net system.

## Root causes found

The Common Emitter source definition already has six distinct logical nets and correct Q1 C/B/E pin identities. Its suspicious horizontal rails are caused by the old exporter’s centroid/special-label hub routes overlapping other nets and passing through foreign pins, not by the source transistor aliases.

Other pipeline gaps allowed malformed or contradictory endpoint fields to be ignored, duplicate component identities to overwrite mappings, invalid net membership to escape validation, and React Flow handles to be lost. These are corrected in the existing logical pipeline rather than through layout or routing changes.

## Common Emitter: source-derived connectivity

Source: `backend/circuits/common_emitter_amplifier.json`. Components and values are unchanged: Q1 BC547, R1 100k, R2 10k, R3 1k, C1 10uF, C2 100uF.

| Electrical net | Exact canonical component pins |
| --- | --- |
| VCC | R1.1, R3.2 |
| Base/bias (anonymous source net) | R1.2, Q1.B, R2.1 |
| GND (`0` in LTspice) | R2.2, C1.2 |
| Collector (anonymous source net) | Q1.C, R3.1, C2.1 |
| Emitter (anonymous source net) | Q1.E, C1.1 |
| OUT (`VOUT` canonical label) | C2.2 |

“Base,” “Collector,” and “Emitter” describe these anonymous nets; they are not invented source labels. Generated net IDs are representation details, not electrical meaning.

The source has no DC emitter-return resistor, input source, actual supply device, or output load. It is preserved exactly; logical correspondence is not a claim that the example is a complete, simulation-ready amplifier. Other source limitations include the LED template’s floating Q1.E and the NE555 template’s unconnected RESET/output/control pins. Validation reports these rather than inventing connections.

## Real LTspice baseline verification

The unmodified export was saved in `backend/tests/artifacts/phase_6_5/common_emitter_before.asc`, alongside diagnostics and the real `.net` output. Running installed LTspice with `-netlist` produced:

```text
Q1 0 0 0 0 BC547
R1 0 0 100k
R2 0 0 10k
R3 0 0 1k
C1 0 0 10µF
C2 0 VOUT 100µF
```

Thus five intended nets collapse to ground in the old physical schematic. The fourth Q1 node is LTspice’s substrate/default node, not a new source pin. Baseline geometry validation reports 22 warnings: 17 `NET_SHORT` and five `WIRE_CROSSES_PIN`.

**Phase 6.5 validates logical topology, not the old exported wire geometry. The existing unsafe `.asc` must not be treated as electrically valid. Phase 7 must remove the physical shorts and prove the resulting partition with the real netlister.**

## Verification status

Initial baseline: 51 backend and three frontend tests passed; independent TypeScript checking passed. A successful Next.js build alone is insufficient because the existing configuration ignores TypeScript build errors.

Verified result: **112 backend tests and 28 frontend tests passed**. Independent TypeScript checking and the production build passed. The backend suite includes all 51 previous tests, 47 source/produced-net/API tests, and 14 independent netlist-verification tests. All five bundled Phase 6 `.asc` outputs remained byte-identical during this phase; the preserved unsafe baseline is intentionally tested as a negative export.

### Files created

- `backend/app/services/connectivity.py`: extracted shared ordered union-find, canonical endpoint validation, source-group snapshots, tracing, and produced-net comparison.
- `backend/tests/test_connectivity.py`: 47 source/produced-net/API regressions.
- `backend/tests/test_ltspice_netlist.py`: 14 parser/invocation/partition/real-LTspice regressions.
- `backend/tools/verify_ltspice.py`: independent real-netlist partition verifier.
- `backend/tools/render_asc.py`: inspection renderer loading actual installed ASY primitives; this is not routing or export production code.
- `frontend/tests/connectivity.test.cjs`: 25 logical and visual-adapter regressions.
- This report and the baseline ASC, real netlist, diagnostics, expected nets, and comparison JSON in `backend/tests/artifacts/phase_6_5/`.

### Files modified

- Backend: `app/services/ltspice_exporter.py`, `exporter_debugger.py`, and `app/routers/circuits.py`. The exporter consumes shared validated groups; debug tracing uses the same model; invalid saves/exports return HTTP 422 before serialization/storage.
- Frontend engine: `CircuitBuilder.ts`, `CircuitValidator.ts`, `NetBuilder.ts`, and `PinSystemDebugger.ts`. Canonical handles, contradictory fields, deterministic build-local IDs, reciprocal net IDs, source-partition equivalence, and edge diagnostics are checked.
- Frontend models/types: `models/Circuit.ts`, `models/Pin.ts`, and `types.ts` carry explicit connections and optional-pin metadata.
- `layout/ComponentGrouping.ts` and `LayoutAnalyzer.ts` only change net lookups from display names to stable IDs; placement algorithms are unchanged.
- `components/circuits/circuitFlowAdapter.ts` and `CircuitSchematic.tsx` return/show diagnostics rather than hide invalid topology.
- `lib/circuitService.ts` no longer invents label endpoints for missing wire fields. `package.json` adds test and independent typecheck commands.

### Validation policy and limitations

Repeated references to one pin in legitimate multi-branch source edges are normal; duplicate whole edges warn and do not duplicate net membership. Explicit supply/ground conflicts and contradictory endpoint representations block. Other explicitly joined label names warn rather than rewriting the source. Mega-net size diagnostics are opt-in because a large valid power net is not evidence of a topology error. Unconnected defined pins remain separate; expected source pins dropped from produced nets are blocking floating-pin errors. Empty drafts may be represented with a warning, not invented connectivity.

The frontend reports the incomplete Common Emitter DC return and floating pins in the other bundled examples. Backend source validation preserves incomplete but explicit circuit definitions; its unconnected-pin query exposes those pins for routing obstacle reservation. Unknown wired pins/kinds block; the existing unwired generic-symbol compatibility fallback remains in Phase 6.5.

No source circuit JSON, pin-map coordinate, component position, grid utility, or routing algorithm was changed. The unrelated pre-existing `frontend/tsconfig.tsbuildinfo` and `backend/_probe_geo.py` are preserved and excluded from commits.

## LTspice junction semantics: independently measured

Eight isolated resistor-only microfixtures were netlisted by LTspice 24.1.9. Their opposite resistor terminals were checked as distinct singleton nets to avoid pin-coincidence false positives.

- An unsplit perpendicular intersection strictly inside both wires stays disconnected.
- Endpoint-to-wire-interior T contacts, shared endpoints, positive-length collinear overlaps, and split-X intersections connect.
- A component pin or FLAG on a wire interior connects to it.
- Disconnected FLAGs carrying the same name join electrically.

Phase 7 may use an unrelated crossing only when both wires remain unsplit through the crossing and no pin, flag, endpoint, or junction occupies it. It must still prefer rerouting and independently validate the final exported partition. The verification tool does not derive source nets or infer connectivity from its own drawing model; the actual LTspice netlist is the measured result.

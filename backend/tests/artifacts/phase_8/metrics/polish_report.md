# Phase 8 measurement evidence

Invariant checks: **PASS**

No PDF, native-rendering, or visual acceptance claim is made.

Values are before -> after. Full presentation bounds are renderer estimates.

| Circuit | Components | WIRE records | Length | Bends | Junctions | Bytes | Checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 555_astable_multivibrator.json | 4 -> 4 | 29 -> 25 | 2400 -> 2400 | 15 -> 15 | 3 -> 3 | 1096 -> 1216 | PASS |
| common_emitter_amplifier.json | 6 -> 6 | 23 -> 14 | 1536 -> 1536 | 4 -> 4 | 2 -> 2 | 1128 -> 1257 | PASS |
| led_blinker.json | 5 -> 5 | 18 -> 13 | 1472 -> 1472 | 6 -> 6 | 1 -> 1 | 904 -> 1077 | PASS |
| rc_high_pass_filter.json | 2 -> 2 | 6 -> 6 | 224 -> 224 | 3 -> 3 | 0 -> 0 | 486 -> 614 | PASS |
| rc_low_pass_filter.json | 2 -> 2 | 6 -> 6 | 224 -> 224 | 3 -> 3 | 0 -> 0 | 485 -> 609 | PASS |
| voltage_divider.json | 2 -> 2 | 5 -> 4 | 160 -> 160 | 0 -> 0 | 0 -> 0 | 461 -> 562 | PASS |
| bridge_rectifier.json | 5 -> 5 | 18 -> 15 | 1648 -> 1648 | 4 -> 4 | 2 -> 2 | 1002 -> 1213 | PASS |

## 555_astable_multivibrator.json

- Circuit bbox: `[176, 192, 752, 560]` -> `[176, 192, 752, 560]`; area 211968 -> 211968.
- Full presentation estimate bbox: `[16.0, 8.5, 788.0, 564.0]` -> `[104.0, 69.5, 760.0, 564.0]`; area 428846.0 -> 324392.0.
- SHEET: `[1, 1200, 800]` -> `[1, 752, 576]`.
- Coverage length: 2400 -> 2400.
- Label counts: `{"comments": 2, "directives": 0, "flags": 2, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 1, "omitted_descriptions": 0, "renderer_visible_labels": 20, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 2, "directives": 0, "flags": 2, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 1, "omitted_descriptions": 0, "renderer_visible_labels": 20, "symbol_window_overrides": 8, "text_records": 2}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## common_emitter_amplifier.json

- Circuit bbox: `[224, 128, 768, 624]` -> `[224, 128, 768, 624]`; area 269824 -> 269824.
- Full presentation estimate bbox: `[16.0, 6.0, 800.0, 644.0]` -> `[174.0, -4.5, 800.0, 644.0]`; area 500192.0 -> 405961.0.
- SHEET: `[1, 1200, 800]` -> `[1, 736, 720]`.
- Coverage length: 1536 -> 1536.
- Label counts: `{"comments": 2, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 17, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 18, "symbol_window_overrides": 12, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## led_blinker.json

- Circuit bbox: `[224, 208, 816, 592]` -> `[224, 208, 816, 592]`; area 227328 -> 227328.
- Full presentation estimate bbox: `[16.0, 8.5, 843.0, 612.0]` -> `[174.0, 77.5, 823.0, 612.0]`; area 499094.5 -> 346890.5.
- SHEET: `[1, 1200, 800]` -> `[1, 720, 608]`.
- Coverage length: 1472 -> 1472.
- Label counts: `{"comments": 2, "directives": 0, "flags": 2, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 1, "omitted_descriptions": 0, "renderer_visible_labels": 14, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 2, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 1, "omitted_descriptions": 0, "renderer_visible_labels": 15, "symbol_window_overrides": 10, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## rc_high_pass_filter.json

- Circuit bbox: `[128, 160, 336, 304]` -> `[128, 160, 336, 304]`; area 29952 -> 29952.
- Full presentation estimate bbox: `[16.0, 6.0, 710.0, 324.0]` -> `[118.0, 27.5, 489.0, 324.0]`; area 220692.0 -> 110001.5.
- SHEET: `[1, 1200, 800]` -> `[1, 528, 368]`.
- Coverage length: 224 -> 224.
- Label counts: `{"comments": 2, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 9, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 10, "symbol_window_overrides": 4, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## rc_low_pass_filter.json

- Circuit bbox: `[128, 160, 352, 288]` -> `[128, 160, 352, 288]`; area 28672 -> 28672.
- Full presentation estimate bbox: `[16.0, 8.5, 710.0, 308.0]` -> `[118.0, 13.5, 481.0, 308.0]`; area 207853.0 -> 106903.5.
- SHEET: `[1, 1200, 800]` -> `[1, 512, 368]`.
- Coverage length: 224 -> 224.
- Label counts: `{"comments": 2, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 9, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 10, "symbol_window_overrides": 4, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## voltage_divider.json

- Circuit bbox: `[144, 160, 176, 480]` -> `[144, 160, 176, 480]`; area 10240 -> 10240.
- Full presentation estimate bbox: `[16.0, 6.0, 581.0, 500.0]` -> `[94.0, 27.5, 443.0, 500.0]`; area 279110.0 -> 164902.5.
- SHEET: `[1, 1200, 800]` -> `[1, 512, 544]`.
- Coverage length: 160 -> 160.
- Label counts: `{"comments": 2, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 9, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 3, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 2, "omitted_descriptions": 0, "renderer_visible_labels": 10, "symbol_window_overrides": 4, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## bridge_rectifier.json

- Circuit bbox: `[208, 192, 752, 512]` -> `[208, 192, 752, 512]`; area 174080 -> 174080.
- Full presentation estimate bbox: `[16.0, 6.0, 779.0, 532.0]` -> `[118.0, 91.5, 768.5, 532.0]`; area 401338.0 -> 286545.25.
- SHEET: `[1, 1200, 800]` -> `[1, 752, 512]`.
- Coverage length: 1648 -> 1648.
- Label counts: `{"comments": 2, "directives": 0, "flags": 4, "ground_flags": 1, "header_descriptions": 2, "non_ground_flags": 3, "omitted_descriptions": 0, "renderer_visible_labels": 16, "symbol_window_overrides": 0, "text_records": 2}` -> `{"comments": 3, "directives": 0, "flags": 4, "ground_flags": 1, "header_descriptions": 0, "non_ground_flags": 3, "omitted_descriptions": 0, "renderer_visible_labels": 17, "symbol_window_overrides": 10, "text_records": 3}`.
- Failed checks: none.
- Native .net source/partition verification and exact input hashes are in the JSON report.

## Definitions and limitations

- **scope**: Measurement only; no optimization, native rendering, PDF, or visual acceptance claim.
- **components**: Number of actual ASC SYMBOL blocks; identities, positions, orientations and SYMATTR values are compared independently of block order. WINDOW changes are presentation-only.
- **segments**: One segment per serialized WIRE record, including duplicates and zero-length records. Endpoints are not snapped; nonzero diagonals are rejected.
- **wire_length**: routing.total_length is the sum of serialized Manhattan lengths in LTspice coordinate units. Duplicates/overlaps count as recorded. wire_coverage_length instead measures their collinear union once.
- **net_assignment**: Every nonzero ASC WIRE must fit wholly within exactly one source-routed net's collinear coverage union. Exact coverage must match per net. This permits reversal, sorting, merging and splitting, not relocation. No geometry is read from *_routing.json.
- **bends_junctions**: routing.bend_count counts degree-two orthogonal turns; junction_count counts degree >= 3 contacts in measure_routing's private per-net graphs. Collinear subdivisions are not bends. Unsplit interior Xs do not conduct. Physical pins/flags make contacts; labels do not shortcut remote islands.
- **crossings**: Distinct proper interior cross-net Xs from the serialized segments using routing.geometry.intersection; contact/short validation is separate. No crossings are assumed from a stale routing summary.
- **pin_pairs**: measure_routing evaluates all unordered pin pairs per net. Detour ratio is mean shortest routed/Manhattan distance for reachable noncoincident pairs; detours require ratio > 1.5 and excess >= 64. Disconnected pairs and coincident pairs are explicit. Efficiency is summed per-net pin HPWL / recorded length, or null for disconnected pairs.
- **routing_bbox**: routing.bounding_box encloses recorded wire endpoints and all installed ASY pins, including unwired singleton pins; no text, flags or symbol bodies. Area is envelope width times height.
- **circuit_bbox**: circuit_bbox encloses serialized wire endpoints plus transformed installed ASY body strokes and pins, excluding FLAG glyphs, text, windows and ASC decorative primitives. Curves use the existing renderer tessellation; no sheet margin is added.
- **full_presentation_bbox**: Renderer estimate at scale 1.0 from the existing _build_scene/_layout helpers, with ALL descriptions included, installed ASY default windows plus ASC overrides, flags, primitives, pin labels and text. Includes the renderer's 4-unit geometry padding and host font measurements. Text stays upright and renderer default/alignment behavior may differ from LTspice; this is NOT a native ink/crop bound. Hidden windows and unsupported defaults follow the existing renderer unchanged.
- **labels**: Counts distinguish FLAG records, ground/non-ground flags, ASC TEXT comments/directives, leading descriptions, WINDOW overrides, and renderer-visible label objects. Counts are records/objects, not unique strings or wrapped lines.
- **sheet**: Exact SHEET [number, width, height] declaration. Independent of occupied geometry and presentation bounds; not a clipping or page-fit assertion.
- **topology**: Existing adjacent .net files are parsed by verify_ltspice.parse_netlist and compared to source canonical pin partitions (including singleton unwired pins), then to each other. Node-token renaming is allowed. No netlist is generated here; provenance/freshness of supplied .net files is the caller's responsibility. SHA-256 identifies the exact inputs measured.
- **invariants**: Fail on exact per-net coverage, SYMBOL identity/attribute/position/orientation, pin, FLAG, IOPIN, conductive geometry, or actual netlist partition drift. Wire record count/length, windows, descriptions and sheet size may change. Electrical TEXT directives must remain equal ignoring position/order.
- **delta**: Numeric deltas are after minus before; negative means a smaller measured quantity, not automatically a quality improvement. All lengths are source-coordinate units and all areas squared units; file_bytes is the on-disk byte count.

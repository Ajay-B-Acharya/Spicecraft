# Phase 7 native LTspice inspection evidence

## Outcome

Seven current circuits were regenerated, netlisted with actual LTspice 24.1.9, opened in LTspice, and captured as native application screenshots at 1800 x 1050 after invoking the discovered View > Zoom to Fit menu command. All 60 canonical component pins preserve their validated partition across 32 electrical groups. No shorts, opens, missing pins, unexpected pins, or export diagnostics were reported.

**Visual acceptance remains blocked, not passed.** The PDF visual-review agent could not start because its configured provider was unavailable (`provider-not-found`). The session model's image read returned `Media omitted ... selected model does not support image input`. Therefore no visual judgement of bends, loops, junction appearance, spacing, label overlap, or professional presentation is claimed. Programmatic document preflight is not a visual review substitute.

No routing/layout fix was made because no visual defect could be confirmed. Topology, electrical nets, component placement, pin maps, router, and production code were not changed during this inspection task. No commit or push was performed.

## Captured circuits

| Circuit | Native screenshot | Electrical groups | Pins | Visual status |
| --- | --- | ---: | ---: | --- |
| Common Emitter Amplifier | native/common_emitter_amplifier/common_emitter_amplifier_ltspice.png | 6 | 13 | Not evaluated |
| RC Low-pass Filter | native/rc_low_pass_filter/rc_low_pass_filter_ltspice.png | 3 | 4 | Not evaluated |
| RC High-pass Filter | native/rc_high_pass_filter/rc_high_pass_filter_ltspice.png | 3 | 4 | Not evaluated |
| Voltage Divider | native/voltage_divider/voltage_divider_ltspice.png | 3 | 4 | Not evaluated |
| Bridge Rectifier | native/bridge_rectifier/bridge_rectifier_ltspice.png | 4 | 10 | Not evaluated |
| NE555 Astable Multivibrator | native/555_astable_multivibrator/555_astable_multivibrator_ltspice.png | 7 | 14 | Not evaluated |
| LED Blinker | native/led_blinker/led_blinker_ltspice.png | 6 | 11 | Not evaluated |

NE555's three unwired pins and LED Q1.E remain separate singleton groups. Common Emitter retains its intended six nets; the source's missing DC return remains unchanged and no simulation-readiness claim is made.

## Evidence

- `visual_verification.pdf`: seven-page native screenshot checklist, explicitly marked with blocked visual acceptance; 416 KB. Metadata, embedded fonts, pagination, and overflow preflight passed, but image content was not visually judged.
- `before/`: current exported ASC files, actual LTspice netlists, installed-ASY inspection renderings, per-circuit routing/partition JSON, and `routing_summary.json` with all_verified/all_deterministic true.
- `native/`: native application screenshots, isolated copies of exact ASC inputs, per-circuit capture metadata, and aggregate `capture_summary.json`. SHA-256 checks confirmed originals and opened copies were unchanged. Captures used only isolated owned LTspice windows, which closed normally; no schematic saves, simulation, or application-setting commands were issued.
- `backend_tests.log`: **172 tests passed in 50.045 seconds; zero failures/errors/skips**, including real LTspice tests and the known-shorted negative control.
- `frontend_tests.log`: **28 tests passed; zero failures/skips**.
- `frontend_typecheck.log`: independent TypeScript checking passed.
- `visual_status.json`: explicit per-circuit not_evaluated visual status plus successful electrical comparisons.

Inspection-only helper scripts were added under `backend/tools/`: `capture_ltspice.py` and `visual_inspection_report.py`. The system Python received small PDF creation/rendering dependencies; no repository dependency manifest or backend virtual-environment configuration changed.

## Gate decision

Electrical verification is complete and no electrical shorts or opens were introduced. The visual acceptance gate cannot be closed with the available image capability. These screenshots remain the evidence set for an image-capable reviewer before Phase 8; they must not be described as visually approved.

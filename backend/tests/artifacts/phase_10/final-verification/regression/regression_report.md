# SpiceCraft circuit regression report

Overall: **PASS**

| Circuit | Components | Pins | Groups | Electrical | Routing | Export | LTspice | Visual |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 555 Astable Multivibrator | 4 | 14 | 7 | PASS | PASS | PASS | PASS | PASS |
| Common Emitter Amplifier | 6 | 13 | 6 | PASS | PASS | PASS | PASS | PASS |
| LED Blinker | 5 | 11 | 6 | PASS | PASS | PASS | PASS | PASS |
| RC High Pass Filter | 2 | 4 | 3 | PASS | PASS | PASS | PASS | PASS |
| RC Low Pass Filter | 2 | 4 | 3 | PASS | PASS | PASS | PASS | PASS |
| Voltage Divider Routing Regression | 2 | 4 | 3 | PASS | PASS | PASS | PASS | PASS |
| Bridge Rectifier Routing Regression | 5 | 10 | 4 | PASS | PASS | PASS | PASS | PASS |

## 555 Astable Multivibrator

Wire length **2400**, segments **25**, bends **15**, junctions **3**, crossings **0**.
Bounding box: `[176, 192, 752, 560]`; routing efficiency: **0.6667**.
Generation time (min / median / max): **39.547 / 55.595 / 60.121 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](555_astable_multivibrator_comparison.png) — PASS.

## Common Emitter Amplifier

Wire length **1536**, segments **14**, bends **4**, junctions **2**, crossings **0**.
Bounding box: `[224, 128, 768, 624]`; routing efficiency: **0.8958**.
Generation time (min / median / max): **28.466 / 37.380 / 40.443 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](common_emitter_amplifier_comparison.png) — PASS.

## LED Blinker

Wire length **1472**, segments **13**, bends **6**, junctions **1**, crossings **0**.
Bounding box: `[224, 208, 816, 592]`; routing efficiency: **0.9348**.
Generation time (min / median / max): **19.969 / 28.021 / 30.451 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](led_blinker_comparison.png) — PASS.

## RC High Pass Filter

Wire length **224**, segments **6**, bends **3**, junctions **0**, crossings **0**.
Bounding box: `[128, 160, 336, 304]`; routing efficiency: **0.4286**.
Generation time (min / median / max): **5.461 / 8.563 / 9.426 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](rc_high_pass_filter_comparison.png) — PASS.

## RC Low Pass Filter

Wire length **224**, segments **6**, bends **3**, junctions **0**, crossings **0**.
Bounding box: `[128, 160, 352, 288]`; routing efficiency: **0.4286**.
Generation time (min / median / max): **5.388 / 5.982 / 7.075 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](rc_low_pass_filter_comparison.png) — PASS.

## Voltage Divider Routing Regression

Wire length **160**, segments **4**, bends **0**, junctions **0**, crossings **0**.
Bounding box: `[144, 160, 176, 480]`; routing efficiency: **0.6000**.
Generation time (min / median / max): **10.778 / 11.208 / 12.186 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](voltage_divider_comparison.png) — PASS.

## Bridge Rectifier Routing Regression

Wire length **1648**, segments **15**, bends **4**, junctions **2**, crossings **0**.
Bounding box: `[208, 192, 752, 512]`; routing efficiency: **0.8835**.
Generation time (min / median / max): **26.156 / 27.924 / 29.371 ms**, 5 samples. Raw measurements and complete connectivity are in the JSON report.
[Visual comparison](bridge_rectifier_comparison.png) — PASS.

## Coverage and limitations

Backend component kinds covered: bc547, capacitor, diode, led, ne555, resistor.
Special connections: ground FLAG 0, VCC power labels, VIN/VOUT and custom net labels.
Unsupported backend features (not counted as passing component coverage): voltage source, current source, AC/pulse source, inductor, potentiometer, PNP, MOSFET, ground component.

No simulation or live AI network request is performed. Fixture input invokes the real frontend compiler through a test-only export-contract adapter. Golden comparison is semantic, not ASC byte equality. Repeated identical input must still be deterministic.

Only 2–6-component source fixtures are available; large-circuit scalability is unverified. Metric growth requires review, not automatic failure. Visual acceptance requires explicit review bound to current export/image hashes.

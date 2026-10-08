# Complete corpus evidence

This is a consolidated evidence view, not a new execution.

```json
{
  "cases": 245,
  "attempts": 490,
  "failure_stages": {
    "bridge": 38,
    "compile": 222,
    "connectivity": 12,
    "export": 10,
    "route": 24,
    "serialized_validation": 14
  },
  "failure_codes": {
    "AMBIGUOUS_SOURCE_IDENTITY": 20,
    "BLOCKED_PIN_ESCAPE": 12,
    "COMPILER_ERROR": 246,
    "CONFLICTING_COMPONENT_DEFINITION": 6,
    "CONFLICTING_NET_LABELS": 8,
    "DUPLICATE_COMPILED_ID": 10,
    "DUPLICATE_WIRE": 6,
    "INSTANCE_NAME_COLLISION": 10,
    "INVALID_ATTRIBUTE": 2,
    "INVALID_BACKEND_IDENTITY": 8,
    "INVALID_COMPILED_LABEL": 4,
    "INVALID_COMPONENTS": 4,
    "INVALID_COMPONENT_IDENTITY": 2,
    "LABEL_ONLY_NET": 2,
    "MISSING_PIN": 24,
    "NET_LABEL_COLLISION": 2,
    "NO_SAFE_ROUTE": 4,
    "PIPELINE_TIMEOUT": 32,
    "UNEXPECTED_PIN": 26,
    "UNMAPPED_COMPILED_REFERENCE": 4,
    "UNMAPPED_SOURCE_IDENTITY": 4,
    "UNRESOLVED_PIN": 6,
    "UNSUPPORTED_COMPONENT": 6,
    "UNSUPPORTED_SHARED_EXPORT_KIND": 18
  },
  "determinism_status": {
    "OBSERVED": 245
  },
  "case_status": {
    "FAIL": 22,
    "INVALID": 106,
    "PASS": 85,
    "UNSUPPORTED": 32
  },
  "attempt_status": {
    "FAIL": 44,
    "INVALID": 212,
    "PASS": 170,
    "UNSUPPORTED": 64
  },
  "successful_attempts_by_stage": {
    "compile": 268,
    "bridge": 230,
    "connectivity": 218,
    "route": 142,
    "export": 184,
    "serialized_validation": 170
  },
  "successful_cases_by_stage": {
    "compile": 134,
    "bridge": 115,
    "connectivity": 109,
    "route": 71,
    "export": 92,
    "serialized_validation": 85
  }
}
```

| Circuit | Components | Status | First failure stage | Evidence |
| --- | ---: | --- | --- | --- |
| circuit-0115ba888b0bdb79953e — test_connectivity.py:line:204 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-01903988ebfae2fea322 — test_connectivity.py:line:273 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-028d64605f0d82fbf036 — Test | 500 | PASS | none | [../phase10-drift-recheck/corpus_report.json](../phase10-drift-recheck/corpus_report.json) |
| circuit-03b15c4e1ce43adf6462 — test_production.py:line:31 | 0 | INVALID | export | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-059b92bfc59c1877b8ba — connectivity.test.cjs:line:82 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-05cc4d8b439735772811 — connectivity.test.cjs:line:70 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-066312efd75869b61593 — test_connectivity.py:line:331 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-06a9646eb15a387137e9 — test_connectivity.py:line:294 | 1 | UNSUPPORTED | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-072945f94051edb70de7 — regressionBridge.test.cjs:line:116 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0760e59cce48acb8205c — test_connectivity.py:line:244 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-07dd90d78111d83e93e3 — test_connectivity.py:line:233 | 1 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0930750b08cb227ec4c0 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-09609bb822e0c72ea5d4 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0993c36910a455790abf — connectivity.test.cjs:line:91 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-09c4a73bf0dc17a7d282 — test_connectivity.py:line:273 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-09f50ff5c79d74932cab — regressionBridge.test.cjs:line:261 | 1 | INVALID | bridge | [../phase10-drift-recheck/corpus_report.json](../phase10-drift-recheck/corpus_report.json) |
| circuit-0a558cbc4a4eb6f348fe — test_connectivity.py:line:236 | 1 | FAIL | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0a8220c632a6a2b94105 — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0ba4a3849088c94540b9 — Inner | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0c1969c5dea0503cf4d7 — Blocked circuit | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0c4bee456753e9aa59cf — test_pipeline_regression.py:line:116 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-0dd593fedb688fbb7b2d — Test | 1 | FAIL | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-109763b282a39b94d088 — regressionBridge.test.cjs:line:289 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1126f4d9ab968a5844fa — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-118cc2dbf76bf959fa3a — connectivity.test.cjs:line:111 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-11d43159df6d8d990adc — regressionBridge.test.cjs:line:192 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-11d9ab365454788650b6 — Common Emitter Amplifier | 6 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-12b0bc244921f893ccf9 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1483fb1ede299a0e2cb5 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1484c39f48834263dceb — regressionBridge.test.cjs:line:201 | 4 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-16771e4190255b558fc3 — Test | 1 | UNSUPPORTED | compile | [../phase10-drift-recheck/corpus_report.json](../phase10-drift-recheck/corpus_report.json) |
| circuit-175f595ed421a1b96264 — connectivity.test.cjs:line:62 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-178b4c854585834852ee — regressionBridge.test.cjs:line:317 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-17c978b058e50543b74f — test_connectivity.py:line:184 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-18eb0bba28c2c1120af7 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-191ca2b21d2f2d005616 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1a71b517910749c1d7a7 — connectivity.test.cjs:line:81 | 2 | INVALID | compile | [../phase10-drift-recheck/corpus_report.json](../phase10-drift-recheck/corpus_report.json) |
| circuit-1c1cb9e3f499d29a8acf — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1d02f28ac4b12d3b95d5 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-1f7080d89f1370b3ab52 — connectivity.test.cjs:line:61 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-20ea3900eb605854bf6c — test_pipeline_regression.py:line:117 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-218e625149f479cef6cf — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-21a636a285c9988bb016 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-23066c4e84620d838ce0 — regressionBridge.test.cjs:line:252 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2366ee1614b76256a58e — test_connectivity.py:line:410 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2470040b96f1d243e839 — connectivity.test.cjs:line:156 | None | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-24bafed30e3b55a469d9 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-27feaf23121146b82730 — regressionBridge.test.cjs:line:164 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-28b386d1c7b60cbad303 — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-29731ee04e0323e67fac — test_pipeline_regression.py:line:114 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2d089e4d2c979c27c20b — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2d7f499af635d0e71c5b — test_connectivity.py:line:329 | 2 | INVALID | export | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2d9a0916473ac7f02801 — test_routing.py:line:353 | 3 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-2f22280e34592faa23b6 — test_connectivity.py:line:184 | 2 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-31010fa8618ea40e6029 — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3337e6fd1fcd18293666 — connectivity.test.cjs:line:70 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3432f85025ca65479f4e — Voltage Divider Routing Regression | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-354c79a826f2f25af4cc — hardening.test.cjs:line:118 | 0 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3c4deb2d9c1d3c4d4f8b — LED Blinker | 5 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3c707fd2cbb172df3a93 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3c8c2d1b46bbcda8371d — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-3fa119bf3a1dc74096a9 — regressionBridge.test.cjs:line:261 | 1 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-40f3e5a6fe13512c8065 — test_connectivity.py:line:244 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-42f0738ac053a96df1fb — connectivity.test.cjs:line:123 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4386b152c692f2744b45 — test_component_support_boundaries.py:line:16 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-439ccb6d4e50ddd4936b — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-440240615dcf4888bfee — test_connectivity.py:line:204 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-44136fa355b3678a1146 — connectivity.test.cjs:line:158 | 0 | INVALID | export | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4439a6734293bb87d5ef — test_regression_validation.py:line:346 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4948e5f50781d4ea66a3 — test_connectivity.py:line:268 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-495ad59c2666db9d2627 — test_connectivity.py:line:96 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4acb7b3adf42a1e4daba — test_connectivity.py:line:119 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4afbe5555c75ae38ca5e — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4b181caefb37f0a82f7d — regressionBridge.test.cjs:line:242 | 2 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4b246f400e7d2cab3c5d — regressionBridge.test.cjs:line:104 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4b606d8ac201c8cfefb6 — Ambiguous refs | 2 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4c7240d6ba3db86f6b03 — test_connectivity.py:line:255 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4d14d418dd8e463e5458 — test_connectivity.py:line:345 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4db0433119dfe7a226b9 — regressionBridge.test.cjs:line:271 | 2 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4f0d2acd28594cd56f28 — test_connectivity.py:line:252 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4f53cda18c2baa0c0354 — test_connectivity.py:line:204 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4fa7ce48b1ee6eecb6a5 — Test | 501 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4fc1256e0b400e5aec88 — test_component_support_boundaries.py:line:16 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-514fb198ed1c3c543e3a — regressionBridge.test.cjs:line:164 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-527823f34ec2ad129642 — connectivity.test.cjs:line:57 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-531f8a28b226d49b52e6 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-538e2f8f2c4abf9ad2f9 — 555 Astable Multivibrator | 4 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-543f702d0dcb12897945 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-547fdf6f2867f0df3f59 — Common Emitter Amplifier | 6 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-561343fcc15e45de847a — connectivity.test.cjs:line:94 | 3 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-57800739208985bab32d — test_connectivity.py:line:244 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-594e1339ccaadcba8920 — export_polish_report.py:line:37 | None | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5adfe6fd024ea0a8885c — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5bd0a24d2dba815a326c — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5bf411d0700870d1dd0b — test_connectivity.py:line:286 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5c17722626a31909aee6 — test_connectivity.py:line:286 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5d3e6ebd71b77842f42d — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5d43216779aacfa68c02 — connectivity.test.cjs:line:105 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5d4a4cef398a7b9ab1cb — Inner | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-61d49cb3ec35ee6c13d3 — regressionBridge.test.cjs:line:164 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-6328860f7adab082790c — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-64c4366287ae0bb03120 — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-650c9fa5864be800715a — regressionBridge.test.cjs:line:151 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-66c18c8da0d662896763 — connectivity.test.cjs:line:117 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-67635628be75e2ae1c9c — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-6bacc236b8a723492c4a — test_regression_validation.py:line:42 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-6e35c90c9194de5fe288 — regressionBridge.test.cjs:line:219 | 3 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-71010c8f22b3754a72be — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-72173c03a45b93630a70 — test_connectivity.py:line:101 | 3 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7344baf2bb9a8d887dae — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-73e909ed8e861cba1b97 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-74234e98afe7498fb5da — test_connectivity.py:line:204 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-74daed06ee141d16b4cb — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7788b8e727d3b2f6f97d — test_connectivity.py:line:128 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7860dd8402d407013fe0 — regressionBridge.test.cjs:line:247 | 2 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-78eaf20340b3e669ed1d — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-79fd1deeca90b2ef8f61 — connectivity.test.cjs:line:100 | 1 | FAIL | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7b8175604702793762ef — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7c0a8699c38a3898403d — test_connectivity.py:line:142 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7c4b65ea31631148fff8 — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7db9977fa4a5aec21786 — test_connectivity.py:line:111 | 2 | UNSUPPORTED | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7e0dd67db0d5c6acc85d — connectivity.test.cjs:line:38 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-7e626debb39bd191c29e — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-817c1c103d58c049ece7 — hardening.test.cjs:line:119 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-81c6444add963075e25f — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-81ec37413acabfef7e77 — hardening.test.cjs:line:121 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8336117f9954e8c058a7 — RC High Pass Filter | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-83be75b29f6fb0ef9c58 — test_connectivity.py:line:313 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8812fde960848c5546f2 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8a097cc0885e0194db83 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8ae8de8ce92bf0f11b6a — test_connectivity.py:line:222 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8b9b59d84a5c6f0149b4 — regressionBridge.test.cjs:line:175 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8c69a40068622fa91a98 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8ca85f4323d18f614b38 — regressionBridge.test.cjs:line:278 | None | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8ca8f4bc59e746b3762d — test_connectivity.py:line:292 | 1 | UNSUPPORTED | connectivity | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8d910904fcc302dab99a — test_connectivity.py:line:306 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8e46c5523d099c7090e2 — test_connectivity.py:line:334 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8f27083fa729f6ea01e2 — connectivity.test.cjs:line:49 | 3 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-8fd2efaa9d3266ed2ad6 — test_connectivity.py:line:340 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-915d8f088f4fc5f3ee9f — connectivity.test.cjs:line:129 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9243ef5763d82292493f — test_pipeline_regression.py:line:115 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-937a53cf299d80a19bfe — Bridge Rectifier Routing Regression | 5 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-93e15d6ad595b7977e4d — regressionBridge.test.cjs:line:164 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9667b08297f2c0c31332 — Common Emitter Amplifier | 6 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-99500527279cdaba1930 — test_routing.py:line:240 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9a28c82776ba5c353578 — test_connectivity.py:line:233 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9a9bdef134526177d9fa — Test | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9d5c9990e1dd54a83112 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9db077e53545d23d643d — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9e2e1ced384dc86cd404 — test_connectivity.py:line:313 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-9f8f74a22a11b8ca0077 — test_connectivity.py:line:273 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a03127880e4fd310acf2 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a08dcc57e5bac435deb6 — test_routing.py:line:361 | 4 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a3dd4bcfee29e523898b — connectivity.test.cjs:line:54 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a4f8d9197f5d204fb97d — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a6ddc3ca6e6ba331b39f — regressionBridge.test.cjs:line:104 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a77e3c336f4929d49967 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a7aabd1ba3f8ba6931f7 — test_component_support_boundaries.py:line:16 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a8d3b622431f29efd0c4 — regressionBridge.test.cjs:line:361 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-aa2c5d249193467689ba — Test | 1 | INVALID | export | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ab203b84adc3280125b2 — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ab96782069306a0e310d — test_pipeline_regression.py:line:113 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ac50acbbe336b55a4fa6 — Test | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ad9a8de607e94d599f38 — connectivity.test.cjs:line:155 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ada25d6e596c9e802c3b — test_pin_geometry.py:line:817 | 3 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b0fe37561a3da3b53b88 — connectivity.test.cjs:line:73 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b11e8facd4d140cc1633 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b3283bf184bb082f364b — hardening.test.cjs:line:119 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b3e3b950eb4a09e0e6b9 — test_connectivity.py:line:214 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b44889fec36a8bd41c62 — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b47c63cdb040faf52fa1 — test_routing.py:line:476 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b5e3053c0dfc519c1056 — hardening.test.cjs:line:119 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b68b39d2b1f1cce18609 — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-b7139aba076994560994 — test_connectivity.py:line:218 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ba91a59a637bb9d10af3 — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-bbd907fe8b0da97d9051 — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-bef3e4c0d95e3d332c34 — connectivity.test.cjs:line:44 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c0c9b5da14184d92feb4 — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c139bafdc5a07ba94d79 — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c1873fce60feb2bc0d36 — RC Low Pass Filter | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c3cc7f5ed7ba5926bce3 — test_export_polish.py:line:117 | 1 | INVALID | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c540b8a187282a67cf55 — regressionBridge.test.cjs:line:113 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c686f07a1b90328322b9 — regressionBridge.test.cjs:line:164 | 1 | UNSUPPORTED | bridge | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c70fa8d455dfba0f6950 — test_connectivity.py:line:263 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c74ddc3e8afdda37cd56 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-c969d1bdba2d5ac6e93a — test_connectivity.py:line:286 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ca19b40a56fa8f141b93 — Test | 500 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-cb08f0621ecabdb63c7f — connectivity.test.cjs:line:78 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ccebc5aebe8bb555502b — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-cde3524b29b7ff905b22 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ce1040c45b8e6c3bcbe8 — test_connectivity.py:line:134 | 3 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ce3077dee0ee193244ff — connectivity.test.cjs:line:102 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d06dbe3c49c25059b57e — connectivity.test.cjs:line:70 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d0a675591fb8bc147594 — test_connectivity.py:line:233 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d10ae1682ca9cbe68456 — connectivity.test.cjs:line:157 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d1c1a52b508e6d3e931c — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d30c8636537ac1fe7fa4 — regressionBridge.test.cjs:line:121 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d33a953ddb979098bb84 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d3b3536c74cb3c9adeea — connectivity.test.cjs:line:90 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d621e90b9ac86375709c — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d79cc631f6503a7ffce1 — test_connectivity.py:line:286 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d8e8907d585233eac4d0 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d8f96adb2962ad5ba9ec — Test | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-db377cdd6a61564fd8a0 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-dca0ec77c98a3bf7fa94 — test_component_support_boundaries.py:line:16 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-df9bdf682ead6ffb9731 — regressionBridge.test.cjs:line:196 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e0065951b5398022cde6 — Test | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e0a8bff21a49caa89e5b — connectivity.test.cjs:line:70 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e150829c70c8fbeedb7d — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e17d306037d74bf59fb3 — test_connectivity.py:line:273 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e3abd2e84c8e5cbd85d2 — connectivity.test.cjs:line:85 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e53a7e3f9ad60a806df0 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e6e89bec12710a6ec377 — test_export_polish.py:line:117 | 1 | INVALID | export | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e70a4fc48ce766624748 — test_connectivity.py:line:247 | 1 | UNSUPPORTED | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e70f65d9168b2c5a2645 — test_connectivity.py:line:161 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e89c2974e9d23e4f26a3 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e89d291d6e5056b905d4 — test_connectivity.py:line:214 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e949db5feb93ffbe0ac2 — test_connectivity.py:line:313 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-e9fb5b1dcf1dcfab24f6 — regressionBridge.test.cjs:line:233 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-eabbd754a05feaba15e2 — regressionBridge.test.cjs:line:261 | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ead1393f52f66e57cb4c — hardening.test.cjs:line:119 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ed73c3594d605fdd7406 — test_connectivity.py:line:204 | None | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f21c0ec514e079021abd — test_export_polish.py:line:122 | 1 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f27fc6b4ad6231ffb68b — connectivity.test.cjs:line:38 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f2b91ea1243440df2645 — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f3fda1406733a47f5c25 — test_connectivity.py:line:313 | 2 | FAIL | serialized_validation | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f511a037f0e4cee3efba — Test | 1 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-f90b1e513f005ba5fff2 — test_connectivity.py:line:300 | 2 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-fa50e06d005f449ebf1f — test_connectivity.py:line:214 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-fb420c6210c600c96e2d — test_connectivity.py:line:204 | 0 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-fddb1c1846acbeb11ff6 — connectivity.test.cjs:line:122 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-fe40af3f98b26ab38791 — Test | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ff5b2622d96773f43335 — test_connectivity.py:line:184 | 2 | INVALID | compile | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-487a1e171625615c17a0 — Repeated resistor sections (10 components) | 10 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d79639eaaa899c072620 — Repeated filter sections (10 components) | 10 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-011da72b4d779fc1e919 — Repeated filter sections (25 components) | 25 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-ff1fd8b1b9cb2998f6df — Repeated resistor sections (25 components) | 25 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-6ceaf1a9d262db9531d6 — Repeated resistor sections (50 components) | 50 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-d1745c42a0d7260ca981 — Repeated filter sections (50 components) | 50 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-44dc9954c88aea4055f2 — Repeated filter sections (100 components) | 100 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-bf177d289f65b1ff63fb — Repeated resistor sections (100 components) | 100 | PASS | none | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-4bcd9f1440d1be5ced40 — Repeated filter sections (250 components) | 250 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-5eee04129d7baad3326a — Repeated resistor sections (250 components) | 250 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-55e763579a65517ae71f — Repeated resistor sections (500 components) | 500 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |
| circuit-a82f72ae9c7431e50765 — Repeated filter sections (500 components) | 500 | FAIL | route | [../phase10-acceptance/corpus_report.json](../phase10-acceptance/corpus_report.json) |

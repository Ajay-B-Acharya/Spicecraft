# Project verification

Overall: **PASS**

REVIEW means incomplete or unreviewed evidence, not a passing gate.

| Gate | Status |
| --- | --- |
| Backend | PASS |
| Frontend | PASS |
| TypeScript | PASS |
| Build | PASS |
| Electrical | PASS |
| Routing | PASS |
| LTspice | PASS |
| Visual | PASS |

## Commands

| Command | Status | Exit | Timeout | Logs |
| --- | --- | --- | --- | --- |
| backend | PASS | 0 | False | [stdout](logs/backend.stdout.log) / [stderr](logs/backend.stderr.log) |
| frontend | PASS | 0 | False | [stdout](logs/frontend.stdout.log) / [stderr](logs/frontend.stderr.log) |
| typescript-before-build | PASS | 0 | False | [stdout](logs/typescript-before-build.stdout.log) / [stderr](logs/typescript-before-build.stderr.log) |
| build | PASS | 0 | False | [stdout](logs/build.stdout.log) / [stderr](logs/build.stderr.log) |
| typescript-after-restore | PASS | 0 | False | [stdout](logs/typescript-after-restore.stdout.log) / [stderr](logs/typescript-after-restore.stderr.log) |
| regression | PASS | 0 | False | [stdout](logs/regression.stdout.log) / [stderr](logs/regression.stderr.log) |

## Evidence

Regression: [regression report](regression/regression_report.json)
Circuit records: 7
Compiler: PASS; Export: PASS

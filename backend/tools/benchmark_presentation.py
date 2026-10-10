"""Compare bounded label-candidate filtering with the unchanged exhaustive score.

Both modes execute the complete backend exporter; output must be byte-identical.
This is a development benchmark, not a production export option.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ltspice_exporter import generate_asc_with_routing


def measure(source: Path, output: Path, samples: int = 3):
    if not 1 <= samples <= 20:
        raise ValueError("Samples must be between 1 and 20")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    circuit = json.loads(source.read_text(encoding="utf-8-sig"))
    before = json.dumps(circuit, sort_keys=True)
    report = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "samples": [], "python": sys.version,
              "limitations": "Backend source export only; timings include validation, not compiler startup or native LTspice."}
    for index in range(samples):
        for mode in ("exhaustive", "filtered"):
            metrics = {}
            if mode == "exhaustive":
                with patch("app.services.export_presentation._nearby_obstacles", side_effect=lambda symbol, obstacles: obstacles):
                    text, diagnostics, _ = generate_asc_with_routing(circuit, metrics=metrics)
            else:
                text, diagnostics, _ = generate_asc_with_routing(circuit, metrics=metrics)
            report["samples"].append({"mode": mode, "sample": index + 1, "metrics": metrics,
                "asc_sha256": hashlib.sha256(text.encode()).hexdigest() if text else None,
                "errors": [d.format() for d in diagnostics if d.severity == "error"]})
            (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    hashes = {sample["asc_sha256"] for sample in report["samples"]}
    report["source_unchanged"] = before == json.dumps(circuit, sort_keys=True)
    report["identical_asc"] = len(hashes) == 1 and None not in hashes
    report["status"] = "PASS" if report["identical_asc"] and report["source_unchanged"] else "FAIL"
    report["medians_ms"] = {}
    for mode in ("exhaustive", "filtered"):
        timings = [sample["metrics"] for sample in report["samples"] if sample["mode"] == mode]
        export = [metrics["stagesMs"]["export"] for metrics in timings if "export" in metrics["stagesMs"]]
        report["medians_ms"][mode] = {"total": statistics.median(metrics["totalTimeMs"] for metrics in timings),
                                     "export": statistics.median(export) if export else None}
    (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    report = measure(args.source, args.output, args.samples)
    print(json.dumps({key: report[key] for key in ("status", "identical_asc", "source_unchanged", "medians_ms")}, indent=2))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

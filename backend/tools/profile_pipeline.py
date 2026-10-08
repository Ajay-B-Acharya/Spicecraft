"""Measure one existing source circuit, including repeated-process retention.

Run with the backend environment. Profiling and traced-memory passes are separate
from uninstrumented timing samples; neither is a production speed guarantee.
"""
from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
from pathlib import Path
import platform
import pstats
import statistics
import sys
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.asc_validation import ERROR
from app.services.ltspice_exporter import generate_asc_with_routing


def measure(source: Path, output: Path, samples: int = 5, memory_samples: int = 20):
    if not 1 <= samples <= 100 or not 1 <= memory_samples <= 100:
        raise ValueError('Samples must be between 1 and 100')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be a new or empty directory')
    output.mkdir(parents=True, exist_ok=True)
    circuit = json.loads(source.read_text(encoding='utf-8-sig'))
    before = json.dumps(circuit, sort_keys=True)
    results = []
    hashes = []

    def export():
        metrics = {}
        asc, diagnostics, routed = generate_asc_with_routing(circuit, strict=True, metrics=metrics)
        errors = [diagnostic.format() for diagnostic in diagnostics if diagnostic.severity == ERROR]
        if errors or not asc:
            raise ValueError('Pipeline failed: ' + '; '.join(errors))
        return asc, metrics

    for _ in range(samples):
        asc, metrics = export()
        hashes.append(hashlib.sha256(asc.encode()).hexdigest())
        results.append(metrics)
    del asc, metrics
    profile = cProfile.Profile()
    profile.runcall(export)
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(35)
    (output / 'profile.txt').write_text(stream.getvalue(), encoding='utf-8')
    del profile
    gc.collect()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    retained = []
    for _ in range(memory_samples):
        export()
        gc.collect()
        retained.append(tracemalloc.get_traced_memory()[0] - baseline)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report = {
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'environment': {'python': sys.version, 'platform': platform.platform()},
        'status': 'PASS', 'samples': results,
        'total_ms': {'min': min(r['totalTimeMs'] for r in results),
                     'median': statistics.median(r['totalTimeMs'] for r in results),
                     'max': max(r['totalTimeMs'] for r in results)},
        'deterministic_asc': len(set(hashes)) == 1, 'asc_hashes': hashes,
        'source_unchanged': before == json.dumps(circuit, sort_keys=True),
        'memory': {'samples': memory_samples, 'retained_bytes_after_gc': retained,
                   'peak_traced_bytes': peak, 'final_traced_bytes': current,
                   'method': 'tracemalloc in one warmed Python process; output discarded and gc.collect after each export',
                   'limitations': 'Python allocations only, not native allocations or RSS; tracing changes performance; small sample is not a leak proof'},
        'profile': 'profile.txt',
        'limitations': ['Backend source export only; compiler and native LTspice are measured by other commands.',
                        'Profile and traced-memory passes are not included in uninstrumented sample timings.'],
    }
    if not report['deterministic_asc'] or not report['source_unchanged']:
        report['status'] = 'FAIL'
    (output / 'profile_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--memory-samples', type=int, default=20)
    args = parser.parse_args()
    try:
        report = measure(args.source, args.output, args.samples, args.memory_samples)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: report[key] for key in ('status', 'total_ms', 'deterministic_asc', 'memory')}, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())

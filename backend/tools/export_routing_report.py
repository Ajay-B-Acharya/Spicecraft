"""Export existing circuits and independently verify their real LTspice pin sets.

Usage: python -B backend/tools/export_routing_report.py --output DIRECTORY
       [--render] [--require-ltspice] [--circuit path/to/circuit.json ...]

Only the caller-supplied output directory receives generated artifacts. This is
inspection tooling, not another connectivity builder or production serializer.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ERROR
from app.services.connectivity import build_connectivity
from app.services.ltspice_exporter import generate_asc_with_routing
from tools.verify_ltspice import (
    compare_partitions, discover_ltspice_executable, parse_netlist,
    read_ltspice_text, run_ltspice_netlist,
)


def export_report(paths: list[Path], output: Path, *, render: bool = False,
                  require_ltspice: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    executable = discover_ltspice_executable()
    if require_ltspice and executable is None:
        raise FileNotFoundError('LTspice is required for independent export verification')
    records = []
    for path in paths:
        source = json.loads(path.read_text(encoding='utf-8'))
        model = build_connectivity(source)
        asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
        errors = [d for d in diagnostics if d.severity == ERROR]
        if errors or routed is None or not asc:
            raise ValueError(f'{path.name}: export failed\n' + '\n'.join(d.format() for d in errors))
        repeated, repeated_diagnostics, _ = generate_asc_with_routing(source, strict=True)
        if asc != repeated or diagnostics != repeated_diagnostics:
            raise ValueError(f'{path.name}: export is not deterministic')
        expected = {net.name: [pin.key for pin in net.pins] for net in model.nets if net.pins}
        expected.update({f'unconnected:{pin.key}': [pin.key] for pin in model.unconnected_pins()})
        asc_path = output / f'{path.stem}.asc'
        asc_path.write_text(asc, encoding='utf-8')
        record = {
            'circuit': source.get('name', path.stem),
            'source_file': path.name,
            'components': len(source.get('components', [])),
            'expected_nets': expected,
            'metrics': routed.metrics,
            'junctions': {name: list(points) for name, points in routed.junctions.items()},
            'crossings': [asdict(crossing) for crossing in routed.crossings],
            'diagnostics': [asdict(d) for d in diagnostics],
            'deterministic': True,
            'netlist_verification': {'status': 'not_run', 'reason': 'LTspice not installed'},
        }
        if executable is not None:
            net_path = run_ltspice_netlist(asc_path, output, executable=executable)
            actual = parse_netlist(asc, read_ltspice_text(net_path))
            verification = compare_partitions(expected, actual)
            record['actual_pin_nodes'] = actual
            record['netlist_verification'] = verification.to_dict()
            if not verification.ok:
                raise ValueError(f'{path.name}: LTspice partition differs\n' + json.dumps(verification.to_dict(), indent=2))
        if render:
            from tools.render_asc import render_asc
            image = render_asc(asc_path, asc_path.with_suffix('.png'),
                               heading=f"Phase 7 — {source.get('name', path.stem)}")
            record['inspection_image'] = {'file': image.output_path.name,
                                          'width': image.width, 'height': image.height}
        (output / f'{path.stem}_routing.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        records.append(record)
    report = {'circuits': records, 'all_deterministic': True,
              'ltspice_verified': executable is not None,
              'all_verified': executable is not None and all(r['netlist_verification'].get('ok') for r in records)}
    (output / 'routing_summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--circuit', type=Path, action='append')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--require-ltspice', action='store_true')
    args = parser.parse_args()
    paths = args.circuit or sorted((BACKEND_ROOT / 'circuits').glob('*.json'))
    report = export_report(paths, args.output, render=args.render, require_ltspice=args.require_ltspice)
    for record in report['circuits']:
        print(f"{record['circuit']}: {json.dumps(record['metrics'], sort_keys=True)}; LTspice={record['netlist_verification'].get('ok', 'not run')}")
    print(f"Artifacts: {args.output.resolve()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

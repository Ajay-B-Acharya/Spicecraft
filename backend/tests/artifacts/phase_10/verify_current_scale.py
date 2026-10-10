"""Remeasure successful corpus geometry and compare the same ASC in native LTspice."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.ltspice_exporter import generate_asc_with_routing, place_components
from app.services.connectivity import build_connectivity
from app.services.routing.metrics import measure_routing
from tools.verify_ltspice import run_ltspice_netlist, parse_netlist, compare_partitions, read_ltspice_text
from tools.render_asc import render_asc

execution = ROOT / 'backend/tests/corpus/runs/current-execution'
if not (execution / 'invocation.json').is_file():
    raise RuntimeError('Complete the corpus command before reviewing its successful cases')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
report = json.loads((execution / 'corpus_report.json').read_text())
results = []
for case in report['cases']:
    successful = [sample for sample in case['samples'] if sample['overall'] == 'PASS']
    if not case.get('synthetic') or not successful:
        continue
    sample = successful[0]
    directory = output / case['id']
    directory.mkdir()
    source = json.loads((execution / sample['evidence_directory'] / 'compiled.json').read_text())['backend']
    metrics = {}
    asc, diagnostics, routed = generate_asc_with_routing(source, metrics=metrics)
    digest = hashlib.sha256(asc.encode()).hexdigest() if asc else None
    result = {'id': case['id'], 'family': case['family'], 'components': len(source['components']),
              'corpus_case_status': case['overall'], 'corpus_sample': sample['evidence_directory'],
              'status': 'FAIL', 'asc_sha256': digest, 'matches_corpus': digest == sample.get('asc_sha256'),
              'diagnostics': [d.format() for d in diagnostics], 'pipeline_metrics': metrics}
    results.append(result)
    if asc and result['matches_corpus']:
        path = directory / 'circuit.asc'
        path.write_text(asc, encoding='utf-8', newline='\n')
        model = build_connectivity(source)
        layouts = place_components(source['components'], model)
        result['geometry'] = measure_routing(routed.net_geometries, layouts=layouts, crossings=routed.crossings)
        expected = {net.name: [pin.key for pin in net.pins] for net in model.nets}
        expected.update({f'unwired:{pin.key}': [pin.key] for pin in model.unconnected_pins()})
        (directory / 'expected.json').write_text(json.dumps(expected, indent=2) + '\n')
        try:
            netlist = run_ltspice_netlist(path, directory / 'native', timeout=30)
            actual = parse_netlist(asc, read_ltspice_text(netlist))
            result['native_partition'] = compare_partitions(expected, actual).to_dict()
            result['status'] = 'PASS' if result['native_partition']['ok'] else 'FAIL'
            if len(source['components']) >= 100:
                render = asdict(render_asc(path, directory / 'schematic.png', heading=case['name']))
                render['output_path'] = str(render['output_path'])
                render['symbol_root'] = str(render['symbol_root'])
                render['symbol_paths'] = [str(symbol) for symbol in render['symbol_paths']]
                result['render'] = render
        except Exception as exc:
            result['status'] = 'FAIL'
            result['error'] = f'{type(exc).__name__}: {exc}'
    (output / 'report.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
print(json.dumps([{k: row[k] for k in ('id', 'family', 'components', 'status', 'matches_corpus')} for row in results], indent=2))
sys.exit(0 if results and all(row['status'] == 'PASS' for row in results) else 1)

"""Reproduce the final evidence view without rerunning or reclassifying attempts."""
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend'))
from tools.circuit_corpus import execution_catalog, fresh_directory, summarize, write_json
from tools.corpus_catalog import enrich_catalog, enrich_report, write_category_indexes

RUNS = ROOT / 'backend/tests/corpus/runs'
COLLECTION = RUNS / 'phase10-acceptance-collection'
SOURCES = ('phase10-acceptance', 'phase10-drift-recheck')


def main():
    catalog = json.loads((COLLECTION / 'catalog.json').read_text())
    reports = [json.loads((RUNS / name / 'corpus_report.json').read_text()) for name in SOURCES]
    expected = {case['id'] for case in reports[0]['cases'] if not case['implementation_stable']}
    actual = {case['id'] for case in reports[1]['cases']}
    assert expected == actual, (expected, actual)
    assert all(case['implementation_stable'] for case in reports[1]['cases'])
    cases = {}
    for name, report in zip(SOURCES, reports):
        for original in report['cases']:
            case = deepcopy(original)
            case['source_report'] = f'../{name}/corpus_report.json'
            for sample in case['samples']:
                sample['evidence_directory'] = f"{name}/{sample['evidence_directory']}"
            cases[case['id']] = case
    assert set(cases) == {case['id'] for case in catalog['cases']}
    report = deepcopy(reports[0])
    report['cases'] = [cases[case['id']] for case in catalog['cases']]
    report['summary'] = summarize(report['cases'])
    report['evidence_root'] = '..'
    report['consolidation'] = {
        'source_reports': [f'../{name}/corpus_report.json' for name in SOURCES],
        'rerun_ids': sorted(actual),
        'policy': 'Use actual final-code rechecks only for the four implementation-drift cases; retain all original reports. No new passes are inferred.',
        'implementation_scope': 'The full run and recheck snapshots are separate. Final changes add catalog/index reporting and classify missing/empty logging counts as unknown; no placement, routing or serialized geometry change.',
    }
    output = fresh_directory(RUNS / 'phase10-final', 'consolidated')
    validated = enrich_catalog(execution_catalog(catalog, report), COLLECTION, report=report, evidence_root=RUNS)
    report = enrich_report(report, validated)
    write_json(output / 'corpus_report.json', report)
    write_json(output / 'validated_catalog.json', validated)
    write_category_indexes(validated, COLLECTION, output / 'indexes')
    benchmarks = []
    for case in report['cases']:
        if not case['synthetic']:
            continue
        samples = case['samples']
        keys = sorted({key for sample in samples for key in sample.get('pipeline_metrics', {}).get('stagesMs', {})})
        benchmarks.append({
            'id': case['id'], 'family': case['family'], 'components': case['counts']['components'], 'overall': case['overall'],
            'stages': [sample['stages'] for sample in samples],
            'timings_ms': {key: value['median'] for key, value in case['timings_ms'].items()},
            'pipeline_stage_medians_ms': {key: statistics.median(sample['pipeline_metrics']['stagesMs'][key] for sample in samples if key in sample.get('pipeline_metrics', {}).get('stagesMs', {})) for key in keys},
            'counts': [sample['counts'] for sample in samples],
            'routing_metrics': [sample.get('routing_metrics') for sample in samples],
            'memory': {kind: max((sample.get('memory', {}).get(kind) or {}).get('peak_rss_bytes') or 0 for sample in samples) for kind in ('compiler', 'backend')},
            'deterministic_asc': case['deterministic_asc'],
        })
    write_json(output / 'benchmarks.json', benchmarks)
    lines = ['# Complete corpus evidence', '', 'This is a consolidated evidence view, not a new execution.', '', '```json', json.dumps(report['summary'], indent=2), '```', '', '| Circuit | Components | Status | First failure stage | Evidence |', '| --- | ---: | --- | --- | --- |']
    for case in report['cases']:
        stages = ', '.join(sorted({sample['failure_stage'] for sample in case['samples'] if sample.get('failure_stage')})) or 'none'
        lines.append(f"| {case['id']} — {case['name'].replace('|', '/')} | {case['counts']['components']} | {case['overall']} | {stages} | [{case['source_report']}]({case['source_report']}) |")
    (output / 'corpus_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'summary': report['summary']}, indent=2))


if __name__ == '__main__':
    main()

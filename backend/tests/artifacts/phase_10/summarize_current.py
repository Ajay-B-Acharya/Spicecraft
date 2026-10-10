"""Summarize recorded corpus attempts without inferring unexecuted passes."""
from collections import Counter
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
run = ROOT / 'backend/tests/corpus/runs/current-execution'
report = json.loads((run / 'corpus_report.json').read_text())
if not (run / 'invocation.json').is_file():
    raise RuntimeError('Corpus execution is incomplete')


def median(values):
    values = [value for value in values if value is not None]
    return round(statistics.median(values), 3) if values else None


def peak(samples, process):
    values = [sample.get('memory', {}).get(process, {}).get('peak_rss_bytes') for sample in samples]
    values = [value for value in values if value is not None]
    return max(values) / 1048576 if values else None


rows = []
for case in report['cases']:
    if not case.get('synthetic'):
        continue
    samples = case['samples']
    rows.append({'id': case['id'], 'family': case['family'], 'components': case['counts']['components'],
        'status': case['overall'], 'attempt_status': [sample['overall'] for sample in samples],
        'stages': [sample['stages'] for sample in samples],
        'compiler_ms': median(sample['timings_ms'].get('compiler_reported') for sample in samples),
        'backend_process_ms': median(sample['timings_ms'].get('backend_process_wall') for sample in samples),
        'pipeline_stages_ms': {stage: median(sample.get('pipeline_metrics', {}).get('stagesMs', {}).get(stage) for sample in samples)
            for stage in sorted({stage for sample in samples for stage in sample.get('pipeline_metrics', {}).get('stagesMs', {})})},
        'backend_peak_mib': peak(samples, 'backend'),
        'routing_metrics': [sample.get('routing_metrics') for sample in samples],
        'diagnostics': [sample.get('failures', []) for sample in samples]})
rows.sort(key=lambda row: (row['components'], row['family']))
attempts = [sample for case in report['cases'] for sample in case['samples']]
result = {'summary': report['summary'],
    'size_classes': dict(Counter(case['catalog_metadata']['size_class'] for case in report['cases'])),
    'failures_by_stage_cases': dict(Counter(next(sample['failure_stage'] for sample in case['samples'] if sample.get('failure_stage'))
        for case in report['cases'] if any(sample.get('failure_stage') for sample in case['samples']))),
    'unstable_cases': [{'id': case['id'], 'name': case['name'], 'status': case['overall'], 'attempts': [sample['overall'] for sample in case['samples']]}
        for case in report['cases'] if case['determinism_status'] != 'OBSERVED'],
    'max_peak_mib': {process: peak(attempts, process) for process in ('backend', 'compiler')},
    'scale': rows}
(run / 'scalability_summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: result[key] for key in ('size_classes', 'failures_by_stage_cases', 'unstable_cases', 'max_peak_mib')}, indent=2))
for row in rows:
    print(row['family'], row['components'], row['status'], row['attempt_status'], row['compiler_ms'], row['pipeline_stages_ms'], row['backend_peak_mib'])

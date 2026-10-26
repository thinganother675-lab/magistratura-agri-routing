# SPDX-License-Identifier: Apache-2.0
"""DEV aggregate baselines; original references preserved, no LLM/model API."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agro_route.mera_set_baselines_20261003 import baseline_expectations
from agro_route.mera_screen_metrics_20261003 import choice_set
from agro_route.mera_screen_analysis_20261003 import validate_claims
from mera_local_screen_20261003 import DEFAULT_SOURCE, validate_source
STUDY = ROOT / 'results/20261003_local_screen_571682f5'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def aggregate(items, refs):
    rows = []
    unresolved = []
    for item in items:
        gold, _, _ = choice_set(refs[item.item_id], item.options)
        if not gold:
            unresolved.append(item.item_id); continue
        rows.append(baseline_expectations(len(item.options), len(gold)))
    methods = ('all_available_options', 'uniform_single_option', 'uniform_nonempty_subset')
    return {'n_expected': len(items), 'n_scored': len(rows), 'reference_issues': len(unresolved),
            'unresolved_ids': unresolved,
            'methods': {method: {metric: sum(r[method][metric] for r in rows) / len(rows) for metric in ('em', 'f1')} for method in methods}}


def main():
    source_sha = json.loads((STUDY / 'protocol_frozen.json').read_text(encoding='utf-8'))['source_sha256']
    items, refs, dev60 = validate_source(DEFAULT_SOURCE, source_sha)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    result = {'run_id': STUDY.name + '_trivial_baselines', 'status': 'DEV', 'private_test_run': False,
              'source_sha256': source_sha, 'code_commit': commit,
              'code_sha256': {p: digest(ROOT / p) for p in ('scripts/mera_trivial_baselines_20261003.py', 'src/agro_route/mera_set_baselines_20261003.py')},
              'dev60': aggregate(dev60, refs), 'dev293': aggregate(items, refs),
              'model_calls': 0, 'random_samples_drawn': 0, 'gold_modified': False,
              'interpretation': 'All-options is a deterministic uninformed baseline; random metrics are analytical expectations over specified uniform distributions, not observed model runs. None uses answer content to choose predictions or tune parameters. F1 alone may reward overprediction; strict EM remains primary.'}
    path = STUDY / 'trivial_baselines.json'; write_new(path, result)
    if digest(DEFAULT_SOURCE) != source_sha:
        raise ValueError('Original benchmark source changed')
    claims = []
    for stage in ('dev60', 'dev293'):
        for method, scores in result[stage]['methods'].items():
            for metric, value in scores.items():
                claims.append({'claim_id': f'{stage}_{method}_{metric}',
                  'statement': stage + ' uninformed baseline ' + method + ' ' + metric + '; deterministic/analytical, no model run',
                  'study_run_id': result['run_id'], 'data_path': path.relative_to(ROOT).as_posix(),
                  'analysis_field': f'/{stage}/methods/{method}/{metric}', 'value': value,
                  'code_commit': commit, 'data_sha256': digest(path), 'status': 'DEV'})
    write_new(ROOT / 'manuscript/CLAIM_PROVENANCE_TRIVIAL_BASELINES_20261003.json',
              {'claims': claims, 'validation': validate_claims(claims, ROOT), 'human_confirmation': 'PENDING'})
    print(json.dumps({'dev60': result['dev60'], 'dev293': result['dev293'], 'model_calls': 0}))


if __name__ == '__main__':
    main()

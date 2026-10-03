# SPDX-License-Identifier: Apache-2.0
"""Bind safe inventory, installed-weight and tensor-type receipts to DEV claims."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agro_route.mera_screen_analysis_20261003 import validate_claims
STUDY = ROOT / 'results/20261003_local_screen_571682f5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')


def main():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    scripts = ['scripts/inspect_local_screen_gguf_20261003.py',
               'scripts/hash_local_screen_weights_20261003.py',
               'scripts/record_screen_auxiliary_provenance_20261003.py']
    code_hashes = {}
    for name in scripts:
        git_bytes = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT)
        if hashlib.sha256(git_bytes).hexdigest() != sha(ROOT / name):
            raise ValueError('Auxiliary executed/analysis code differs from committed source')
        code_hashes[name] = sha(ROOT / name)
    paths = [STUDY / name for name in ('inventory.json', 'installed_weight_checksums.json',
                                     'installed_gguf_tensor_types.json', 'runtime_inventory_review.json')]
    inventory, weights, tensors, runtime = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    indexed = {m['modelKey']: m for m in inventory['cli_models']}
    tensor_by_key = {m['model_key']: m for m in tensors['models']}
    models = []
    for weight in weights['models']:
        key = weight['model_key']; tensor = tensor_by_key[key]
        if tensor['weight_sha256_prior_receipt'] != weight['sha256']:
            raise ValueError('GGUF descriptor and earlier weight checksum do not identify the same file')
        models.append({'model_key': key, 'primary_gguf_bytes': weight['bytes'],
                       'cli_package_bytes': indexed[key]['sizeBytes'], 'weight_sha256': weight['sha256'],
                       'reported_context_max': indexed[key].get('maxContextLength'),
                       'backend_reported_quantization': weight['quantization'],
                       'actual_tensor_types': tensor['tensor_type_histogram'],
                       'gguf_architecture': tensor['metadata'].get('general.architecture')})
    report = {'run_id': STUDY.name + '_inventory', 'status': 'DEV', 'private_test_run': False,
              'created_utc': datetime.now(timezone.utc).isoformat(), 'code_commit': commit,
              'code_sha256': code_hashes, 'code_commit_role': 'Exact versions of inspection/hash/analysis code; earlier receipts retain actual measurement timestamps; not a claim that earlier measurements occurred at this later commit',
              'source_hashes': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in paths},
              'lm_studio_inventory_entries': len(inventory['cli_models']),
              'candidate_configurations': len(inventory['candidate_keys']),
              'api_endpoint': inventory['api_endpoint'], 'hardware': inventory['hardware'],
              'globally_selected_runtime': runtime['globally_selected_runtime'],
              'per_model_runtime_identity': 'UNKNOWN', 'models': models,
              'tensor_inspection_primary_source': tensors['primary_source_url'],
              'gguf_format_reference': tensors['format_reference'],
              'scope': 'CLI package sizes may include projector/support files; primary GGUF hashes are complete. Quantization names are backend labels, tensor composition is measured separately. Stored elements do not establish active MoE parameter counts.'}
    path = STUDY / 'inventory_analysis.json'; write_new(path, report)
    claims = []
    def add(id_, pointer, value, statement):
        claims.append({'claim_id': id_, 'statement': statement, 'study_run_id': report['run_id'],
                       'data_path': str(path.relative_to(ROOT)).replace('\\', '/'), 'analysis_field': pointer,
                       'value': value, 'code_commit': commit, 'data_sha256': sha(path), 'status': 'DEV'})
    for key in ('lm_studio_inventory_entries', 'candidate_configurations', 'api_endpoint', 'globally_selected_runtime'):
        add('inventory_' + key, '/' + key, report[key], 'Observed inventory: ' + key)
    for key in ('cpu', 'gpu', 'ram_total_gib', 'lm_studio_version', 'cli'):
        add('hardware_' + key, '/hardware/' + key, report['hardware'][key], 'Observed hardware/backend: ' + key)
    for i, model in enumerate(models):
        for key in ('primary_gguf_bytes', 'cli_package_bytes', 'weight_sha256', 'reported_context_max',
                    'backend_reported_quantization', 'actual_tensor_types', 'gguf_architecture'):
            add('inventory_' + model['model_key'].replace('/', '_') + '_' + key,
                f'/models/{i}/{key}', model[key], model['model_key'] + ' installed-file evidence: ' + key)
    result = {'run_id': report['run_id'], 'claims': claims, 'validation': validate_claims(claims, ROOT),
              'human_confirmation': 'PENDING'}
    write_new(ROOT / 'manuscript/CLAIM_PROVENANCE_SCREEN_INVENTORY_20261003.json', result)
    print(json.dumps({'inventory_entries': report['lm_studio_inventory_entries'], 'claims': len(claims),
                      'validation': result['validation']}))


if __name__ == '__main__':
    main()

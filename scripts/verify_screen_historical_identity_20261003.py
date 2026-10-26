# SPDX-License-Identifier: Apache-2.0
"""Independently verify two QA-discovered historical Gemma LFS identities."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agro_route.mera_screen_analysis_20261003 import validate_claims
STUDY = ROOT / 'results/20261003_local_screen_571682f5'
REVISIONS = {'gemma-4-12b-it': 'faacc07cd184152e87f520a91e1112947b0751da',
             'gemma-4-26b-a4b-it': 'b68961b3c96e42475123a39fe3f8aa149163cf8b'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def main():
    source = STUDY / 'weight_upstream_identity.json'
    original = json.loads(source.read_text(encoding='utf-8'))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    rows = []
    with httpx.Client(timeout=30, trust_env=False) as client:
        for model in original['models']:
            if model['match']:
                rows.append({**model, 'revision_scope': 'CURRENT_AT_INITIAL_METADATA_CHECK'})
                continue
            revision = REVISIONS[model['model_key']]
            url = 'https://huggingface.co/api/models/' + model['repository'] + '/revision/' + revision
            response = client.get(url, params={'blobs': 'true'}); response.raise_for_status()
            data = response.json()
            if data['sha'] != revision:
                raise ValueError('Historical Hub reference differs from requested commit')
            siblings = [s for s in data['siblings'] if s['rfilename'] == model['file']]
            if len(siblings) != 1:
                raise ValueError('Historical exact file unavailable')
            lfs = siblings[0]['lfs']
            if (lfs.get('sha256') or lfs.get('oid')) != model['installed_sha256'] or lfs['size'] != model['installed_bytes']:
                raise ValueError('Historical installed-file identity mismatch')
            rows.append({'model_key': model['model_key'], 'repository': model['repository'], 'file': model['file'],
                         'installed_sha256': model['installed_sha256'], 'installed_bytes': model['installed_bytes'],
                         'match': True, 'revision_scope': 'HISTORICAL_EXACT_FILE', 'hub_revision': revision,
                         'api_url': url + '?blobs=true', 'api_response_sha256': hashlib.sha256(response.content).hexdigest(),
                         'hub_file_sha256': lfs.get('sha256') or lfs.get('oid'), 'hub_file_bytes': lfs['size'],
                         'pinned_file_url': 'https://huggingface.co/' + model['repository'] + '/blob/' + revision + '/' + quote(model['file'], safe='/'),
                         'checked_utc': datetime.now(timezone.utc).isoformat()})
    result = {'run_id': STUDY.name + '_upstream', 'status': 'DEV', 'private_test_run': False,
              'code_commit': commit, 'source_sha256': sha(__file__), 'parent_receipt_sha256': sha(source),
              'current_matches': original['matched_files'], 'historical_matches': len(REVISIONS),
              'all_primary_files_verified': all(r['match'] for r in rows), 'verified_files': sum(r['match'] for r in rows),
              'models': rows, 'additional_public_metadata_requests': len(REVISIONS), 'model_downloads': 0,
              'discovery': 'Two historical revisions found by independent bounded metadata-only QA after current8/10 check; verified here without weights or model calls',
              'installation_time_revision': 'UNKNOWN', 'semantic_cause_of_upstream_changes': 'UNKNOWN',
              'scope': 'Exact evaluated GGUF file identities, not base training revision or current latest-model performance'}
    path = STUDY / 'weight_upstream_historical_verified.json'; write_new(path, result)
    claims = []
    def add(id_, pointer, value, statement):
        claims.append({'claim_id': id_, 'statement': statement, 'study_run_id': result['run_id'],
                       'data_path': path.relative_to(ROOT).as_posix(), 'analysis_field': pointer, 'value': value,
                       'code_commit': commit, 'data_sha256': sha(path), 'status': 'DEV'})
    for name in ('current_matches', 'historical_matches', 'all_primary_files_verified', 'verified_files'):
        add('upstream_' + name, '/' + name, result[name], 'Public metadata proves installed GGUF byte identity: ' + name)
    for i, model in enumerate(rows):
        for name in ('installed_sha256', 'installed_bytes', 'pinned_file_url', 'revision_scope'):
            add('upstream_' + model['model_key'].replace('/', '_') + '_' + name, f'/models/{i}/{name}', model[name], model['model_key'] + ' evaluated installed-file provenance: ' + name)
    write_new(ROOT / 'manuscript/CLAIM_PROVENANCE_SCREEN_UPSTREAM_20261003.json',
              {'status': 'DEV', 'claims': claims, 'validation': validate_claims(claims, ROOT), 'human_confirmation': 'PENDING'})
    print(json.dumps({'verified_files': result['verified_files'], 'current': result['current_matches'],
                      'historical': result['historical_matches'], 'model_downloads': 0, 'claim_count': len(claims)}))


if __name__ == '__main__':
    main()

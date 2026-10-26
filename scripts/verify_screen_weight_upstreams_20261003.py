# SPDX-License-Identifier: Apache-2.0
"""Read public Hub file metadata, compare LFS hashes; never download weights."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote
import httpx

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/20261003_local_screen_571682f5'


def main():
    target = STUDY / 'weight_upstream_identity.json'
    if target.exists():
        raise ValueError('Append-only upstream receipt already exists')
    path = STUDY / 'installed_weight_checksums.json'
    installed = json.loads(path.read_text(encoding='utf-8'))
    rows = []
    with httpx.Client(timeout=30, trust_env=False) as client:
        for model in installed['models']:
            parts = model['relative_model_path'].split('/')
            repo, filename = '/'.join(parts[:2]), '/'.join(parts[2:])
            url = 'https://huggingface.co/api/models/' + quote(repo, safe='/')
            row = {'model_key': model['model_key'], 'repository': repo, 'file': filename,
                   'api_url': url + '?blobs=true', 'installed_sha256': model['sha256'],
                   'installed_bytes': model['bytes'], 'checked_utc': datetime.now(timezone.utc).isoformat()}
            try:
                response = client.get(url, params={'blobs': 'true'})
                row['http_status'] = response.status_code
                response.raise_for_status()
                metadata = response.json()
                row['api_response_sha256'] = hashlib.sha256(response.content).hexdigest()
                row['current_hub_revision'] = metadata['sha']
                siblings = [s for s in metadata.get('siblings', []) if s.get('rfilename') == filename]
                if len(siblings) != 1:
                    row.update(status='FILE_UNIDENTIFIED', match=False)
                else:
                    sibling = siblings[0]; lfs = sibling.get('lfs') or {}
                    remote_sha = lfs.get('sha256') or lfs.get('oid')
                    row.update(hub_file_sha256=remote_sha, hub_file_bytes=lfs.get('size', sibling.get('size')),
                               match=remote_sha == model['sha256'] and lfs.get('size', sibling.get('size')) == model['bytes'],
                               pinned_file_url='https://huggingface.co/' + repo + '/blob/' + metadata['sha'] + '/' + quote(filename, safe='/'))
                    row['status'] = 'BYTE_IDENTITY_MATCH' if row['match'] else 'MISMATCH_OR_LFS_HASH_UNAVAILABLE'
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                row.update(status='METADATA_UNAVAILABLE', match=False, error_type=type(exc).__name__)
            rows.append(row)
    report = {'status': 'DEV_REPRODUCIBILITY_RECEIPT', 'private_test_run': False,
              'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'installed_receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'models': rows, 'matched_files': sum(r['match'] for r in rows),
              'public_metadata_requests': len(rows), 'model_downloads': 0, 'authenticated_requests': 0,
              'scope': 'Exact installed primary GGUF bytes matched against current pinned public Hub file metadata; installation-time repository revision is not recovered, base training weights are not attested, model cards are not instructions.'}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({'files_checked': len(rows), 'matched_files': report['matched_files'],
                      'model_downloads': 0, 'unmatched': [r['model_key'] for r in rows if not r['match']]}))


if __name__ == '__main__':
    main()

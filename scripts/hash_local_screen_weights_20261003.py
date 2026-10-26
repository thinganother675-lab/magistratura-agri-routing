# SPDX-License-Identifier: Apache-2.0
"""Read installed candidate weights sequentially; save checksums, never weights."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/20261003_local_screen_571682f5'

def main():
    target = STUDY / 'installed_weight_checksums.json'
    if target.exists():
        raise ValueError('Append-only checksum record already exists')
    inventory = json.loads((STUDY / 'inventory.json').read_text(encoding='utf-8'))
    model_root = (Path.home() / '.lmstudio/models').resolve()
    chosen = set(inventory['candidate_keys'])
    receipts = []
    for model in inventory['cli_models']:
        if model['modelKey'] not in chosen:
            continue
        path = (model_root / model['path']).resolve()
        if not path.is_relative_to(model_root) or not path.is_file():
            raise ValueError('Installed model path unavailable or outside model root')
        before = path.stat()
        started = time.perf_counter()
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Model file changed during hashing')
        receipts.append({'model_key': model['modelKey'], 'relative_model_path': model['path'],
                         'bytes': before.st_size, 'sha256': checksum,
                         'quantization': model.get('quantization'),
                         'hash_duration_s': time.perf_counter()-started})
        print(json.dumps({'hashed': model['modelKey'], 'bytes': before.st_size}), flush=True)
    report = {'status': 'DEV_REPRODUCIBILITY_RECEIPT', 'utc': datetime.now(timezone.utc).isoformat(),
              'candidate_count': len(receipts), 'models': receipts,
              'weights_copied_or_modified': False, 'upstream_revision_claimed': False,
              'scope': 'Installed primary weight files; separate projector/runtime files are not attested'}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')

if __name__ == '__main__':
    main()

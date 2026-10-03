# SPDX-License-Identifier: Apache-2.0
"""Archive exact executed local-screen code and imported helpers, no data text."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '3bbe24410cdc42d74edd2791cd7b5862e2848987'
FILES = (
    'scripts/mera_local_screen_20261003.py', 'src/agro_route/mera_screen_metrics_20261003.py',
    'src/agro_route/home_config.py', 'src/agro_route/mera_adapter_20261003.py',
    'scripts/home_pc_benchmark.py', 'scripts/home_lm_api_benchmark.py',
    'scripts/mera_dev_20261003.py', 'src/agro_route/models.py',
    'src/agro_route/evaluation.py', 'src/agro_route/routing.py', 'src/agro_route/tools.py',
)

def main():
    target = ROOT / 'experiments/mera_local_screen_code_20261003'
    if target.exists():
        raise ValueError('Append-only code archive already exists')
    blobs = {}
    for name in FILES:
        data = subprocess.check_output(['git', '-C', str(ROOT), 'show', COMMIT+':'+name])
        if (ROOT / name).read_bytes() != data:
            raise ValueError('Working helper/source differs from execution commit: '+name)
        blobs[name] = data
    target.mkdir()
    records = []
    for name, data in blobs.items():
        archive_name = name.replace('/', '__')+'.txt'
        with (target / archive_name).open('xb') as stream:
            stream.write(data)
        records.append({'source_path': name, 'archive_path': archive_name,
                        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                        'working_equals_execution_commit': True})
    receipt = {'classification': 'DEV', 'execution_code_commit': COMMIT,
               'run_id': '20261003_local_screen_571682f5', 'sources': records,
               'benchmark_questions_gold_or_model_outputs_in_archive': False,
               'scope': 'Runner, strict metrics, imported native/RAM helpers and their project imports; downstream analysis separately hashed'}
    with (target / 'source_index.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': 'PASS', 'sources': len(records), 'execution_code_commit': COMMIT}))

if __name__ == '__main__':
    main()

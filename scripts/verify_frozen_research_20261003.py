# SPDX-License-Identifier: Apache-2.0
"""Compare every pre-continuation research artifact with Git; never extract tar."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '420c3eccf46b4a233780b62b5fda86cf7f5f1e80'
STUDY = ROOT / 'results/20261003_mera_agro_routing_3de88b82'


def main():
    archive = subprocess.check_output(['git', 'archive', '--format=tar', BASELINE, '--',
                                       'data', 'results', 'experiments', 'manuscript'], cwd=ROOT)
    hashes, failures = {}, []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as stream:
        for member in stream.getmembers():
            if not member.isfile():
                continue
            relative = Path(member.name)
            path = (ROOT / relative).resolve()
            assert path.is_relative_to(ROOT)
            recorded = hashlib.sha256(stream.extractfile(member).read()).hexdigest()
            hashes[member.name] = recorded
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
                failures.append(member.name)
    assert not failures, repr(failures)
    local_cleanup = {}
    for profile in ('gemma-4-26b-a4b-it', 'qwen3.8-27b'):
        manifest = json.loads((STUDY / (profile + '_dev_manifest.json')).read_text(encoding='utf-8'))
        assert manifest['provider'] == 'local' and manifest['own_instance_cleanup_success'] is True
        local_cleanup[profile] = True
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS',
              'pre_continuation_commit': BASELINE, 'pre_continuation_research_files': len(hashes),
              'failures': failures,
              'review40_files': {name: value for name, value in hashes.items() if 'review40' in name},
              'manuscript_files_preserved': sum(name.startswith('manuscript/') for name in hashes),
              'own_local_instances_cleanup_verified': local_cleanup,
              'comparison': 'Working file bytes versus git archive baseline; archive parsed in memory without extraction'}
    with (STUDY / 'continuation_integrity.json').open('x', encoding='utf-8') as out:
        out.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'pre_continuation_research_files', 'failures', 'manuscript_files_preserved')}))


if __name__ == '__main__':
    main()

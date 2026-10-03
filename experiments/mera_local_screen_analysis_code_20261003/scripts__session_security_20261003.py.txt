"""Read-only security/history and preservation checks; never serialize secrets."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile
import scan_public_artifacts as scanner

ROOT = Path(__file__).resolve().parents[1]
BASE = '63b481475653bb13a9e111526019adf16a4ce672'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def inspect_bytes(data, label, secrets):
    if data.startswith((b'%PDF-', b'\x89PNG', b'\xff\xd8', b'RIFF')) or b'\0' in data[:4096]:
        return []
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return [{'path': label, 'rule': 'unreadable_nonbinary'}]
    hits = [{'path': label, 'rule': rule} for rule, pattern in scanner.PATTERNS.items()
            if pattern.search(content)]
    for match in scanner.ASSIGNMENT.finditer(content):
        if match.group(1).lower() not in scanner.PLACEHOLDERS:
            hits.append({'path': label, 'rule': 'literal_credential_assignment'})
    if any(value in content for value in secrets):
        hits.append({'path': label, 'rule': 'configured_secret_exact_match'})
    return hits

def history_blobs(objects):
    records = [line.partition(' ') for line in objects]
    labels = {oid: label for oid, _, label in records}
    request = ''.join(oid+'\n' for oid, _, _ in records).encode()
    checked = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '--batch-check'],
                             input=request, capture_output=True, check=True).stdout
    ids = [line.split()[0] for line in checked.decode().splitlines() if line.split()[1] == 'blob']
    for start in range(0, len(ids), 32):
        response = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '--batch'],
            input=('\n'.join(ids[start:start+32])+'\n').encode(), capture_output=True, check=True).stdout
        stream = io.BytesIO(response)
        while header := stream.readline():
            oid, kind, size = header.decode().split()
            assert kind == 'blob'
            data = stream.read(int(size))
            assert len(data) == int(size) and stream.read(1) == b'\n'
            yield labels[oid], data

def audit():
    secrets = scanner.configured_secret_values(ROOT)
    # Include project keys with numbered names, without printing or hashing them.
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name, value = line.split('=', 1)
            if 'key' in name.lower() or 'token' in name.lower():
                value = value.strip().strip('\"\'')
                if len(value) >= 8:
                    secrets.add(value)
    objects = git('rev-list', '--objects', '--all').decode('utf-8').splitlines()
    findings, archive_members, blobs, max_bytes = [], 0, 0, 0
    for label, data in history_blobs(objects):
        blobs += 1
        max_bytes = max(max_bytes, len(data))
        if scanner.sensitive_filename(Path(label)):
            findings.append({'path': label, 'rule': 'sensitive_filename'})
        if len(data) >= 50 * 1024**2:
            findings.append({'path': label, 'rule': 'large_blob'})
        findings.extend(inspect_bytes(data, label, secrets))
        if label.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as stream:
                for entry in stream.infolist():
                    if not entry.is_dir():
                        archive_members += 1
                        findings.extend(inspect_bytes(stream.read(entry), label+'!'+entry.filename, secrets))
        elif label.endswith(('.tar.gz', '.tgz')):
            with tarfile.open(fileobj=io.BytesIO(data)) as stream:
                for entry in stream.getmembers():
                    if entry.isfile():
                        archive_members += 1
                        findings.extend(inspect_bytes(stream.extractfile(entry).read(), label+'!'+entry.name, secrets))
    paths = scanner.publication_paths(ROOT, all_tracked=True)
    for path in paths:
        label = path.relative_to(ROOT).as_posix()
        if scanner.sensitive_filename(path):
            findings.append({'path': label, 'rule': 'sensitive_filename'})
        findings.extend(inspect_bytes(path.read_bytes(), label, secrets))
    for oid in git('rev-list', '--all').decode().splitlines():
        findings.extend(inspect_bytes(git('show', '-s', '--format=%B', oid), 'commit:'+oid, secrets))
    preserved, changed = 0, []
    archive = git('archive', '--format=tar', BASE)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            if member.isfile():
                current = ROOT / member.name
                if not current.is_file() or current.read_bytes() != stream.extractfile(member).read():
                    changed.append(member.name)
                else:
                    preserved += 1
    return {'utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS' if not findings else 'REVIEW',
            'head': git('rev-parse', 'HEAD').decode().strip(), 'reachable_blobs_checked': blobs,
            'current_files_checked': len(paths), 'archive_members_checked': archive_members,
            'largest_blob_bytes': max_bytes, 'findings': findings,
            'preservation_base': BASE, 'preserved_base_files': preserved, 'changed_base_files': changed,
            'secret_values_or_fingerprints_printed': False,
            'limitations': 'Pattern/exact-secret scan; binary pixels and unknown opaque secrets are not certified.'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = (ROOT / args.output).resolve()
    if not target.is_relative_to(ROOT / 'results') or target.exists():
        raise ValueError('Use a new results path')
    report = audit()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=True, indent=2)
        out.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'reachable_blobs_checked', 'current_files_checked',
          'archive_members_checked', 'largest_blob_bytes', 'findings', 'preserved_base_files', 'changed_base_files')}))
    return 0 if not report['findings'] else 1

if __name__ == '__main__':
    raise SystemExit(main())

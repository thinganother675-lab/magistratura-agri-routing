"""Check prospective public Git files without printing secret values.

Default scope: modified tracked files plus untracked, nonignored files. This is
a publication check, not proof that arbitrary secrets cannot exist in text.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KEY_NAMES = {
    'CLOUD_API_KEY', 'LOCAL_API_KEY', 'INCEPTION_API_KEY', 'MERCURY_API_KEY',
    'JEV_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'HF_TOKEN',
    'HUGGING_FACE_HUB_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN',
}
PATTERNS = {
    'private_key_block': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'openai_anthropic_key': re.compile(r'(?<![\w-])sk-(?:ant-)?[A-Za-z0-9_-]{20,}'),
    'huggingface_token': re.compile(r'(?<!\w)hf_[A-Za-z0-9]{20,}'),
    'github_token': re.compile(r'(?<!\w)(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})'),
    'telegram_bot_token': re.compile(r'(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}'),
    'aws_access_key_id': re.compile(r'(?<!\w)(?:AKIA|ASIA)[A-Z0-9]{16}(?!\w)'),
    'literal_bearer_token': re.compile(r'(?i)Bearer\s+[A-Za-z0-9_.-]{24,}'),
}
ASSIGNMENT = re.compile(
    r'''(?im)(?:^\s*|[\s,{])['"]?(?:''' + '|'.join(sorted(KEY_NAMES)) +
    r'''|api_key|access_token|refresh_token)['"]?\s*[:=]\s*['"]?([A-Za-z0-9_./+-]{12,})(?=['"\s,;}]|$)''')
PLACEHOLDERS = {'your_api_key_here', 'your-api-key-here', 'configure_locally',
                'replace_with_your_key', 'test-placeholder', 'not-a-real-key'}


def publication_paths(root: Path, all_tracked: bool = False) -> list[Path]:
    tracked = ['ls-files', '-z'] if all_tracked else ['diff', '--name-only', '-z', 'HEAD']
    commands = [tracked, ['ls-files', '--others', '--exclude-standard', '-z']]
    names: set[str] = set()
    for command in commands:
        result = subprocess.run(['git', '-C', str(root), *command], check=True,
                                capture_output=True, encoding='utf-8', errors='strict')
        names.update(name for name in result.stdout.split('\0') if name)
    return [root / name for name in sorted(names) if (root / name).exists()]


def configured_secret_values(root: Path) -> set[str]:
    # Values are used only for exact matching. Never serialize, hash, or print.
    values = {os.environ[name] for name in KEY_NAMES if os.environ.get(name)}
    dotenv = root / '.env'
    if dotenv.is_file():
        for line in dotenv.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                if name.strip() in KEY_NAMES:
                    values.add(value.strip().strip('"\''))
    return {value for value in values if len(value) >= 8}


def sensitive_filename(path: Path) -> bool:
    name = path.name.lower()
    if name == '.env.example':
        return False
    return (name == '.env' or name.startswith('.env.') or
            path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'} or
            name.startswith(('id_rsa', 'id_ed25519', 'credentials.')) or
            name in {'auth.json', 'cookies.json', 'cookies.txt',
                     'storage_state.json', 'storage-state.json'} or
            bool(re.search(r'service.account.*\.json$', name)))


def inspect_file(root: Path, path: Path, secrets: set[str]) -> list[dict]:
    label = path.relative_to(root).as_posix()
    findings: list[dict] = []
    if path.is_symlink():
        return [{'path': label, 'rule': 'symlink_requires_review', 'line': None}]
    if sensitive_filename(path):
        findings.append({'path': label, 'rule': 'sensitive_filename', 'line': None})
    if path.stat().st_size > 64 * 1024 * 1024:
        findings.append({'path': label, 'rule': 'oversize_file_requires_review', 'line': None})
        return findings
    data = path.read_bytes()
    if b'\0' in data[:4096]:
        return findings  # Binary artifacts: filename checked, textual scan inapplicable.
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        findings.append({'path': label, 'rule': 'unreadable_text_requires_review', 'line': None})
        return findings
    for rule, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            findings.append({'path': label, 'rule': rule,
                             'line': content.count('\n', 0, match.start()) + 1})
    for match in ASSIGNMENT.finditer(content):
        if match.group(1).lower() not in PLACEHOLDERS:
            findings.append({'path': label, 'rule': 'literal_credential_assignment',
                             'line': content.count('\n', 0, match.start()) + 1})
    for secret in secrets:
        start = content.find(secret)
        if start >= 0:
            findings.append({'path': label, 'rule': 'configured_secret_exact_match',
                             'line': content.count('\n', 0, start) + 1})
    return sorted(findings, key=lambda row: (row['line'] or 0, row['rule']))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-tracked', action='store_true',
                        help='Also scan every tracked file, useful for first public release.')
    args = parser.parse_args()
    paths = publication_paths(ROOT, args.all_tracked)
    secrets = configured_secret_values(ROOT)
    findings = [finding for path in paths for finding in inspect_file(ROOT, path, secrets)]
    report = {'scope': 'all tracked plus nonignored untracked' if args.all_tracked else
              'Git modified plus nonignored untracked',
              'files_checked': len(paths), 'findings': findings,
              'secret_values_printed': False,
              'limitation': 'Pattern and configured-secret checks do not prove absence of every possible secret.'}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())

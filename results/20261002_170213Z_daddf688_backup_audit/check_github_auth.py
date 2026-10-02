"""Use the legitimate Git credential provider internally; persist no credential.

This script performs only GET preflight by default. --create-private is allowed
only after the adjacent completed secret audit passes and Apartman36 is verified.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TARGET = 'Apartman36/magistratura-agri-routing'
parser = argparse.ArgumentParser()
parser.add_argument('--create-private', action='store_true')
args = parser.parse_args()
report = {
    'checked_utc': datetime.now(timezone.utc).isoformat(),
    'credential_source': 'existing configured Git Credential Manager',
    'credential_values_or_fingerprints_persisted': False,
    'target': TARGET, 'identity': None, 'repository': None,
    'status': 'BLOCKED', 'git_global_config_changed': False,
    'creation_requested': args.create_private,
}

def finish(name='github_auth_preflight.json'):
    (OUT/name).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))

env = os.environ.copy()
env.update({'GIT_TERMINAL_PROMPT':'0', 'GCM_INTERACTIVE':'never'})
try:
    fetched = subprocess.run(
        ['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\nusername=Apartman36\n\n',
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=25,
    )
except subprocess.TimeoutExpired:
    report['blocker'] = 'Existing Git credential lookup exceeded 25 seconds; no browser authentication attempted.'
    finish(); raise SystemExit(2)
report['credential_fill_exit_code'] = fetched.returncode
if fetched.returncode:
    report['blocker'] = 'Existing Git credential provider did not return a usable credential with interaction disabled.'
    finish(); raise SystemExit(2)
fields = dict(line.split('=', 1) for line in fetched.stdout.splitlines() if '=' in line)
credential = fields.get('password')
if not credential:
    report['blocker'] = 'Configured Git provider returned no password/token field.'
    finish(); raise SystemExit(2)
try:
    with httpx.Client(timeout=25, trust_env=True, headers={
        'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28',
        'Authorization':'Bearer '+credential,
    }) as client:
        user = client.get('https://api.github.com/user')
        report['identity_http_status'] = user.status_code
        if user.status_code != 200:
            report['blocker'] = 'Existing Git credential was not accepted by GitHub REST identity endpoint.'
            finish(); raise SystemExit(2)
        identity = user.json().get('login')
        report['identity'] = identity
        if identity != 'Apartman36':
            report['blocker'] = 'Authenticated identity is not the user-authorized Apartman36 account.'
            finish(); raise SystemExit(2)
        repo = client.get('https://api.github.com/repos/'+TARGET)
        report['repository_http_status'] = repo.status_code
        if repo.status_code == 404 and args.create_private:
            audit = json.loads((OUT/'security_history_audit.json').read_text(encoding='utf-8'))
            if audit['status'] != 'PASS':
                raise RuntimeError('Security audit does not pass')
            made = client.post('https://api.github.com/user/repos', json={
                'name':'magistratura-agri-routing', 'private':True,
                'description':'Tool-aware local/cloud agricultural QA research: preserved experimental history',
                'auto_init':False,
            })
            report['create_http_status'] = made.status_code
            if made.status_code != 201:
                report['blocker'] = 'GitHub private-repository creation was refused; no token or response body persisted.'
                finish('github_create_private.json'); raise SystemExit(2)
            repo = client.get('https://api.github.com/repos/'+TARGET)
            report['repository_http_status'] = repo.status_code
        if repo.status_code == 200:
            data = repo.json()
            report['repository'] = {key:data.get(key) for key in (
                'full_name','html_url','private','visibility','default_branch','size','empty','permissions')}
            report['status'] = 'PRIVATE_VERIFIED' if data.get('private') is True else 'BLOCKED'
            if data.get('private') is not True:
                report['blocker'] = 'Existing destination is not private; no visibility change authorized.'
            branch = data.get('default_branch') or 'main'
            ref = client.get('https://api.github.com/repos/'+TARGET+'/git/ref/heads/'+branch)
            report['remote_branch_http_status'] = ref.status_code
            report['remote_branch_sha'] = ref.json().get('object',{}).get('sha') if ref.status_code == 200 else None
        elif repo.status_code == 404:
            report['status'] = 'AUTHENTICATED_DESTINATION_ABSENT'
            report['blocker'] = 'Destination absent or not visible. Creation deferred until security scan passes.'
        else:
            report['blocker'] = 'GitHub destination preflight refused; no credential or response body persisted.'
except httpx.HTTPError as exc:
    report['blocker'] = 'HTTPS preflight failed: '+type(exc).__name__
    finish(); raise SystemExit(2)
finish('github_create_private.json' if args.create_private else 'github_auth_preflight.json')

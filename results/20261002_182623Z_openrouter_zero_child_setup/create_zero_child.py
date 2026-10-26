"""One-shot same-account zero-cap inference setup; never log credentials."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import os
import subprocess
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ENV_NAME = 'OPENROUTER_INFERENCE_KEY_ZERO_20261002'
BASE = 'https://openrouter.ai/api/v1'
SAFE_FIELDS = ('limit', 'limit_remaining', 'limit_reset', 'include_byok_in_limit',
               'disabled', 'usage', 'usage_daily', 'usage_weekly', 'usage_monthly',
               'is_free_tier', 'free_model_daily_requests', 'rate_limit',
               'is_management_key', 'is_provisioning_key', 'expires_at')

def now():
    return datetime.now(timezone.utc).isoformat()

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def safe_snapshot(response):
    result = {'http_status': response.status_code, 'checked_utc': now()}
    if response.status_code == 200:
        data = response.json().get('data', {})
        result.update({field: data.get(field) for field in SAFE_FIELDS})
    return result

def main():
    env_path = ROOT / '.env'
    before = env_path.read_bytes()
    ignored = subprocess.run(['git', 'check-ignore', '.env'], cwd=ROOT, capture_output=True).returncode == 0
    if not ignored:
        raise ValueError('ProjectEnvNotIgnored')
    if any(line.split('=', 1)[0].strip() == ENV_NAME for line in before.decode('utf-8-sig').splitlines() if '=' in line):
        raise ValueError('ChildSourceAlreadyExistsNoRotation')
    spec = importlib.util.spec_from_file_location('or_management_source', ROOT / 'scripts/openrouter_screen_20261002.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    management, source = module.read_key(ROOT)
    if not management:
        raise ValueError('MissingExactManagementSource')
    result = {
        'started_utc': now(), 'credential_source_management': source,
        'credential_source_inference': 'project_env:' + ENV_NAME,
        'credential_values_or_fingerprints_persisted': False,
        'child_credentials_saved_only_in_git_ignored_project_env': False,
        'paid_spend_cap_usd': 0, 'account_or_quota_rotation': False,
        'generation_attempts': 0, 'metadata_requests': 0, 'setup_mutations': 0,
        'account_changes': 'ONE same-account regular inference key only',
        'privacy_preferences_changed': False,
        'sources': [
            'https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key',
            'https://openrouter.ai/docs/guides/overview/auth/management-api-keys',
            'https://openrouter.ai/docs/api/reference/limits'],
    }
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        preflight = client.get(BASE + '/key', headers={'Authorization': 'Bearer ' + management})
        result['metadata_requests'] += 1
        result['management_before'] = safe_snapshot(preflight)
        if preflight.status_code != 200 or preflight.json().get('data', {}).get('is_management_key') is not True:
            result['status'] = 'BLOCKED_MANAGEMENT_PREFLIGHT'
            write('setup_summary.json', result)
            return
        request = {'name': 'magistratura free-only research 20261002', 'limit': 0,
                   'limit_reset': None, 'include_byok_in_limit': True,
                   'expires_at': '2026-10-09T23:59:59Z'}
        with (OUT / 'creation_claim.json').open('x', encoding='utf-8') as claim:
            json.dump({'claimed_utc': now(), 'request': request,
                       'no_automatic_retry_or_key_rotation': True}, claim, indent=2)
        # A single POST; unknown outcome must never create a replacement key.
        try:
            response = client.post(BASE + '/keys', headers={'Authorization': 'Bearer ' + management}, json=request)
        except httpx.HTTPError as error:
            result.update(status='CREATION_OUTCOME_UNKNOWN_DO_NOT_RETRY', error=type(error).__name__)
            write('setup_summary.json', result)
            return
        result['setup_mutations'] = 1
        result['creation_http_status'] = response.status_code
        if response.status_code != 201:
            result['status'] = 'CREATION_REJECTED_NO_RETRY'
            write('setup_summary.json', result)
            return
        body = response.json()
        child = body.get('key')
        data = body.get('data', {})
        result['created_metadata'] = {field: data.get(field) for field in SAFE_FIELDS}
        if not isinstance(child, str) or not child or '\r' in child or '\n' in child:
            result['status'] = 'INVALID_CREATION_RESPONSE_NO_RETRY'
            write('setup_summary.json', result)
            return
        if env_path.read_bytes() != before:
            # Never overwrite another local credential writer. Keep the returned
            # one-time secret in a dedicated ignored local env instead.
            fallback = ROOT / '.env.openrouter-zero-20261002'
            with fallback.open('x', encoding='utf-8') as handle:
                handle.write(ENV_NAME + '=' + child + '\n')
            result['credential_source_inference'] = 'local_env_file:.env.openrouter-zero-20261002:' + ENV_NAME
        else:
            newline = b'' if before.endswith(b'\n') else b'\r\n'
            with env_path.open('ab') as handle:
                handle.write(newline + (ENV_NAME + '=' + child + '\r\n').encode('utf-8'))
                handle.flush()
                os.fsync(handle.fileno())
            result['original_project_env_bytes_preserved_as_prefix'] = env_path.read_bytes().startswith(before)
        result['child_credentials_saved_only_in_git_ignored_project_env'] = True
        check = client.get(BASE + '/key', headers={'Authorization': 'Bearer ' + child})
        result['metadata_requests'] += 1
        result['child_key'] = safe_snapshot(check)
        management_after = client.get(BASE + '/key', headers={'Authorization': 'Bearer ' + management})
        result['metadata_requests'] += 1
        result['management_after'] = safe_snapshot(management_after)
        original_again, source_again = module.read_key(ROOT)
        result['management_key_source_value_unchanged'] = original_again == management and source_again == source
        child_metadata = check.json().get('data', {}) if check.status_code == 200 else {}
        safe_cap = data.get('limit') == 0 and child_metadata.get('limit') == 0
        ordinary = child_metadata.get('is_management_key') is False and child_metadata.get('is_provisioning_key') is False
        result['zero_cap_verified'] = safe_cap
        result['regular_inference_type_verified'] = ordinary
        result['free_completion_eligibility'] = 'UNKNOWN UNTIL FIRST STRICT ZERO-PRICE COMPLETION; limit will not be raised'
        result['free_quota_global_not_new_per_key'] = True
        result['status'] = 'READY_METADATA_ONLY' if safe_cap and ordinary and result['management_key_source_value_unchanged'] else 'BLOCKED_SETUP_VALIDATION'
        result['finished_utc'] = now()
        write('setup_summary.json', result)
        print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'status': result['status'],
                          'creation_http_status': response.status_code, 'child_type_regular': ordinary,
                          'limit_usd': child_metadata.get('limit'), 'generation_attempts': 0}))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception values may include service data; retain the type only.
        write('setup_exception.json', {'checked_utc': now(), 'error_type': type(error).__name__,
                                      'no_automatic_retry': True, 'credential_values_or_fingerprints_persisted': False})
        print(json.dumps({'status': 'SETUP_EXCEPTION', 'error_type': type(error).__name__}))
        raise SystemExit(1)

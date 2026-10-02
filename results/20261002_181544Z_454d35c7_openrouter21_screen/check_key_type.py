"""One legitimate metadata GET, no inference or account changes."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import httpx

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('or_screen_keytype',ROOT/'scripts/openrouter_screen_20261002.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
key,source=helper.read_key()
if not key:raise SystemExit('Exact project credential missing; no calls')
with httpx.Client(timeout=20,trust_env=True,follow_redirects=False) as client:
    r=client.get(helper.BASE+'/key',headers={'Authorization':'Bearer '+key})
    data=r.json().get('data',{}) if r.status_code==200 else {}
report={'checked_utc':datetime.now(timezone.utc).isoformat(),'http_status':r.status_code,
 'credential_source':source,'credential_values_or_fingerprints_persisted':False,
 'is_management_key':data.get('is_management_key'),'is_provisioning_key':data.get('is_provisioning_key'),
 'is_free_tier':data.get('is_free_tier'),'expires_at':data.get('expires_at'),
 'generation_attempts':0,'external_metadata_requests':1,'account_changes':False,
 'scope':'Separate key-type diagnostic; not part of generation benchmark; no label/hash/creator ID persisted',
 'source':'https://openrouter.ai/docs/guides/overview/auth/management-api-keys'}
(HERE/'key_type_diagnostic.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))

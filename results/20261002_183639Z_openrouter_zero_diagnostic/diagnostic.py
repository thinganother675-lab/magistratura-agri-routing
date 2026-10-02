"""ONE explicitly authorized fixed-free connectivity diagnostic; no retry."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import math
import re
import time
import httpx

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
MODEL='liquid/lfm-2.5-2.6b:free'
ENDPOINT='liquid/fp8'
WINDOW='OR_DIAGNOSTIC_ZERO_20261002_1836Z'

def now():return datetime.now(timezone.utc).isoformat()
def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    spec=importlib.util.spec_from_file_location('or_fixed_zero_diagnostic',ROOT/'scripts/openrouter_screen_20261002.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    key,source=module.read_key(source_name='OPENROUTER_INFERENCE_KEY_ZERO_20261002')
    secrets=[]
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line or line.lstrip().startswith('#'):continue
        name,value=line.split('=',1);name=name.upper()
        if any(part in name for part in ('KEY','TOKEN','SECRET','PASSWORD')):
            value=value.strip().strip('"\'')
            if value:secrets.append(value)
    def scrub(value):
        if isinstance(value,str):
            for secret in sorted(secrets,key=len,reverse=True):value=value.replace(secret,'[REDACTED_CREDENTIAL]')
            value=re.sub(r'\bsk-or-v1-[a-zA-Z0-9_-]+','[REDACTED_CREDENTIAL]',value)
            return value
        if isinstance(value,list):return [scrub(item) for item in value]
        if isinstance(value,dict):return {scrub(k):scrub(v) for k,v in value.items()}
        return value
    result={'started_utc':now(),'phase':'CONNECTIVITY_DIAGNOSTIC_NOT_BENCHMARK',
      'measurement_window':WINDOW,'credential_source':source,
      'model_requested':MODEL,'endpoint_pinned':ENDPOINT,'paid_spend_cap_usd':0,
      'generation_attempts':0,'successful_generations':0,'retries':0,
      'privacy_settings_changed':False,'account_key_provider_model_rotation':False,
      'original_401_and_403_runs_preserved':True,'metadata_requests':0,
      'credential_values_or_fingerprints_persisted':False,
      'known_usage':{},'reported_cost_usd':None,'provider_reported':None,
      'source_driver_sha256':hashlib.sha256((ROOT/'scripts/openrouter_screen_20261002.py').read_bytes()).hexdigest()}
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        catalog=client.get(module.BASE+'/models');result['metadata_requests']+=1
        endpoints=client.get(module.BASE+'/models/'+MODEL+'/endpoints');result['metadata_requests']+=1
        quota=module.key_snapshot(client,key);result['metadata_requests']+=1
        write('quota_before.json',scrub(quota));result['quota_before']=quota
        if catalog.status_code!=200 or endpoints.status_code!=200 or quota.get('http_status')!=200:
            result['status']='BLOCKED_METADATA';write('summary.json',scrub(result));return
        models=[m for m in catalog.json().get('data',[]) if m.get('id')==MODEL]
        eps=[ep for ep in (endpoints.json().get('data') or {}).get('endpoints',[]) if module.endpoint_slug(ep)==ENDPOINT]
        if len(models)!=1 or len(eps)!=1 or not MODEL.endswith(':free'):
            result['status']='BLOCKED_EXACT_IDENTITY';write('summary.json',scrub(result));return
        row={'eligible':True,'model':models[0],'selected_endpoint':eps[0]}
        if module.ancillary_charge(models[0]) or not module.all_prices_zero(models[0].get('pricing')) or not module.eligible_endpoint(eps[0],models[0]):
            result['status']='BLOCKED_ZERO_PRICE_POLICY';write('summary.json',scrub(result));return
        if quota.get('limit')!=0 or quota.get('is_management_key') is not False or quota.get('is_provisioning_key') is not False or (quota.get('free_model_daily_requests') or {}).get('remaining',0)<1:
            result['status']='BLOCKED_CREDENTIAL_OR_QUOTA_POLICY';write('summary.json',scrub(result));return
        sample=module.read_dev_samples()[1]
        body=module.payload(row,sample)
        result.update(model_catalog_identity={'id':models[0]['id'],'canonical_slug':models[0].get('canonical_slug'),
                        'pricing':models[0].get('pricing'),'context_length':models[0].get('context_length')},
                      endpoint_metadata={'tag':ENDPOINT,'pricing':eps[0].get('pricing'),
                        'supported_parameters':eps[0].get('supported_parameters')},
                      sample_id=sample['id'],request=body)
        write('config.json',scrub(result))
        with (OUT/'execution_claim.json').open('x',encoding='utf-8') as handle:
            json.dump({'claimed_utc':now(),'model':MODEL,'endpoint':ENDPOINT,'max_attempts':1,
                       'measurement_window':WINDOW,'no_automatic_resume':True},handle,indent=2)
        result['generation_attempts']=1;result['request_started_utc']=now()
        started=time.perf_counter()
        try:
            response=client.post(module.BASE+'/chat/completions',headers={'Authorization':'Bearer '+key},json=body,timeout=45)
            result['latency_seconds']=time.perf_counter()-started;result['http_status']=response.status_code
            # NEVER persist full error body, raw response headers or any key/hash.
            if response.status_code!=200:
                try:error=response.json().get('error') or {}
                except ValueError:error={}
                result['safe_error']={k:scrub(error.get(k)) for k in ('code','message') if isinstance(error.get(k),(str,int,float))}
                result['status']='BLOCKED_HTTP_'+str(response.status_code)
            else:
                body_response=response.json();choices=body_response.get('choices') or []
                content=(choices[0].get('message') or {}).get('content') if choices else None
                result['successful_generations']=int(isinstance(content,str) and bool(content.strip()) and not body_response.get('error'))
                result['status']='CONNECTIVITY_ONLY_SUCCESS' if result['successful_generations'] else 'NO_VALID_GENERATION'
                result['output_text']=scrub(content)
                result['structured_failure']=module.schema_failure(content)
                result['provider_reported']=scrub(body_response.get('provider'))
                result['model_reported']=scrub(body_response.get('model'))
                usage=body_response.get('usage') or {}
                for field in ('prompt_tokens','completion_tokens','total_tokens','cost'):
                    value=usage.get(field)
                    if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0:
                        result['known_usage'][field]=value
                result['reported_cost_usd']=result['known_usage'].get('cost')
                if result['reported_cost_usd'] not in (None,0):result['status']='NONZERO_COST_STOP'
        except (httpx.HTTPError,ValueError,TypeError) as error:
            result.update(status='DIAGNOSTIC_ERROR_NO_RETRY',error_type=type(error).__name__,latency_seconds=time.perf_counter()-started)
        result['request_finished_utc']=now()
        after=module.key_snapshot(client,key);result['metadata_requests']+=1
        result['quota_after']=after;write('quota_after.json',scrub(after))
        result['total_external_requests']=result['metadata_requests']+1
        result['branch_external_requests_total']=105+result['total_external_requests']
        result['branch_generation_attempts_total']=3
        result['measurement_window_released']=True
        write('summary.json',scrub(result))
        print(json.dumps({k:result.get(k) for k in ('status','http_status','generation_attempts','successful_generations','latency_seconds','safe_error','known_usage','reported_cost_usd','branch_external_requests_total')},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as error:
        write('exception.json',{'error_type':type(error).__name__,'no_automatic_retry':True})
        print(json.dumps({'status':'EXCEPTION','error_type':type(error).__name__}));raise SystemExit(1)

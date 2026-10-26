"""Explicit fixed-model OpenRouter DEV screening, with a fail-closed $0 cap.

Metadata-only by default. Credentials use ONLY the newly authorized exact
project variable; no frozen configuration files or old experiments are changed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import time
import uuid
import httpx
from agro_route.evaluation import score
from agro_route.models import SYSTEM_PROMPT, parse_output, public_request

ROOT=Path(__file__).resolve().parents[1]
BASE='https://openrouter.ai/api/v1'
REQUESTED=[
 'inclusionAI: Ling 3.1 Flash','Apodex: Apodex 1.1 Mini (free)',
 'Space Bunny Alpha','inclusionAI: Ling 3.0 Flash Sante (free)',
 'Qwen: Qwen3.8 27B (free)','Dots Studio: Dots3-Note Preview (free)',
 'LiquidAI: LFM2.5-2.6B (free)','NVIDIA: Nemotron 3.5 Lightning (free)',
 'Thinking Machines: Inkling Small (free)','Poolside: Laguna S 2.1 (free)',
 'Thinking Machines: Inkling (free)','Poolside: Laguna XS 2.1 (free)',
 'Cohere: North Mini Code (free)','NVIDIA: Nemotron 3.5 Content Safety (free)',
 'NVIDIA: Nemotron 3 Ultra (free)','NVIDIA: Nemotron 3 Nano Omni (free)',
 'Google: Gemma 4 26B A4B (free)','Google: Gemma 4 31B (free)',
 'Google: Lyria 3 Pro Preview','Google: Lyria 3 Clip Preview',
 'NVIDIA: Nemotron 3 Super (free)',
]
EXACT_HINTS={16:'google/gemma-4-26b-a4b-it:free',17:'google/gemma-4-31b-it:free',
             20:'nvidia/nemotron-3-super-120b-a12b:free'}
SCHEMA={'type':'object','additionalProperties':False,'required':['action','answer','numeric','unit','tool'],
 'properties':{'action':{'type':'string','enum':['ANSWER','ASK_FOR_DATA','ABSTAIN']},
 'answer':{'type':'string'},'numeric':{'type':['number','null']},
 'unit':{'type':['string','null']},'tool':{'type':['string','null']}}}

def now(): return datetime.now(timezone.utc).isoformat()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sanitize(value,key):
    if isinstance(value,str):return value.replace(key,'[REDACTED_CREDENTIAL]') if key else value
    if isinstance(value,list):return [sanitize(v,key) for v in value]
    if isinstance(value,dict):return {sanitize(k,key):sanitize(v,key) for k,v in value.items()}
    return value
def read_key(root=ROOT):
    """Exact variable only; never fall back to the previously invalid key."""
    path=Path(root)/'.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):continue
            name,value=line.split('=',1)
            if name.strip()!='openrouter_api_key_2':continue
            value=value.strip()
            if len(value)>=2 and value[0] in '\"\'' and value[-1]==value[0]:value=value[1:-1]
            if '\n' in value or '\r' in value:raise ValueError('Invalid credential linebreak')
            return value,'project_env:openrouter_api_key_2'
    return '',None
def zero_price(value):
    if isinstance(value,bool) or value is None:return False
    try: d=Decimal(str(value));return d.is_finite() and d==0
    except (InvalidOperation,ValueError):return False
def all_prices_zero(pricing):
    # All present monetary components must be explicit zero. Unknown/null fails.
    return isinstance(pricing,dict) and all(k in pricing for k in ('prompt','completion')) and all(zero_price(v) for v in pricing.values())
def ancillary_charge(model):
    """Metadata token fields can omit a per-song/clip/media charge."""
    text=model.get('description','') or ''
    matches=re.findall(r'(?:priced|costs?|price)[^\n.]{0,45}\$([0-9]+(?:\.[0-9]+)?)',text,re.IGNORECASE)
    return any(Decimal(value)>0 for value in matches)
def normalized_name(value):return re.sub(r'[^a-z0-9]','',value.lower().replace('(free)','').replace(':free',''))
def resolve_requested(index,name,catalog):
    free='(free)' in name.lower()
    matches=[m for m in catalog if normalized_name(m.get('name',''))==normalized_name(name)
             and (not free or m['id'].endswith(':free'))]
    if not matches and index in EXACT_HINTS:
        matches=[m for m in catalog if m['id']==EXACT_HINTS[index]]
    if len(matches)!=1:return None,[m['id'] for m in matches]
    return matches[0],[]
def endpoint_slug(ep):return ep.get('tag') or ep.get('provider_slug') or ep.get('provider_name')
def eligible_endpoint(ep,model):
    params=ep.get('supported_parameters',model.get('supported_parameters',[]))
    return all_prices_zero(ep.get('pricing')) and isinstance(endpoint_slug(ep),str) and all(p in params for p in ('max_tokens','temperature'))
def key_snapshot(client,key):
    try:
        r=client.get(BASE+'/key',headers={'Authorization':'Bearer '+key})
        result={'retrieved_utc':now(),'http_status':r.status_code}
        if r.status_code==200:
            data=r.json().get('data',{})
            # Exclude label, hash, creator ID and any credential-like field.
            result.update({k:data.get(k) for k in ('limit','limit_remaining','limit_reset','usage','usage_daily',
              'usage_weekly','usage_monthly','is_free_tier','free_model_daily_requests','rate_limit')})
        return sanitize(result,key)
    except httpx.HTTPError as e:return {'retrieved_utc':now(),'error':type(e).__name__}
def metadata(client,key,output):
    r=client.get(BASE+'/models');r.raise_for_status();body=sanitize(r.json(),key)
    write(output/'catalog.json',{'retrieved_utc':now(),'url':BASE+'/models','response':body})
    quota=key_snapshot(client,key) if key else {'http_status':None,'error':'MissingExactProjectCredential','retrieved_utc':now()}
    write(output/'quota_before.json',quota)
    rows=[]
    for index,name in enumerate(REQUESTED):
        model,ambiguous=resolve_requested(index,name,body.get('data',[]))
        row={'requested_display_name':name,'resolved_model_id':None,'status':'NOT_FOUND','reason':'No unique exact display-name or documented checkpoint match',
             'ambiguous_matches':ambiguous,'model':None,'endpoints':None,'selected_endpoint':None,'eligible':False}
        if model:
            row.update(resolved_model_id=model['id'],model=model,context_length=model.get('context_length'),
              modalities=model.get('architecture'),pricing=model.get('pricing'),created=model.get('created'),
              identity_stability='EXPLORATORY_PREVIEW' if any(x in model['id'] for x in ('stealth/','alpha','preview')) else 'FIXED_CATALOG_ALIAS; remote weight/version immutability UNKNOWN',
              canonical_slug=model.get('canonical_slug'))
            response=client.get(BASE+'/models/'+model['id']+'/endpoints')
            endpoint_body=sanitize(response.json(),key) if response.status_code==200 else None
            write(output/f'endpoints_{index+1:02d}.json',{'retrieved_utc':now(),'url':BASE+'/models/'+model['id']+'/endpoints','http_status':response.status_code,'response':endpoint_body})
            row['endpoints']=endpoint_body
            if ancillary_charge(model):
                row.update(status='PAID_NOT_AUTHORIZED',reason='Description discloses an ancillary media/item charge despite zero token fields; $0 cap blocks request',ancillary_price_warning=True)
            elif 'text' not in model.get('architecture',{}).get('output_modalities',[]) or 'lyria' in model['id']:
                row.update(status='INCOMPATIBLE_MODALITY',reason='No text output; no media generation authorized')
            elif not all_prices_zero(model.get('pricing')):
                row.update(status='PAID_NOT_AUTHORIZED',reason='At least one listed monetary component nonzero, null or invalid; paid cap $0')
            elif 'content safety' in name.lower():
                row.update(status='SPECIALIZED_NOT_COMPARABLE',reason='Content-safety classifier is not a general agricultural answer generator')
            elif response.status_code!=200:
                row.update(status='NOT_RUN',reason='Endpoint metadata unavailable; strict free/provider validation cannot complete')
            else:
                endpoint_list=(endpoint_body.get('data') or {}).get('endpoints',[])
                choices=[ep for ep in endpoint_list if eligible_endpoint(ep,model)]
                if choices:
                    choices.sort(key=lambda ep:str(endpoint_slug(ep)))
                    row.update(selected_endpoint=choices[0],eligible=True,status='NOT_RUN',reason='Eligible zero-price endpoint; waiting for isolated measurement window')
                    desc=(model.get('description') or '').lower()
                    row['scope']='CODING_SPECIALIZED_SMOKE' if 'code' in name.lower() or 'coding agent model' in desc else 'HEALTH_DOMAIN_TRANSFER_SMOKE' if 'health and medicine-focused' in desc else 'GENERAL_TEXT_DEV'
                else:row.update(status='NOT_RUN',reason='No explicitly all-zero endpoint supports required parameters/provider pin')
            if quota.get('http_status') in (401,403) and row['eligible']:
                row.update(status='AUTH_BLOCKED',reason='Exact new project credential rejected; no inference')
        rows.append(row)
    manifest={'created_utc':now(),'phase':'OPENROUTER_METADATA_ONLY','paid_spend_cap_usd':0,'credential_source':'project_env:openrouter_api_key_2',
      'credential_values_or_fingerprints_persisted':False,'catalog_models_n':len(body.get('data',[])),
      'requested_models_n':len(rows),'rows':rows,'inference_calls':0,'final_holdout_run':False,
      'privacy':'Account/provider privacy preferences not changed; only public/synthetic DEV inputs permitted',
      'metadata_requests':'Catalog+key+one endpoints GET per resolved model; these are external metadata requests, not generative calls'}
    manifest['metadata_requests_n']=2+sum(r['resolved_model_id'] is not None for r in rows)
    write(output/'manifest.json',manifest)
    return manifest,quota
def payload(row,sample):
    model=row['model'];ep=row['selected_endpoint']
    if not row.get('eligible') or ancillary_charge(model) or not all_prices_zero(model.get('pricing')) or not eligible_endpoint(ep,model):
        raise ValueError('Free-only policy rejected this endpoint')
    params=ep.get('supported_parameters',model.get('supported_parameters',[]))
    body={'model':model['id'],'messages':[{'role':'system','content':SYSTEM_PROMPT},
      {'role':'user','content':json.dumps(public_request(sample),ensure_ascii=False)}],
      'temperature':0,'max_tokens':512,'stream':False,
      'provider':{'order':[endpoint_slug(ep)],'only':[endpoint_slug(ep)],'allow_fallbacks':False,
       'require_parameters':True,'max_price':{'prompt':0,'completion':0,'request':0,'image':0}}}
    if 'response_format' in params:
        body['response_format']={'type':'json_schema','json_schema':{'name':'agricultural_response','strict':True,'schema':SCHEMA}} if 'structured_outputs' in params else {'type':'json_object'}
    if 'reasoning' in params:body['reasoning']={'enabled':False}
    if 'seed' in params:body['seed']=42
    return body
def read_dev_samples():
    import importlib.util
    spec=importlib.util.spec_from_file_location('home_selector_orscreen',ROOT/'scripts/home_pc_benchmark.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    samples=helper.choose_samples(12)
    if len(samples)!=12 or any(s.get('split')!='dev' for s in samples):raise ValueError('Expected immutable DEV12 selector')
    return samples
def schema_failure(content):
    """Measure exact JSON/schema reliability separately from tolerant scoring."""
    if not isinstance(content,str):return 'NoText'
    try:obj=json.loads(content)
    except (ValueError,TypeError):return 'InvalidExactJSON'
    if not isinstance(obj,dict) or set(obj)!=set(SCHEMA['required']):return 'FieldsMismatch'
    if obj['action'] not in ('ANSWER','ASK_FOR_DATA','ABSTAIN') or not isinstance(obj['answer'],str):return 'ActionOrAnswerType'
    if obj['numeric'] is not None and (isinstance(obj['numeric'],bool) or not isinstance(obj['numeric'],(int,float)) or not math.isfinite(obj['numeric'])):return 'NumericType'
    if any(obj[k] is not None and not isinstance(obj[k],str) for k in ('unit','tool')):return 'UnitOrToolType'
    return None
def rows_summary(rows):
    lat=[r['latency_seconds'] for r in rows if isinstance(r.get('latency_seconds'),(int,float))]
    successful=[r for r in rows if r.get('http_status')==200 and r.get('error') is None]
    usage=[r.get('usage') or {} for r in rows]
    def known(field):
        values=[u.get(field) for u in usage]
        values=[v for v in values if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0]
        return {'known_sum':sum(values) if values else None,'coverage_n':len(values)}
    ordered=sorted(lat)
    p95=ordered[0] if len(ordered)==1 else None
    if len(ordered)>1:
        pos=(len(ordered)-1)*.95;lo=int(pos);p95=ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(pos-lo)
    costs=[r.get('reported_cost_usd') for r in rows]
    return {'attempts':len(rows),'successful_generations':len(successful),
      'correct':sum(r.get('score',{}).get('correct') is True for r in rows),
      'accuracy_all_attempts':sum(r.get('score',{}).get('correct') is True for r in rows)/len(rows) if rows else None,
      'errors':sum(r.get('error') is not None for r in rows),'structured_failures':sum(r.get('parse_error') is not None or r.get('schema_error') is not None for r in rows),
      'mean_latency_seconds':statistics.mean(lat) if lat else None,'p50_latency_seconds':statistics.median(lat) if lat else None,'p95_latency_seconds':p95,
      'known_input_tokens':known('prompt_tokens'),'known_output_tokens':known('completion_tokens'),
      'reported_cost_known_sum_usd':sum(c for c in costs if isinstance(c,(int,float)) and math.isfinite(c)) if any(isinstance(c,(int,float)) for c in costs) else None,
      'unknown_cost_events':sum(c is None for c in costs),'ttft_seconds':None,'tokens_per_second':None,
      'resource_vram_ram_gpu_offload':'NOT_APPLICABLE: remote service; actual allocation UNKNOWN',
      'providers_reported':sorted({r['provider_reported'] for r in rows if r.get('provider_reported')}),
      'by_language':{lang:{'n':sum(r['language']==lang for r in rows),'correct':sum(r['language']==lang and r.get('score',{}).get('correct') is True for r in rows)} for lang in ('en','ru')}}
def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
def stable_general(row):
    slug=row['resolved_model_id']
    return row.get('scope')=='GENERAL_TEXT_DEV' and not any(x in slug for x in ('stealth/','alpha','preview'))
def choose_shortlist(candidates,records):
    """Exploratory two-probe priority, not a claim of robust quality ranking."""
    good=[r for r in candidates if stable_general(r) and len(records[r['resolved_model_id']])==2
          and all(x.get('error') is None and x.get('parse_error') is None and x.get('schema_error') is None for x in records[r['resolved_model_id']])]
    scored=[(r,rows_summary(records[r['resolved_model_id']])) for r in good]
    ranked=sorted(scored,key=lambda pair:(-pair[1]['correct'],pair[1]['mean_latency_seconds'],pair[0]['resolved_model_id']))
    result=[]
    if ranked:result.append(ranked[0][0])
    speed=sorted(scored,key=lambda pair:(pair[1]['mean_latency_seconds'],-pair[1]['correct'],pair[0]['resolved_model_id']))
    result.extend(pair[0] for pair in speed if pair[0] not in result)
    return result[:2]
def run_screen(client,key,metadata_dir,out,window):
    metadata_dir=Path(metadata_dir).resolve()
    out=Path(out).resolve()
    original=json.loads((metadata_dir/'manifest.json').read_text(encoding='utf-8'))
    # Revalidate current catalogue, ancillary charges and ALL endpoint components
    # before any inference; preserve the first snapshot unchanged.
    fresh_dir=out/'pre_inference_metadata';fresh_dir.mkdir()
    source,quota=metadata(client,key,fresh_dir)
    candidates=[]
    for row in source['rows']:
        if row.get('model') and ancillary_charge(row['model']):
            row.update(eligible=False,selected_endpoint=None,status='PAID_NOT_AUTHORIZED',reason='Ancillary media fee in description despite zero token prices; no request')
        if row.get('eligible'):candidates.append(row)
    write(out/'eligibility_v2.json',source)
    write(out/'quota_before.json',quota)
    remaining=(quota.get('free_model_daily_requests') or {}).get('remaining')
    def blocked_summary(status,reason):
        rows=[]
        for row in source['rows']:
            base={k:row.get(k) for k in ('requested_display_name','resolved_model_id','scope','identity_stability','context_length','modalities','pricing','status','reason')}
            base.update(rows_summary([]),endpoint_pinned=endpoint_slug(row['selected_endpoint']) if row.get('selected_endpoint') else None)
            if row.get('eligible'):base.update(status=status,reason=reason)
            rows.append(base)
        initial=original.get('metadata_requests_n',2+sum(r['resolved_model_id'] is not None for r in original['rows']))
        write(out/'summary.json',{'status':status,'stop_reason':reason,'rows':rows,'generation_attempts':0,
          'successful_generations':0,'known_reported_cost_usd':None,'unknown_cost_events':0,
          'metadata_requests_initial':initial,'metadata_requests_screening':source['metadata_requests_n'],
          'total_external_requests':initial+source['metadata_requests_n'],'quota_after':quota,
          'paid_spend_cap_usd':0,'generative_cloud_calls':0,'retries':0})
    if quota.get('http_status')!=200 or not isinstance(remaining,int) or remaining<1:
        blocked_summary('AUTH_BLOCKED' if quota.get('http_status') in (401,403) else 'NOT_RUN','No verified available global free request quota');return
    # Reserve one account-wide request; never manufacture a per-key quota.
    cap=min(49,max(0,remaining-1))
    if cap<len(candidates):
        blocked_summary('NOT_RUN','Quota cannot provide one probe to every eligible candidate; metadata considered all21');return
    claim=metadata_dir/'execution_claim.json'
    with claim.open('x',encoding='utf-8') as f:json.dump({'claimed_utc':now(),'output':out.relative_to(ROOT).as_posix(),'max_generation_attempts':cap,'no_automatic_resume':True},f)
    samples=read_dev_samples();write(out/'samples_dev12.json',samples)
    records={r['resolved_model_id']:[] for r in candidates};calls=0;last=0.;stop=None
    plan={'created_utc':now(),'status':'RUNNING','phase':'EXPLORATORY_DEVELOPMENT','measurement_window':window,
      'paid_spend_cap_usd':0,'max_generation_attempts':cap,'probe_indices':[1,2],
      'extension_indices':[0,3,4,5,6,9,11],'shortlist_max':2,
      'shortlist_selection':'Stable general models with two complete structured probes: highest probe correctness/latency first, fastest different model second; exploratory priority only',
      'minimum_request_spacing_seconds':3.1,'timeout_seconds':45,'concurrency':1,'automatic_retries':0,
      'final_holdout_run':False,'system_prompt':SYSTEM_PROMPT,'benchmark_sha256':hashlib.sha256((ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest(),
      'metadata_directory':metadata_dir.relative_to(ROOT).as_posix(),'public_request_only':True,
      'metadata_reference_sha256':hashlib.sha256((metadata_dir/'manifest.json').read_bytes()).hexdigest(),
      'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'privacy_settings_changed':False,'requests_exclude_gold_category_expected_routes':True}
    write(out/'config.json',plan)
    def attempt(row,sample,stage):
        nonlocal calls,last,stop
        if stop or calls>=cap:return False
        body=payload(row,sample)
        delay=3.1-(time.monotonic()-last)
        if delay>0:time.sleep(delay)
        last=time.monotonic();calls+=1
        rec={'attempt_index':calls,'request_started_utc':now(),'sample_id':sample['id'],'group_id':sample.get('group'),
          'category':sample.get('category'),'language':sample.get('language'),'stage':stage,'model_requested':row['resolved_model_id'],
          'endpoint_pinned':endpoint_slug(row['selected_endpoint']),'request':body,'http_status':None,'error':None,
          'parse_error':None,'schema_error':None,'reported_cost_usd':None,'usage':{},'provider_reported':None,'raw':None,
          'score':{'correct':False},'timing_kind':'LIVE_CLIENT_END_TO_END; includes remote queuing/network; model load UNKNOWN'}
        append(out/'attempts_started.jsonl',sanitize(rec,key))
        started=time.perf_counter()
        try:
            response=client.post(BASE+'/chat/completions',headers={'Authorization':'Bearer '+key},json=body,timeout=45)
            rec['latency_seconds']=time.perf_counter()-started;rec['http_status']=response.status_code
            if response.status_code!=200:
                rec['error']='HTTP_'+str(response.status_code)
                rec['rate_limit_headers']={k:response.headers[k] for k in ('retry-after','x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset') if k in response.headers}
                if response.status_code in (401,403):stop='AUTH_BLOCKED: persistent authentication rejection; no retry'
                elif response.status_code==429:
                    # No retry is safer where the daily/minute reset source is unknown.
                    rec['retry_policy']='No retry: quota/reset source not verified; Retry-After retained for a future versioned trial'
                    stop='RATE_LIMITED: checkpoint; no provider/model/key fallback'
            else:
                raw=sanitize(response.json(),key);rec['raw']=raw;rec['provider_reported']=raw.get('provider');rec['model_reported']=raw.get('model')
                rec['usage']=raw.get('usage') if isinstance(raw.get('usage'),dict) else {}
                cost=rec['usage'].get('cost')
                if isinstance(cost,(int,float)) and not isinstance(cost,bool) and math.isfinite(cost):
                    rec['reported_cost_usd']=cost
                    if cost!=0:rec['error']='UnexpectedNonzeroCost';stop='NONZERO_COST_STOP'
                choices=raw.get('choices') or []
                content=(choices[0].get('message') or {}).get('content') if choices else None
                rec['schema_error']=schema_failure(content)
                rec['finish_reason']=choices[0].get('finish_reason') if choices else None
                try:
                    if not isinstance(content,str):raise ValueError('No text')
                    parsed=parse_output(content);rec['normalized_answer']=parsed;rec['score']=score(sample,parsed)
                except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:rec['parse_error']=type(e).__name__
                if 'error' in raw:rec['error']='ProviderErrorInsideHTTP200'
                rec['server_timing_stats']=raw.get('stats')
        except (httpx.HTTPError,ValueError,TypeError) as e:
            rec['latency_seconds']=time.perf_counter()-started;rec['error']=type(e).__name__
        rec['request_finished_utc']=now()
        records[row['resolved_model_id']].append(rec);append(out/'raw.jsonl',sanitize(rec,key))
        print(json.dumps({k:rec.get(k) for k in ('attempt_index','model_requested','sample_id','http_status','error','parse_error','schema_error','latency_seconds','reported_cost_usd')}) ,flush=True)
        return rec['error'] is None
    # Round-robin probes guarantee all eligible models considered before expansion.
    for row in candidates:
        sample=samples[1]
        if row.get('scope')=='CODING_SPECIALIZED_SMOKE':
            sample={'id':'or_code_dispatch_gdd_20261002','group':'coding_scope_smoke','split':'dev','category':'coding_tool_dispatch','language':'en',
             'input':'A Python dispatcher must choose the function for accumulated growing degree days from daily minimum/maximum temperatures and a base temperature. Return the exact tool identifier.',
             'context':'Available function names: gdd, vpd, et0, rain_deficit.','inputs':{},'expected':{'action':'ANSWER','answers':['gdd']},'scoring':'exact_label'}
        attempt(row,sample,'ONE_CASE_CONNECTIVITY_FORMAT_PROBE')
        if stop:break
    quota_mid=key_snapshot(client,key);write(out/'quota_after_probe.json',quota_mid)
    if not stop and (quota_mid.get('free_model_daily_requests') or {}).get('remaining',0)>len(candidates):
        for row in candidates:
            if row.get('scope')=='GENERAL_TEXT_DEV' and records[row['resolved_model_id']] and records[row['resolved_model_id']][0].get('error') is None:
                attempt(row,samples[2],'SECOND_SHARED_RUSSIAN_MISSING_INPUT_PROBE')
                if stop:break
    quota_second=key_snapshot(client,key);write(out/'quota_after_second_probe.json',quota_second)
    shortlist=choose_shortlist(candidates,records) if not stop else []
    if (quota_second.get('free_model_daily_requests') or {}).get('remaining',0)<len(shortlist)*len(plan['extension_indices'])+1:
        shortlist=[]
    write(out/'shortlist_selection.json',{'selected_utc':now(),'models':[r['resolved_model_id'] for r in shortlist],
       'method':plan['shortlist_selection'],'two_case_quality_is_not_reliable_model_ranking':True})
    for i in plan['extension_indices']:
        for row in shortlist:
            attempt(row,samples[i],'SHARED_DEV9_SHORTLIST_EXTENSION')
            if stop:break
        if stop:break
    summaries=[]
    for row in source['rows']:
        measured=records.get(row['resolved_model_id'],[])
        summary={k:row.get(k) for k in ('requested_display_name','resolved_model_id','scope','identity_stability','context_length','modalities','pricing','status','reason')}
        summary.update(rows_summary(measured),endpoint_pinned=endpoint_slug(row['selected_endpoint']) if row.get('selected_endpoint') else None)
        if measured:
            summary['status']='RATE_LIMITED' if any(r.get('http_status')==429 for r in measured) else 'AUTH_BLOCKED' if any(r.get('http_status') in (401,403) for r in measured) else 'TESTED'
            summary['test_scope']='SHARED_DEV9' if len(measured)==9 else 'CONNECTIVITY/FORMAT_PROBE_ONLY; NOT FULL BENCHMARK'
            summary['reason']='All attempts retained; no provider/model fallback or retries; unequal N not ranked together'
        elif row.get('eligible'):
            summary['status']='NOT_RUN';summary['reason']=stop or 'Free quota reserved for already-considered models'
        summaries.append(summary)
    after=key_snapshot(client,key);write(out/'quota_after.json',after)
    result={'completed_utc':now(),'status':'PARTIAL' if stop else 'DONE_EXPLORATORY_SCREEN','stop_reason':stop,
      'generation_attempts':calls,'successful_generations':sum(s['successful_generations'] for s in summaries),
      'rows':summaries,'paid_spend_cap_usd':0,'known_reported_cost_usd':sum(s['reported_cost_known_sum_usd'] or 0 for s in summaries),
      'unknown_cost_events':sum(s['unknown_cost_events'] for s in summaries),'quota_after':after,
      'requests_count_note':'Generation attempts plus initial catalogue metadata GETs, fresh pre-inference metadata GETs and3 additional quota GETs; all metadata excluded from per-generation latency',
      'metadata_requests_initial':original.get('metadata_requests_n',2+sum(r['resolved_model_id'] is not None for r in original['rows'])),
      'metadata_requests_screening':source['metadata_requests_n']+3,
      'generative_cloud_calls':calls,'hosted_router_calls':0,'verification_calls':0,'retries':0,
      'limitations':['No fresh confirmatory holdout','Unequal N: probes are not full benchmarks','Free-tier queue latency is a service condition','Model weights/actual remote quantization UNKNOWN','Account privacy preferences preserved, no override','Initial metadata Lyria classification corrected before any inference'],
      'resume':'Do not repeat this metadata execution claim. A new versioned trial after quota reset must explicitly preserve all prior attempts and sample IDs.'}
    result['total_external_requests']=calls+result['metadata_requests_initial']+result['metadata_requests_screening']
    write(out/'summary.json',result)
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'status':result['status'],'generation_attempts':calls,'stop_reason':stop,'successful_generations':result['successful_generations']}) ,flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path)
    mode=p.add_mutually_exclusive_group();mode.add_argument('--metadata-only',action='store_true');mode.add_argument('--execute',action='store_true')
    p.add_argument('--metadata-dir',type=Path);p.add_argument('--measurement-window')
    args=p.parse_args();key,source=read_key()
    suffix='_openrouter21_screen' if args.execute else '_openrouter21_metadata'
    out=(args.output or ROOT/'results'/(datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')+'_'+uuid.uuid4().hex[:8]+suffix)).resolve()
    out.mkdir(parents=True,exist_ok=False)
    with httpx.Client(timeout=30,follow_redirects=False,trust_env=True) as c:
        if args.execute:
            if not key or args.metadata_dir is None or not args.measurement_window:raise SystemExit('Execution needs exact project credential, metadata directory and confirmed measurement window')
            run_screen(c,key,args.metadata_dir,out,args.measurement_window);return
        manifest,quota=metadata(c,key,out)
    print(json.dumps({'output':out.relative_to(ROOT).as_posix(),'quota':quota,'rows':[{'name':r['requested_display_name'],'id':r['resolved_model_id'],'status':r['status'],'reason':r['reason'],'endpoint':endpoint_slug(r['selected_endpoint']) if r['selected_endpoint'] else None} for r in manifest['rows']]},ensure_ascii=False),flush=True)

if __name__=='__main__':main()

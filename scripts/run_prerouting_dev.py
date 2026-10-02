"""Fresh live exploratory routing-vs-cascade comparison. No old/final response replay.

Requires a model instance loaded by the single LM Studio controller. This
driver never loads/unloads models, and never selects the observed final150.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import os
import random
import subprocess
import sys
import time
import uuid
import hashlib
import queue
import threading

import httpx
from agro_route.prerouting import QUESTIONS, public_state, rule_route, normalize_router, decide_pre, SharedBudget
from agro_route.home_config import resolve_api_key
from agro_route.evaluation import score
import run_home_final as old

ROOT=Path(__file__).resolve().parents[1]
METHODS=['tool_cloud','cascade','rule_first','jev_first','laya_first','offline_laya']

def now():return datetime.now(timezone.utc).isoformat()
def offline_socket_guard(active_method,event,args):
    if active_method[0]=='offline_laya' and event=='socket.connect':
        address=args[1]
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1','localhost'):
            raise RuntimeError('External sockets disabled for offline arm')
def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

class Jev:
    def __init__(self,key,client,budget,out):self.key,self.client,self.budget,self.out=key,client,budget,out;self.stop=None
    def __call__(self,request,enabled):
        if self.stop or not self.key:
            return {'route':None,'error':{'type':self.stop or 'CredentialMissing'},'router_external_calls':0,'cost_usd':0.}
        state=public_state(request,enabled)
        try:identifier=self.budget.reserve('jev',64000*.042/1e6)
        except RuntimeError:
            self.stop='SharedBudgetBlocked'
            return {'route':None,'error':{'type':self.stop},'router_external_calls':0,'cost_usd':0.}
        append(self.out/'attempts.jsonl',{'utc':now(),'event':'started','provider':'jev','attempt_id':identifier})
        began=time.perf_counter();raw=None;cost=None
        try:
            response=self.client.post('https://api.typesafe.ai/v1/systemone',headers={'Authorization':'Bearer '+self.key},
                                      json={'model':'jev-1.13.0','state':state,'questions':QUESTIONS})
            response.raise_for_status();raw=response.json()
            inp=raw.get('usage',{}).get('input_tokens')
            if isinstance(inp,int) and not isinstance(inp,bool) and inp>=0:cost=inp*.042/1e6
            if raw.get('model')!='jev-1.13.0':
                self.stop='PinnedModelMismatch';raise ValueError('Pinned Jev version mismatch')
            result=normalize_router(raw,'jev-1.13.0',True)
        except Exception as exc:
            status=getattr(getattr(exc,'response',None),'status_code',None)
            if status in (401,402,403,429) or isinstance(status,int) and status>=500:self.stop='HTTP_'+str(status)
            result={'route':None,'error':{'type':type(exc).__name__,'http_status':status},'router_external_calls':1,'raw':raw}
        self.budget.finish(identifier,cost)
        result.update(cost_usd=cost,latency_ms=(time.perf_counter()-began)*1000,attempt_id=identifier)
        append(self.out/'attempts.jsonl',{'utc':now(),'event':'finished','provider':'jev','attempt_id':identifier,'error':result.get('error'),'cost_usd':cost})
        return old.sanitize(result,(self.key,))

class Laya:
    def __init__(self,out):
        self.stderr=(out/'laya_worker_stderr.txt').open('w',encoding='utf-8')
        self.process=subprocess.Popen([str(ROOT/'.runtime/jev/.venv/Scripts/python.exe'),str(ROOT/'scripts/laya_prerouter_worker.py'),str(out/'protocol.json')],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        self.lines=queue.Queue()
        def read_lines():
            for line in self.process.stdout:self.lines.put(line)
            self.lines.put('')
        threading.Thread(target=read_lines,daemon=True).start()
        try:
            self.metadata=self.read(120)
            if not self.metadata.get('ready'):raise RuntimeError('Laya worker not ready')
        except Exception:
            self.close();raise
    def read(self,timeout=60):
        try:line=self.lines.get(timeout=timeout)
        except queue.Empty:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
            raise RuntimeError('Laya worker timed out') from None
        if not line:raise RuntimeError('Laya worker exited before response')
        return json.loads(line)
    def __call__(self,request,enabled):
        state=public_state(request,enabled)
        self.process.stdin.write(json.dumps({'state':state},ensure_ascii=True)+'\n');self.process.stdin.flush()
        body=self.read()
        if body.get('error'):return {'route':None,'error':body['error'],'router_external_calls':0,'cost_usd':0.}
        result=normalize_router(body['raw'],'laya-multilingual@e4e9ddf',False)
        return {**result,'cost_usd':0.,'component_metadata':body}
    def close(self):
        if self.process.poll() is None:
            try:self.process.stdin.write('{"stop":true}\n');self.process.stdin.flush()
            except (BrokenPipeError,OSError):pass
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        self.stderr.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--instance',required=True);parser.add_argument('--n',type=int,default=36)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',type=Path)
    parser.add_argument('--model-root',type=Path,default=Path.home()/'.lmstudio/models');args=parser.parse_args()
    samples=old.api.select_samples(args.n)
    assert all(s['split']=='dev' for s in samples)
    protocol={'phase':'EXPLORATORY_DEVELOPMENT_NOT_CONFIRMATORY','created_utc':now(),'n':len(samples),'ids':[s['id'] for s in samples],
              'local_reference':'gemma-4-26b-a4b-it','quantization':'IQ4_NL_XL','model_instance':args.instance,'context':4096,'gpu_requested':.70,
              'actual_gpu_offload_layers':'UNKNOWN; nativeAPI omits layer/ratio; controller CLI invocation recorded separately',
              'local_main_weight_sha256':'c1ac61e3af04b40c7688dfe0686c54d68ff5ed26178a56f0b18c8a0e2b94db83',
              'local_main_weight_bytes':14556687680,
              'cloud_reference':old.CLOUD,'jev':'jev-1.13.0','laya_revision':'e4e9ddf21a7b1903b7acffd8814ad4307bf63a67',
              'methods':METHODS,'router_questions':QUESTIONS,'seed':20261002,'max_tokens':512,'retries':0,'concurrency':1,
              'samples_canonical_sha256':hashlib.sha256(old.canonical(samples).encode('utf-8')).hexdigest(),
              'router_missing_data_question':'Diagnostic only; route choice selects, shared deterministic gate validates numerical completeness',
              'lm_prompt_kv_cache_policy':'UNKNOWN server policy; interleaved order, no client response replay; not cold-request latency',
              'local_requested_settings':{'temperature':0,'top_p':1,'seed':42,'reasoning_effort':'none','structured_schema':old.api.SCHEMA},
              'cloud_requested_settings':{'temperature':0,'max_tokens':512,'mode':'instant','historical_observed_temperature':1,'deviation':'Prior Mercury responses forced temperature1. Fresh actual setting must be read from raw warnings; not assumed.'},
              'prompt_sha256':hashlib.sha256(old.SYSTEM_PROMPT.encode('utf-8')).hexdigest(),
              'scoring_sha256':hashlib.sha256((ROOT/'src/agro_route/evaluation.py').read_bytes()).hexdigest(),
              'dataset_sha256':hashlib.sha256((ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest(),
              'shared_new_paid_cap_usd':.01,'budget_basis':'Conservative bound no larger than documented prior Jev pilot0.01 and final0.25; shared across Jev/Mercury workers.',
              'primary_comparison':'jev_first versus rule_first; same guards/generators','secondary_comparison':'pre-routing versus unchanged historical cascade; ambiguity guard is an explicit additional factor',
              'human_review':False,'fresh_confirmatory_holdout':'NOT RUN; prior final150 observed and excluded','latency_scope':'live end-to-end; Laya resident for all methods; loads/warmup excluded and separate',
              'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(old.DEPENDENCIES|{'src/agro_route/prerouting.py','scripts/run_prerouting_dev.py','scripts/laya_prerouter_worker.py'})}}
    if not args.execute:print(json.dumps(protocol,ensure_ascii=False,indent=2));return
    if args.resume:
        out=args.resume.resolve()
        if not out.is_relative_to((ROOT/'results').resolve()):raise ValueError('Resume must be inside project results')
        protocol=json.loads((out/'protocol.json').read_text(encoding='utf-8'))
        samples=json.loads((out/'samples_dev.json').read_text(encoding='utf-8'))
        if protocol['model_instance']!=args.instance or protocol['n']!=len(samples) or protocol['methods']!=METHODS:raise ValueError('Resume configuration mismatch')
        if protocol['ids']!=[s['id'] for s in samples] or any(s['split']!='dev' for s in samples):raise ValueError('Resume sample IDs or split mismatch')
        if hashlib.sha256(old.canonical(samples).encode('utf-8')).hexdigest()!=protocol['samples_canonical_sha256']:raise ValueError('Resume sample snapshot mismatch')
        if hashlib.sha256((ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest()!=protocol['dataset_sha256']:raise ValueError('Resume dataset mismatch')
        for name,expected in protocol['code_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Resume scientific code mismatch')
    else:
        out=ROOT/'results'/(datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')+'_'+uuid.uuid4().hex[:8]+'_prerouting_dev');out.mkdir(exist_ok=False)
        old.write_new(out/'protocol.json',protocol);old.write_new(out/'samples_dev.json',samples)
    budget=SharedBudget(ROOT/'.runtime/prerouting_shared/budget.sqlite3',.01)
    local_key,local_source=resolve_api_key('local');cloud_key,cloud_source=resolve_api_key('mercury');jev_key,jev_source=resolve_api_key('jev')
    secrets=(local_key,cloud_key,jev_key)
    manifest={'created_utc':now(),'state':'running','run_id':out.name,'credential_sources':{'local':local_source,'cloud':cloud_source,'jev':jev_source},'rows':0,'load_model_by_this_driver':False}
    old.write_new(out/('manifest_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'manifest_initial.json'),manifest)
    if not args.resume:old.write_new(out/'hardware.json',old.hardware())
    rows=[json.loads(line) for line in (out/'raw_decisions.jsonl').read_text(encoding='utf-8').splitlines()] if args.resume and (out/'raw_decisions.jsonl').is_file() else []
    completed={(r['sample']['id'],r['method']) for r in rows}
    if len(completed)!=len(rows):raise ValueError('Duplicate decisions in resume source')
    started_pairs=set()
    if args.resume and (out/'decisions_events.jsonl').is_file():
        started_pairs={(r['sample_id'],r['method']) for r in map(json.loads,(out/'decisions_events.jsonl').read_text(encoding='utf-8').splitlines()) if r['event']=='started'}
        if started_pairs-completed:raise RuntimeError('Unresolved decision attempt: manual audit needed; no automatic provider replay')
    weight=args.model_root/'unsloth/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-UD-IQ4_NL_XL.gguf'
    fingerprint={'checked_utc':now(),'file':str(weight),'bytes':weight.stat().st_size,'sha256':old.sha(weight),'excluded_from_latency':True}
    if fingerprint['bytes']!=protocol['local_main_weight_bytes'] or fingerprint['sha256']!=protocol['local_main_weight_sha256']:
        raise RuntimeError('Reference GGUF fingerprint mismatch')
    old.write_new(out/('weight_fingerprint_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'weight_fingerprint.json'),fingerprint)
    laya=None;monitor=old.home.Monitor();monitor.__enter__()
    print('RUN '+out.as_posix(),flush=True)
    try:
        laya=Laya(out);old.write_new(out/('laya_load_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'laya_load.json'),laya.metadata)
        active_method=[None]
        sys.addaudithook(lambda event,args:offline_socket_guard(active_method,event,args))
        def offline_remote_guard(request):
            if active_method[0]=='offline_laya':raise RuntimeError('External inference disabled for offline arm')
        with httpx.Client(timeout=60,trust_env=False) as local_client,httpx.Client(timeout=60,follow_redirects=False,event_hooks={'request':[offline_remote_guard]}) as remote_client:
            catalog=old.api.native_models(local_client,local_key)
            matches=[i for m in catalog if m.get('key')==protocol['local_reference'] and m.get('quantization',{}).get('name')==protocol['quantization'] for i in m.get('loaded_instances',[]) if i['id']==args.instance]
            if len(matches)!=1 or matches[0]['config']['context_length']!=4096 or matches[0]['config']['parallel']!=1:raise RuntimeError('Reference instance configuration mismatch')
            old.write_new(out/('catalog_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'catalog_before.json'),old.sanitize(catalog,secrets))
            jev=Jev(jev_key,remote_client,budget,out)
            cloud_model=old.Model(old.CLOUD['base_url'],old.CLOUD['model'],cloud_key,.04,.15,timeout=60)
            cloud_stop=[None]
            def local(req):
                available=old.home.resource_headroom()
                if available['ram_available_gib']<2 or available['gpu_free_mib']<512:raise old.ProviderBlocked('local','memory_guard')
                append(out/'attempts.jsonl',{'utc':now(),'event':'started','provider':'local'})
                began=time.perf_counter()
                try:r={**old.api.api_call(local_client,local_key,args.instance,req,'none'),'provider':'local'}
                except Exception as exc:r={'provider':'local','output':None,'error':{'type':type(exc).__name__},'cost_usd':0.,'latency_ms':(time.perf_counter()-began)*1000}
                append(out/'attempts.jsonl',{'utc':now(),'event':'finished','provider':'local','error':r.get('error')})
                return r
            def cloud(req):
                if active_method[0]=='offline_laya':raise old.ProviderBlocked('cloud','external_inference_disabled')
                if cloud_stop[0] or not cloud_key:raise old.ProviderBlocked('cloud',cloud_stop[0] or 'credential_missing')
                # UTF8 bytes + generous template overhead bound input tokens; output bound512.
                input_bound=len((old.SYSTEM_PROMPT+json.dumps(req,ensure_ascii=False)).encode('utf-8'))+1024
                try:identifier=budget.reserve('mercury',input_bound*.04/1e6+512*.15/1e6)
                except RuntimeError:raise old.ProviderBlocked('cloud','shared_budget_guard') from None
                append(out/'attempts.jsonl',{'utc':now(),'event':'started','provider':'cloud','attempt_id':identifier})
                try:r=old.strict_cloud_record(cloud_model.call(req))
                except Exception as exc:r={'output':None,'error':{'type':type(exc).__name__},'cost_usd':None}
                returned_model=(r.get('raw') or {}).get('model')
                if returned_model is not None and returned_model!=old.CLOUD['model']:
                    cloud_stop[0]='PinnedModelMismatch'
                    r.update(output=None,error={'type':'PinnedModelMismatch','returned_model':returned_model})
                budget.finish(identifier,r.get('cost_usd'))
                if old.fatal_status(r.get('error')):cloud_stop[0]='provider_http_failure'
                append(out/'attempts.jsonl',{'utc':now(),'event':'finished','provider':'cloud','attempt_id':identifier,'error':r.get('error'),'cost_usd':r.get('cost_usd')})
                return {**r,'provider':'cloud'}
            rng=random.Random(20261002)
            for index,sample in enumerate(samples):
                order=METHODS.copy();rng.shuffle(order)
                for method in order:
                    if (sample['id'],method) in completed:continue
                    active_method[0]=method
                    append(out/'decisions_events.jsonl',{'utc':now(),'event':'started','sample_id':sample['id'],'method':method})
                    public={k:sample[k] for k in ('input','context','inputs') if k in sample}
                    if method in ('tool_cloud','cascade'):
                        result=old.measured_decision(public,'tool_cloud' if method=='tool_cloud' else 'hybrid',local,cloud)
                        result.update(router_external_calls=0,verification_external_calls=0,retry_calls=0,total_external_requests=result['cloud_calls'],router_latency_ms=0)
                    else:
                        selector={'rule_first':rule_route,'jev_first':jev,'laya_first':laya,'offline_laya':laya}[method]
                        result=decide_pre(public,selector,local,cloud,cloud_available=method!='offline_laya',hosted_router=method=='jev_first')
                    row=old.sanitize({'sample':sample,'method':method,'result':result,'score':score(sample,result['output'])},secrets)
                    append(out/'raw_decisions.jsonl',row);rows.append(row)
                    append(out/'decisions_events.jsonl',{'utc':now(),'event':'finished','sample_id':sample['id'],'method':method})
                print(json.dumps({'completed_cases':index+1,'target':len(samples),'budget':{k:v for k,v in budget.snapshot().items() if k!='attempts'}},ensure_ascii=True),flush=True)
        manifest.update(state='completed',completed_utc=now(),rows=len(rows),expected_rows=len(samples)*len(METHODS))
    except Exception as exc:
        manifest.update(state='partial_or_blocked',error={'type':type(exc).__name__},rows=len(rows),completed_utc=now())
        print('CHECKPOINT '+type(exc).__name__,flush=True)
    finally:
        if laya:laya.close()
        monitor.__exit__()
        old.write_new(out/('resources_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'resources.json'),{'summary':monitor.summary(),'samples':monitor.rows})
        old.write_new(out/('budget_snapshot_resume_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'budget_snapshot.json'),budget.snapshot())
        old.write_new(out/('manifest_resume_completed_'+uuid.uuid4().hex[:8]+'.json' if args.resume else 'manifest.json'),manifest)
    print('RESULT '+str(out.relative_to(ROOT)),flush=True)

if __name__=='__main__':main()

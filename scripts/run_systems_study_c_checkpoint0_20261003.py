"""Separate operational recovery protocol; never overwrites V1 or DEV293.

Explicit native context_checkpoints=0, parallel=1 and MTP off, verified from
echoed load config. Native REST does not expose GPU offload control: placement
is automatic/unknown, unlike historical lms CLI max/.75 requested settings.
Qwen9 Study C is reused from its already completed V1, Qwen27 is evaluated only
after resource-censored V1; no selection by correctness and no prompt changes.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import time

import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_systems_study_c_20261003 as base
import mera_local_screen_20261003 as screen
import home_lm_api_benchmark as native
from agro_route.home_config import resolve_api_key
from agro_route.lm_telemetry_20261003 import ResourceSampler, device_snapshot, safe_record, redact, utc_now
from agro_route.study_c_run_20261003 import score_text
from agro_route.deterministic_study_20261003 import public_request

RUN = "20261003_systems_checkpoint0_v2"
SAFE = ROOT / "results" / RUN
RAW = ROOT / ".runtime/mera" / RUN
OLD = ROOT / "results/20261003_systems_study_c_v1"


def native_load_body(model):
    return {"model": model, "context_length": 2048, "eval_batch_size": 2048,
            "flash_attention": True, "echo_load_config": True, "context_checkpoints": 0,
            "parallel": 1, "speculative_draft_mtp": False}


def verify_load_config(config):
    required = {"context_length":2048,"eval_batch_size":2048,"parallel":1,
                "speculative_draft_mtp":False,"context_checkpoints":0,"flash_attention":True}
    if any(config.get(k) != v for k,v in required.items()):
        raise RuntimeError("Native load config not confirmed")


def run():
    previous = json.loads((OLD / "protocol_frozen.json").read_text(encoding="utf-8"))
    items, _, _ = screen.validate_source(screen.DEFAULT_SOURCE, previous["source_sha256"])
    by_id={i.item_id:i for i in items}
    blocks = [[by_id[k] for k in ids] for ids in previous["blocks"]]
    cases = json.loads(base.STUDY.read_text(encoding="utf-8"))["cases"]
    assignments=[(0,"qwen3.5-9b"),(0,"qwen3.8-27b"),(1,"qwen3.8-27b"),(1,"qwen3.5-9b")]
    SAFE.mkdir(exist_ok=False); RAW.mkdir(parents=True,exist_ok=False)
    sources = [Path(__file__), Path(base.__file__),ROOT/'src/agro_route/lm_telemetry_20261003.py', ROOT/'src/agro_route/study_c_run_20261003.py']
    plan={**previous,"run_id":RUN,"created_utc":utc_now(),"parent_run":previous['run_id'],
          "parent_plan_sha256":base.sha((OLD/'protocol_frozen.json').read_bytes()),
          "source_code_sha256":{str(p.relative_to(ROOT)).replace('\\','/'):base.sha(p.read_bytes()) for p in sources},
          "new_native_load":{m:native_load_body(m) for m,_ in base.MODELS},
          "gpu_requested":None,"gpu_placement":"Native loader automatic; ratio and actual layers UNKNOWN. NOT equivalent to historical lms --gpu profiles.",
          "amendment_reason":"V1 Q27 RAM guard with32 context checkpoints; disable checkpoint caching for both telemetry models before full same40 systems run. No historical quality changed.",
          "study_c_reuse":"Q9 complete27 responses from V1 reused; Q27 V1 all27 resource-censored, new operational profile evaluates27. No prompt/scorer changes.",
          "stop_on_resource_guard":True,"new_study_c_calls":{"qwen3.5-9b":0,"qwen3.8-27b":27}}
    base.write(SAFE/'protocol_frozen.json',plan)
    (SAFE/'study_c_system_prompt.txt').write_text(base.study_system(),encoding='utf-8')
    key,_=resolve_api_key('local',env_path=ROOT/'.env')
    if not key: raise RuntimeError('Local credential unavailable')
    with httpx.Client(timeout=240,trust_env=False) as client:
        screen.idle(client,key)
        base.write(SAFE/'host_before.json',device_snapshot())
        loads=[]
        for index,(block,model) in enumerate(assignments):
            load={'block':block,'model_key':model,'gpu_requested':None,'actual_gpu_layers':None,
                  'stabilized_idle':base.stabilized(),'load_start_utc':utc_now()}
            identifier=None
            try:
                body=native_load_body(model)
                with ResourceSampler() as monitor:
                    start=time.perf_counter()
                    response=client.post('http://127.0.0.1:1234/api/v1/models/load',json=body,headers={'Authorization':'Bearer '+key})
                    load['load_latency_s']=time.perf_counter()-start
                    response.raise_for_status()
                    obj=response.json(); identifier=obj['instance_id']
                    config=obj['load_config'];verify_load_config(config)
                    load['config']={k:v for k,v in config.items() if k!='prompt_template'}
                    load['prompt_template_sha256']=base.sha(json.dumps(config.get('prompt_template'),sort_keys=True).encode())
                    load['backend_load_time_s']=obj.get('load_time_seconds')
                    if monitor.tripped.is_set():raise RuntimeError('Native loading resource guard')
                load['resource_after_load']=device_snapshot()
                warm=base.call(client,key,identifier,screen.SYSTEM,screen.WARMUP,'synthetic_warmup',model,block,'warmup','synthetic')
                base.append(RAW/'raw.jsonl',warm);base.append(SAFE/'inference_metrics.jsonl',safe_record(warm));load['warmup_latency_s']=warm['latency_s']
                if warm['error'] or not warm['parse_success']:raise RuntimeError('Warmup failed')
                for item in blocks[block]:
                    raw=base.call(client,key,identifier,screen.SYSTEM,item.prompt,item.item_id,model,block,'telemetry',item.domain)
                    base.append(RAW/'raw.jsonl',raw);base.append(SAFE/'inference_metrics.jsonl',safe_record(raw))
                    if raw['error'] or raw['resources']['system_ram_available_gib_min_sampled']<2 or raw['resource_errors']:
                        raise RuntimeError('Stop on first resource/inference failure')
                if model=='qwen3.8-27b':
                    for case in cases[block::2]:
                        raw=base.call(client,key,identifier,base.study_system(),json.dumps(public_request(case),ensure_ascii=False),case['id'],model,block,'study_c',case['group'])
                        base.append(RAW/'raw.jsonl',raw);base.append(SAFE/'inference_metrics.jsonl',safe_record(raw))
                        base.append(SAFE/'study_c_scores.jsonl',{'model_key':model,'source_run':RUN,'latency_s':raw['latency_s'],'error':raw['error'],**score_text(case,raw['response_text'],raw['error'])})
                        if raw['error'] or raw['resources']['system_ram_available_gib_min_sampled']<2 or raw['resource_errors']:
                            raise RuntimeError('Stop on first resource/inference failure')
                print(json.dumps({'model':model,'block':block,'telemetry_complete':len(blocks[block]),'study_c_new':len(cases[block::2]) if model=='qwen3.8-27b' else 0}),flush=True)
            finally:
                if identifier is not None:
                    response=client.post('http://127.0.0.1:1234/api/v1/models/unload',json={'instance_id':identifier},headers={'Authorization':'Bearer '+key})
                    load['unload_success']=response.status_code==200
                    screen.idle(client,key)
                else:
                    # If a load times out before returning its ID, only a model
                    # absent before and matching this exact requested key is ours.
                    matches=[i['id'] for m in native.native_models(client,key) if m.get('key')==model for i in m.get('loaded_instances',[])]
                    for own in matches:
                        client.post('http://127.0.0.1:1234/api/v1/models/unload',json={'instance_id':own},headers={'Authorization':'Bearer '+key}).raise_for_status()
                    screen.idle(client,key)
                load['resource_after_unload']=device_snapshot();loads.append(load);base.append(SAFE/'loads_append.jsonl',redact(load,key))
        base.write(SAFE/'load_receipts.json',loads)
        base.write(SAFE/'host_after.json',device_snapshot())
    previous_scores=[json.loads(line) for line in (OLD/'study_c_scores.jsonl').read_text(encoding='utf-8').splitlines()]
    for row in previous_scores:
        if row['model_key'] in {'qwen3.5-9b','deterministic_tools'}:
            base.append(SAFE/'study_c_scores.jsonl',{**row,'source_run':previous['run_id']})
    base.write(SAFE/'completion_receipt.json',{'run_id':RUN,'finished_utc':utc_now(),'state':'COMPLETE','models_unloaded':True,
        'raw_sha256':base.sha((RAW/'raw.jsonl').read_bytes()),'inference_metrics_sha256':base.sha((SAFE/'inference_metrics.jsonl').read_bytes()),
        'private_test_run':False,'paid_api_calls':0,'new_paid_api_spend_authorized_usd':0})
    base.SAFE=SAFE;base.RAW=RAW;base.RUN=RUN
    base.analyze()


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    run()

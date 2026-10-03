"""One predeclared live Study C development run. No native function calls.

Public task supplied in both arms; all model arguments preserved and checked.
New artifacts only. HTTP cancellation and independent sampled resource guard
remain active during blocked loads and SSE reads. No paid API or hidden TEST.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import run_systems_study_c_20261003 as old
import run_systems_study_c_checkpoint0_20261003 as safe_load
from agro_route.home_config import resolve_api_key
from agro_route.deterministic_study_20261003 import (TASK_TO_TOOL, REQUIRED, UNITS,
    public_request, execute_request, _no_private_fields)
from agro_route.lm_telemetry_20261003 import (native_payload, parse_native_sse,
    parse_json_presentation, windows_ram, lmstudio_process_rss, summarize_resources,
    utc_now, redact)
from agro_route.study_c_run_20261003 import score_text

RUN = '20261004_study_c_live'
SAFE = ROOT / 'results' / RUN
RAW = ROOT / '.runtime/study_c_live_20261004'
PLAN = ROOT / 'experiments/STUDY_C_LIVE_PROTOCOL_20261004.json'
MODELS = ['qwen3.5-9b', 'qwen3.8-27b']
BASE = 'http://127.0.0.1:1234'
TOOL_INSTRUCTION = '''\nРежим инструментов: сам не выполняй вычисления.
Верни ровно JSON. Чтобы использовать инструмент, верни
{"action":"CALL_TOOL","tool":"<allowlisted ID>","arguments":{"inputs":{...},"units":{...}}}.
Скопируй ВСЕ публичные inputs и units точно, включая неполные и неверные.
Не заполняй отсутствующие поля, не исправляй единицы, не добавляй значения.
Приложение проверит JSON, публичные значения, контракт, единицы и исполнит код.
Если требуется уточнение, допускается сразу ASK_FOR_DATA с теми же полями,
что в основном контракте; неизвестный task: ABSTAIN,UNSUPPORTED_TASK.
Это application JSON dispatch, не native function calls. task публично дан.
'''
FINAL_INSTRUCTION = '''Верни ровно итоговый JSON по основному контракту.
Используй полученный tool_result: для ANSWER скопируй numeric с полной точностью,
unit и tool; для ASK_FOR_DATA скопируй reason_code и requested_fields.
Не подменяй данные и не вычисляй заново. Никаких агрономических рекомендаций.
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def append(path, obj):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False, allow_nan=False) + '\n')


def strict_json(text):
    # Duplicate keys are a schema error rather than silently keeping last value.
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DuplicateJSONKey')
            result[key] = value
        return result
    stripped = text.strip()
    if stripped.startswith('```'):
        parse_json_presentation(stripped)  # only documented presentation fences
        stripped = '\n'.join(stripped.splitlines()[1:-1])
    obj = json.loads(stripped, object_pairs_hook=pairs,
                     parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NonfiniteJSON')))
    if not isinstance(obj, dict):
        raise ValueError('ObjectRequired')
    _no_private_fields(obj)
    return obj


def same_public(left, right):
    # Preserve type and value: bool cannot impersonate 1, int/float numeric equal.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_public(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_public(a, b) for a, b in zip(left, right))
    return left == right


def dispatch(request, selection):
    """Never receives case/gold. No fallback fills any model argument."""
    _no_private_fields(request)
    _no_private_fields(selection)
    if set(selection) != {'action', 'tool', 'arguments'} or selection['action'] != 'CALL_TOOL':
        raise ValueError('CallSchema')
    tool, arguments = selection['tool'], selection['arguments']
    if not isinstance(tool, str) or tool not in REQUIRED:
        raise ValueError('ToolNotAllowlisted')
    if not isinstance(arguments, dict) or set(arguments) != {'inputs', 'units'}:
        raise ValueError('ArgumentSchema')
    if not isinstance(arguments['inputs'], dict) or not isinstance(arguments['units'], dict):
        raise ValueError('ArgumentObjectRequired')
    for name in ('inputs', 'units'):
        if not same_public(arguments[name], request.get(name)):
            raise ValueError('PublicArgumentsChanged')
    exact = {'task': request.get('task'), 'question_ru': request.get('question_ru'),
             'inputs': arguments['inputs'], 'units': arguments['units']}
    result = execute_request(exact, selected_tool=tool)
    return {'schema_valid': True, 'public_arguments_exact': True,
            'contract_valid': result['action'] == 'ANSWER',
            'executed_numeric': result['action'] == 'ANSWER', 'tool_result': result}


def snapshot():
    started = time.perf_counter()
    # A short subprocess deadline prevents a monitoring hang from blocking guard.
    p = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1.5)
    parts = p.stdout.strip().split(',')
    if p.returncode or len(parts) != 5:
        raise RuntimeError('ResourceObservationFailed')
    values = [float(x.strip()) for x in parts]
    if any(not math.isfinite(x) or x < 0 for x in values):
        raise RuntimeError('ResourceObservationFailed')
    names = ['gpu_memory_used_mib', 'gpu_memory_free_mib', 'gpu_utilization_pct', 'gpu_temperature_c', 'gpu_power_w']
    return {'utc': utc_now(), 'monotonic_s': time.perf_counter(),
            'sample_acquisition_s': time.perf_counter()-started,
            **dict(zip(names, values)), **windows_ram(), **lmstudio_process_rss()}


async def guarded(operation, *, deadline_s, sample=snapshot, interval=.15):
    """Cancel blocked async I/O, independent of SSE arrival or load return."""
    samples, errors = [], []
    async def watcher():
        while True:
            try:
                row = await asyncio.wait_for(asyncio.to_thread(sample), timeout=2)
                samples.append(row)
                if row['system_ram_available_gib'] < 2 or row['gpu_memory_free_mib'] < 512:
                    return 'RESOURCE_GUARD'
            except Exception as exc:
                errors.append(type(exc).__name__)
                return 'RESOURCE_OBSERVATION_FAILED'
            await asyncio.sleep(interval)
    task = asyncio.create_task(operation())
    watch = asyncio.create_task(watcher())
    began = time.perf_counter()
    value, error = None, None
    try:
        done, _ = await asyncio.wait({task, watch}, timeout=deadline_s, return_when=asyncio.FIRST_COMPLETED)
        if watch in done:
            error = watch.result()
        elif task in done:
            try:
                value = task.result()
            except Exception as exc:
                error = type(exc).__name__
        else:
            error = 'WALL_DEADLINE'
    finally:
        task.cancel(); watch.cancel()
        await asyncio.gather(task, watch, return_exceptions=True)
    return {'value': value, 'error': error, 'latency_s': time.perf_counter()-began,
            'resource_samples': samples, 'resource_errors': errors,
            'resources': summarize_resources(samples)}


def prepare():
    cases = json.loads(old.STUDY.read_text(encoding='utf-8'))['cases']
    assert len(cases) == 27
    hashes = json.loads((ROOT/'results/20261003_local_screen_571682f5/installed_weight_checksums.json').read_text(encoding='utf-8'))['models']
    protocol = {'run_id': RUN, 'created_utc': utc_now(), 'classification': 'MATCHED_DEVELOPMENT_RUN',
        'cases': [c['id'] for c in cases], 'n_each_arm_each_model': 27,
        'arms': ['model_only', 'live_application_tools'], 'models': MODELS,
        'data_sha256': sha(old.STUDY.read_bytes()),
        'public_information': 'Identical public_request with explicit typed task, question, inputs and units. No hidden category/tool/gold in dispatch.',
        'tool_transport': 'Model-generated JSON selection and arguments; application validates and executes allowlisted code; NOT native function calls.',
        'tool_argument_policy': 'Entire public inputs/units must equal model-supplied objects; no completion, coercion or conversion by application.',
        'load': safe_load.native_load_body('MODEL_KEY'), 'decoding': native_payload('INSTANCE','SYSTEM','PROMPT'),
        'seed': None, 'schema_enforcement': 'Application validates returned JSON; native API does not enforce response schema.',
        'order': 'Q9 then Q27; per case alternating model-only/tool-first by case index. Fixed case order.',
        'warmup': 'One synthetic JSON echo per load, separate from measured cases.',
        'limits': {'run_wall_s': 900, 'load_wall_s': 180, 'request_wall_s': 45, 'output_tokens_each_call':512,
                   'guard_min_ram_gib':2, 'guard_min_gpu_free_mib':512, 'preload_ram_gib':3, 'preload_gpu_mib':1024,
                   'monitor_subprocess_deadline_s':1.5, 'monitor_acquisition_deadline_s':2},
        'guard_method': 'Independent asyncio watcher cancels blocked HTTP load/SSE; observation failure stops run; cleanup unloads exact owned model instances.',
        'strict_absolute_tolerance':1e-8, 'secondary_rounding_absolute_tolerance':1e-4,
        'diagnostic': 'Rounding sensitivity only, not agricultural or field safety; no post-hoc rerun.',
        'whole_device_resource_scope':'whole GPU / whole-system RAM / named LM Studio process-group RSS, NOT per-model allocation',
        'reference':'Deterministic formula reference, not independent farm-level truth.',
        'identities': [h for h in hashes if h['model_key'] in MODELS],
        'source_code_sha256': {str(p.relative_to(ROOT)).replace('\\','/'):sha(p.read_bytes()) for p in
            [Path(__file__), ROOT/'src/agro_route/deterministic_study_20261003.py', ROOT/'src/agro_route/lm_telemetry_20261003.py', ROOT/'src/agro_route/study_c_run_20261003.py']},
        'paid_api_calls':0, 'private_test_run':False, 'downloads':False}
    write_new(PLAN, protocol)
    return protocol, cases


async def listing(client):
    response = await client.get(BASE+'/api/v1/models')
    response.raise_for_status()
    return response.json()['models']


async def cleanup(client, model, failed_load=False):
    # Entry asserts globally idle before run; only matching run-requested key owned.
    receipts = []
    for attempt in range(30 if failed_load else 4):
        try:
            models = await listing(client)
            own = [i['id'] for m in models if m.get('key') == model for i in m.get('loaded_instances', [])]
            for instance in own:
                r = await client.post(BASE+'/api/v1/models/unload', json={'instance_id':instance})
                receipts.append({'instance_id':instance, 'status':r.status_code, 'utc':utc_now()})
                r.raise_for_status()
            if attempt >= (29 if failed_load else 1) and not own:
                return {'success':True, 'receipts':receipts}
        except Exception as exc:
            receipts.append({'error':type(exc).__name__, 'utc':utc_now()})
        await asyncio.sleep(.5)
    return {'success':False, 'receipts':receipts}


async def call(client, identifier, system, prompt, key):
    payload = native_payload(identifier, system, prompt)
    request_utc = utc_now()
    began = time.perf_counter()
    async def operation():
        lines = []
        async with client.stream('POST', BASE+'/api/v1/chat', json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                lines.append((time.perf_counter(),line))
        clocks = iter(t for t,line in lines if line.startswith('data:'))
        return parse_native_sse((line for _,line in lines), began, clock=lambda:next(clocks))
    guarded_result = await guarded(operation, deadline_s=45)
    value = guarded_result.pop('value') or {}
    record = {**guarded_result, **value, 'error':guarded_result['error'] or value.get('error'),
              'request_utc':request_utc, 'request':payload, 'request_sha256':sha(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()),
              'prompt_sha256':sha(prompt.encode()), 'prompt_bytes':len(prompt.encode()), 'response_text':value.get('response_text','')}
    if (value.get('stats') or {}).get('total_output_tokens',0) >= 512:
        record['error'] = record['error'] or 'OUTPUT_BUDGET_REACHED'
    return redact(record,key)


def summarize(rows):
    result = {}
    for model in MODELS:
        result[model] = {}
        for arm in ['model_only','live_application_tools']:
            mine = [r for r in rows if r['model_key']==model and r['arm']==arm]
            latencies = [r['latency_s'] for r in mine]
            result[model][arm] = {'n_expected':27, 'n_attempted':len(mine),
                'strict_correct':sum(r['score']['correct'] for r in mine),
                'numeric_cases':sum(r['score']['numeric_case'] for r in mine),
                'strict_numeric_correct':sum(r['score']['numeric_correct'] for r in mine),
                'rounding_1e4_numeric_correct':sum(r['score']['numeric_rounding_1e4_correct'] for r in mine),
                'errors':sum(bool(r['error']) for r in mine),
                'tool_calls_submitted':sum(r.get('tool_submission',False) for r in mine),
                'numeric_executions':sum(r.get('validation',{}).get('executed_numeric',False) for r in mine),
                'latency_mean_s':statistics.mean(latencies) if latencies else None,
                'latency_median_s':statistics.median(latencies) if latencies else None}
    return result


async def run():
    protocol = json.loads(PLAN.read_text(encoding='utf-8'))
    if sha(Path(__file__).read_bytes()) != protocol['source_code_sha256']['scripts/study_c_live_20261004.py']:
        raise RuntimeError('FrozenScriptChanged')
    cases = json.loads(old.STUDY.read_text(encoding='utf-8'))['cases']
    if sha(old.STUDY.read_bytes()) != protocol['data_sha256']:
        raise RuntimeError('FrozenDataChanged')
    SAFE.mkdir(exist_ok=False); RAW.mkdir(parents=True,exist_ok=False)
    write_new(SAFE/'protocol_frozen.json',protocol)
    key, _ = resolve_api_key('local',env_path=ROOT/'.env')
    if not key:
        raise RuntimeError('LocalCredentialUnavailable')
    headers = {'Authorization':'Bearer '+key}
    rows, loads, state, stop = [], [], 'PARTIAL', None
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(8,read=190),trust_env=False,headers=headers) as client:
        models = await listing(client)
        if any(m.get('loaded_instances') for m in models):
            raise RuntimeError('ExistingLoadedModelNotOwned')
        write_new(SAFE/'inventory.json',redact({'utc':utc_now(),'models':models},key))
        write_new(SAFE/'host_before.json',snapshot())
        for model in MODELS:
            receipt = {'model_key':model,'started_utc':utc_now(),'body':safe_load.native_load_body(model)}
            identifier = None
            try:
                before = snapshot()
                if before['system_ram_available_gib']<3 or before['gpu_memory_free_mib']<1024:
                    raise RuntimeError('PreloadHeadroom')
                async def load_op():
                    response = await client.post(BASE+'/api/v1/models/load',json=receipt['body'])
                    response.raise_for_status()
                    return response.json()
                loaded = await guarded(load_op,deadline_s=180)
                receipt.update({k:v for k,v in loaded.items() if k!='value'})
                if loaded['error']:
                    raise RuntimeError(loaded['error'])
                value = loaded['value']; identifier=value['instance_id']
                safe_load.verify_load_config(value['load_config'])
                receipt['instance_id']=identifier
                receipt['load_config']={k:v for k,v in value['load_config'].items() if k!='prompt_template'}
                receipt['backend_load_time_s']=value.get('load_time_seconds')
                warm = await call(client,identifier,'Верни ровно JSON {"ok":true}.','Синтетический прогрев.',key)
                append(RAW/'calls.jsonl',{'kind':'warmup','model_key':model,**warm})
                if warm['error']:
                    raise RuntimeError('WarmupFailed')
                for index, case in enumerate(cases):
                    for arm in (['model_only','live_application_tools'] if index%2==0 else ['live_application_tools','model_only']):
                        if time.perf_counter()-started >900:
                            raise RuntimeError('RunWallDeadline')
                        request=public_request(case); prompt=json.dumps(request,ensure_ascii=False)
                        system=old.study_system()+(TOOL_INSTRUCTION if arm=='live_application_tools' else '')
                        first=await call(client,identifier,system,prompt,key)
                        append(RAW/'calls.jsonl',{'kind':arm,'stage':'first','model_key':model,'id':case['id'],**first})
                        output=first['response_text']; error=first['error']; total=first['latency_s']
                        row={'id':case['id'],'model_key':model,'arm':arm,'request':request,'selection':None,
                             'validation':{},'tool_output':None,'final_output':output,'tool_submission':False}
                        if arm=='live_application_tools' and not error:
                            try:
                                selection=strict_json(output);row['selection']=selection
                                if selection.get('action')=='CALL_TOOL':
                                    row['tool_submission']=True
                                    row['validation']=dispatch(request,selection)
                                    row['tool_output']=row['validation']['tool_result']
                                    final_prompt=json.dumps({'public_request':request,'model_selection':selection,'tool_result':row['tool_output']},ensure_ascii=False)
                                    final=await call(client,identifier,old.study_system()+FINAL_INSTRUCTION,final_prompt,key)
                                    append(RAW/'calls.jsonl',{'kind':arm,'stage':'final','model_key':model,'id':case['id'],**final})
                                    total+=final['latency_s'];output=final['response_text'];error=final['error']
                                elif selection.get('action') not in {'ASK_FOR_DATA','ABSTAIN'}:
                                    raise ValueError('UnexpectedToolArmAction')
                            except (ValueError,TypeError,KeyError) as exc:
                                error='VALIDATION_'+str(exc)
                        row.update(final_output=output,error=error,latency_s=total,score=score_text(case,output,error),
                            end_utc=utc_now(),first_call_resources=first['resources'],first_call_stats=first.get('stats'),
                            first_call_timing=first.get('timing'),prompt_sha256=first['prompt_sha256'])
                        append(RAW/'traces.jsonl',row)
                        # Study C synthetic content may be retained, independent of MERA.
                        append(SAFE/'traces.jsonl',row); rows.append(row)
                        print(json.dumps({'model':model,'id':case['id'],'arm':arm,'correct':row['score']['correct'],'error':error}),flush=True)
                        if first['error'] or (error and not error.startswith('VALIDATION_')):
                            raise RuntimeError('InferenceFailureStop')
            except Exception as exc:
                stop={'type':type(exc).__name__,'reason':str(exc),'model':model,'utc':utc_now()}
            finally:
                receipt['cleanup']=await cleanup(client,model,failed_load=identifier is None)
                receipt['finished_utc']=utc_now();loads.append(receipt)
                append(SAFE/'loads.jsonl',receipt)
            if stop or not receipt['cleanup']['success']:
                break
        if len(rows)==108 and not stop:
            state='COMPLETE'
        write_new(SAFE/'summary.json',{'run_id':RUN,'status':state,'models':summarize(rows),'stop':stop,
            'finished_utc':utc_now(),'elapsed_s':time.perf_counter()-started,
            'private_test_run':False,'paid_api_calls':0,'new_model_calls':sum(1 for _ in (RAW/'calls.jsonl').open(encoding='utf-8')),
            'traces_sha256':sha((SAFE/'traces.jsonl').read_bytes()) if rows else None,
            'all_requested_models_unloaded':all(l['cleanup']['success'] for l in loads)})
        write_new(SAFE/'host_after.json',snapshot())
    print(json.dumps({'status':state,'rows':len(rows),'stop':stop}),flush=True)


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run'])
    args=parser.parse_args()
    if args.mode=='prepare':
        prepare();print('Predeclared protocol created; no model request.',flush=True)
    else:
        asyncio.run(run())

"""Append-only HOME-PC development runs; never changes the original protocol.

CLI is a diagnostic fallback when HTTP authentication is unavailable. CLI runs
are not confirmatory: temperature/max tokens/JSON grammar are not controllable
through the installed CLI. API runs use explicitly recorded parameters.
"""
import argparse
import collections
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time
import uuid

import httpx
import numpy as np
from agro_route.evaluation import score
from agro_route.models import SYSTEM_PROMPT, public_request, parse_output
from agro_route.routing import decide, grounded, hard_gate

ROOT = Path(__file__).resolve().parents[1]
LMS = str(Path.home() / '.lmstudio/bin/lms.exe')
CANDIDATES = [('qwen3.5-9b', 'max'), ('gemma-4-12b-it', 'max'),
              ('qwen3.8-27b', '0.75'), ('qwen3.5-35b-a3b', '0.55'),
              ('gpt-oss-20b', 'max'), ('minicpm5-1b', 'max'),
              ('webworld-8b-i1', 'max'), ('granite-4.1-8b', 'max'),
              ('dr-venus-4b-rl', 'max'), ('qwen3-vl-8b-instruct', 'max'),
              ('qwen3-8b-deepseek-v3.2-speciale-distill', 'max'),
              ('gemma-4-26b-a4b-it', '0.70'),
              ('qwen3-omni-30b-a3b-instruct', '0.60'),
              ('qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive', '0.55'),
              ('qwen3-coder-next', '0.35')]
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

def now():
    return datetime.now(timezone.utc).isoformat()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def command(args, timeout=240):
    return subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)

def cli_json(*args):
    r = command([LMS, *args])
    if r.returncode:
        raise RuntimeError('LM Studio command failed')
    return json.loads(r.stdout)

def load_env():
    """Read only this project's allowlisted keys; never print or persist secrets."""
    allowed = {'LOCAL_API_KEY', 'CLOUD_API_KEY', 'CLOUD_BASE_URL', 'CLOUD_MODEL'}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                if name.strip() in allowed and value.strip():
                    os.environ[name.strip()] = value.strip().strip('\"\'')

class Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                *[(name, ctypes.c_ulonglong) for name in
                  ('total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]]

def ram_used():
    m = Memory(); m.length = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return (m.total - m.available) / 2**30

def resource_headroom():
    m = Memory(); m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise RuntimeError('RAM guard measurement unavailable')
    r = command(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'], 10)
    if r.returncode:
        raise RuntimeError('GPU guard measurement unavailable')
    gpu_free = float(r.stdout.strip().splitlines()[0])
    if not math.isfinite(gpu_free) or gpu_free < 0:
        raise RuntimeError('GPU guard measurement invalid')
    return {'ram_available_gib': m.available / 2**30, 'gpu_free_mib': gpu_free}

def guarded_load(args, log_path, meta):
    """Check whole-system headroom while loading; stop own load on pressure.

    Killing the CLI may not cancel a backend load. Exact-identifier cleanup is
    still mandatory in run(), and a failed cleanup stops subsequent models.
    """
    before = resource_headroom(); meta['headroom_before_load'] = before
    if before['ram_available_gib'] < 3 or before['gpu_free_mib'] < 1024:
        raise RuntimeError('Insufficient baseline headroom for model loading')
    started = time.perf_counter()
    with log_path.open('x', encoding='utf-8') as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                headroom = resource_headroom(); meta['headroom_latest'] = headroom
                if headroom['ram_available_gib'] < 2 or headroom['gpu_free_mib'] < 512:
                    meta['resource_guard_stop'] = headroom
                    raise RuntimeError('Model loading stopped by resource guard')
                if time.perf_counter() - started > 240:
                    raise subprocess.TimeoutExpired('LM Studio model load', 240)
                time.sleep(.5)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
    return subprocess.CompletedProcess(args, process.returncode)

class Monitor:
    """Sample total device VRAM and total system RAM, not per-model allocation."""
    def __init__(self):
        self.done = threading.Event(); self.rows = []; self.errors = []
    def sample(self):
        try:
            r = command(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'], 10)
            if r.returncode:
                self.errors.append({'utc':now(),'type':'nvidia_smi_nonzero','returncode':r.returncode}); return
            vram, util = map(float, r.stdout.strip().splitlines()[0].split(',')[:2])
            self.rows.append({'utc': now(), 'vram_mib_total': vram, 'gpu_util_percent': util,
                              'ram_gib_system_used': ram_used()})
        except (subprocess.TimeoutExpired, OSError, ValueError, IndexError) as exc:
            self.errors.append({'utc':now(),'type':type(exc).__name__})
    def loop(self):
        while not self.done.is_set():
            self.sample(); self.done.wait(.5)
    def __enter__(self):
        self.sample(); self.thread = threading.Thread(target=self.loop, daemon=True); self.thread.start(); return self
    def __exit__(self, *exc):
        self.done.set(); self.thread.join(timeout=12); self.sample()
    def summary(self):
        return {'vram_mib_peak_sampled_total': max((r['vram_mib_total'] for r in self.rows), default=None),
                'ram_gib_peak_sampled_system_used': max((r['ram_gib_system_used'] for r in self.rows), default=None),
                'resource_scope': 'entire GPU / entire system; sampled about every 0.5s plus subprocess overhead',
                'samples': len(self.rows), 'resource_poll_errors':self.errors}

def choose_samples(n):
    if isinstance(n,bool) or not isinstance(n,int) or n<=0:
        raise ValueError('n must be a positive integer')
    # Old DEV only. Never read old final test responses for model selection.
    data = [json.loads(line) for line in (ROOT/'data/benchmark.jsonl').read_text(encoding='utf-8').splitlines()]
    by = collections.defaultdict(list)
    for s in data:
        if s['split'] == 'dev': by[s['category']].append(s)
    if n>sum(map(len,by.values())):
        raise ValueError('n exceeds available development records')
    # Alternate languages and groups inside each category. Original dev contains
    # English-only extractive QA; this limitation must remain visible.
    for cat, values in by.items():
        values.sort(key=lambda s: s['id'])
        queues = collections.defaultdict(list)
        for s in values: queues[(s['language'],s['group'])].append(s)
        languages = sorted({s['language'] for s in values}, reverse=True)
        turns = {lang:collections.deque(sorted(k for k in queues if k[0]==lang)) for lang in languages}
        arranged=[]
        while any(queues.values()):
            for lang in languages:
                for _ in range(len(turns[lang])):
                    key=turns[lang].popleft(); turns[lang].append(key)
                    if queues[key]:
                        arranged.append(queues[key].pop(0)); break
        by[cat]=arranged
    ordered = []
    while any(by.values()):
        for cat in sorted(by):
            if by[cat]: ordered.append(by[cat].pop(0))
    return ordered[:n]

def cli_call(identifier, request):
    started = time.perf_counter()
    try:
        r = command([LMS, 'chat', identifier, '--prompt', json.dumps(public_request(request), ensure_ascii=False),
                     '--system-prompt', SYSTEM_PROMPT, '--reasoning', 'off', '--stats', '--dont-fetch-catalog', '--yes'], 120)
        raw = ANSI.sub('', r.stdout).replace('\r', '')
        diagnostics = ANSI.sub('', r.stderr).replace('\r', '')
        content = raw.split('Prediction Stats:')[0].strip()
        # CLI renders reasoning and final channels into one stream for GPT-OSS.
        # The closing channel marker provides an explicit boundary; never search
        # arbitrary prose for a JSON object. Keep the original stream in raw.
        reasoning_rendered='</think>' in content
        if reasoning_rendered:
            content=content.rsplit('</think>',1)[1].strip()
        fields = {'tokens_per_second': r'Tokens/Second:\s*([\d.]+)',
                  'time_to_first_token_seconds': r'Time to First Token:\s*([\d.]+)',
                  'prompt_tokens': r'Prompt Tokens:\s*(\d+)', 'completion_tokens': r'Predicted Tokens:\s*(\d+)'}
        stats = {k: float(m.group(1)) for k, p in fields.items() if (m := re.search(p, raw+'\n'+diagnostics))}
        output = parse_output(content) if r.returncode == 0 else None
        error = None if output else {'type': 'CLIError'}
        return {'output': output, 'error': error, 'raw': raw, 'final_content':content,
                'reasoning_rendered':reasoning_rendered, 'stats': stats,
                'usage': {k:stats[k] for k in ('prompt_tokens','completion_tokens') if k in stats},
                'latency_ms': (time.perf_counter()-started)*1000, 'cost_usd': 0.}
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return {'output': None, 'error': {'type':type(exc).__name__}, 'raw': locals().get('raw'),
                'stats':locals().get('stats',{}), 'latency_ms':(time.perf_counter()-started)*1000, 'cost_usd':0.}

def api_call(identifier, request):
    started = time.perf_counter(); raw = None
    payload = {'model': identifier, 'messages': [{'role':'system','content':SYSTEM_PROMPT},
               {'role':'user','content':json.dumps(public_request(request),ensure_ascii=False)}],
               'temperature':0, 'seed':42, 'max_tokens':512,
               'response_format':{'type':'json_object'}, 'chat_template_kwargs':{'enable_thinking':False}}
    try:
        with httpx.Client(timeout=120, trust_env=False) as client:
            r = client.post('http://127.0.0.1:1234/api/v0/chat/completions', json=payload,
                            headers={'Authorization':'Bearer '+os.environ['LOCAL_API_KEY']})
            r.raise_for_status(); raw = r.json()
        output = parse_output(raw['choices'][0]['message']['content']); error = None
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        output = None; error = {'type':type(exc).__name__, 'http_status':getattr(getattr(exc,'response',None),'status_code',None)}
    envelope=raw if isinstance(raw,dict) else {}
    return {'output':output,'error':error,'raw':raw,'usage':envelope.get('usage',{}),
            'stats':envelope.get('stats',{}),'latency_ms':(time.perf_counter()-started)*1000,'cost_usd':0.}

def summarize(rows):
    lat = [r['local']['latency_ms']/1000 for r in rows]
    speed = [r['local']['stats']['tokens_per_second'] for r in rows if 'tokens_per_second' in r['local']['stats']]
    ttft = [r['local']['stats']['time_to_first_token_seconds'] for r in rows if 'time_to_first_token_seconds' in r['local']['stats']]
    return {'n':len(rows),'correct':sum(r['score']['correct'] for r in rows),
            'quality':sum(r['score']['correct'] for r in rows)/len(rows),
            'latency_mean_s':statistics.mean(lat), 'latency_p50_s':float(np.quantile(lat,.5)),
            'latency_p95_s':float(np.quantile(lat,.95)), 'decode_tps_median':statistics.median(speed) if speed else None,
            'ttft_median_s':statistics.median(ttft) if ttft else None,
            'errors':sum(bool(r['local']['error']) for r in rows),
            'by_category':{c:{'n':len(sub),'correct':sum(r['score']['correct'] for r in sub)}
                           for c in sorted({r['sample']['category'] for r in rows})
                           if (sub := [r for r in rows if r['sample']['category']==c])},
            'by_language':{c:{'n':len(sub),'correct':sum(r['score']['correct'] for r in sub)}
                           for c in sorted({r['sample']['language'] for r in rows})
                           if (sub := [r for r in rows if r['sample']['language']==c])}}

def run(n, models, transport, samples_path=None, guard=False):
    unknown = set(models) - {key for key, _ in CANDIDATES}
    if unknown:
        raise ValueError('Unknown candidate model keys: ' + ', '.join(sorted(unknown)))
    load_env()
    if transport == 'api' and not os.getenv('LOCAL_API_KEY'):
        raise RuntimeError('LOCAL_API_KEY is required for HTTP API; configure project .env locally')
    inventory = cli_json('ls','--json'); loaded = cli_json('ps','--json')
    missing = set(models) - {m['modelKey'] for m in inventory}
    if missing:
        raise ValueError('Requested models absent from inventory: ' + ', '.join(sorted(missing)))
    # Never unload a model belonging to another task.
    if any(not m['identifier'].startswith('home-') for m in loaded):
        raise RuntimeError('An unrelated model is loaded; finish its work before serial benchmark')
    for m in loaded:
        unloaded = command([LMS,'unload',m['identifier']])
        if unloaded.returncode or any(p['identifier']==m['identifier'] for p in cli_json('ps','--json')):
            raise RuntimeError('Own previous model could not be unloaded')
    directory = ROOT/'results'/('20261001_'+datetime.now(timezone.utc).strftime('%H%M%SZ')+'_'+uuid.uuid4().hex[:8]+'_'+transport)
    directory.mkdir(exist_ok=False)
    if samples_path:
        samples=[json.loads(line) for line in Path(samples_path).read_text(encoding='utf-8').splitlines()]
        if not samples or any(s.get('split')!='dev' for s in samples):
            raise ValueError('Custom samples must be explicitly developmental')
        if n!=len(samples):
            raise ValueError('n must equal the custom development sample count')
        # Counterbalance adjacent EN/RU pairs; preserve the source file verbatim.
        if len(samples)%2==0 and all(samples[i]['group']==samples[i+1]['group'] and {samples[i]['language'],samples[i+1]['language']}=={'en','ru'} for i in range(0,len(samples),2)):
            samples=[s for i in range(0,len(samples),2) for s in (samples[i:i+2] if (i//2)%2==0 else samples[i:i+2][::-1])]
    else:
        samples = choose_samples(n)
    write(directory/'samples_dev.json',samples); write(directory/'inventory.json',inventory)
    (directory/'system_prompt.txt').write_text(SYSTEM_PROMPT,encoding='utf-8')
    manifest = {'run_id':directory.name,'started_utc':now(),'state':'running','phase':'development_only',
                'transport':transport,'dataset_split':'custom_dev' if samples_path else 'old_dev','sample_ids':[s['id'] for s in samples],
                'dataset_sha256':hashlib.sha256(Path(samples_path or ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest(),
                'prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                'context':4096,'parallel':1,'reasoning':'requested off; verify observed channels per raw response','temperature':0 if transport=='api' else 'CLI default UNKNOWN',
                'max_tokens':512 if transport=='api' else 'CLI default UNKNOWN', 'cloud_calls':0,
                'historical_test_used_for_selection':False,'models':{},'python':sys.version,
                'latency_kind':'measured CLI process wall time' if transport=='cli' else 'measured HTTP wall time',
                'note':'CLI diagnostics cannot establish a frozen HTTP protocol' if transport=='cli' else 'controlled development; not independent final test'}
    manifest['resource_guard']={'enabled':guard,'min_ram_gib_during_load':2,'min_gpu_free_mib_during_load':512}
    manifest['harness_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source_root=Path(__file__).resolve().parents[1]/'src/agro_route'
    manifest['core_source_sha256']={name:hashlib.sha256((source_root/name).read_bytes()).hexdigest()
        for name in ('models.py','routing.py','evaluation.py','tools.py')}
    write(directory/'manifest.json',manifest)
    for key, gpu in CANDIDATES:
        if key not in models: continue
        identifier='home-'+key
        info = next(m for m in inventory if m['modelKey']==key)
        rows=[]; monitor=Monitor()
        meta={'inventory':info,'requested_offload':gpu,'load_success':False}
        try:
            with monitor:
                load_start=time.perf_counter()
                load_args=[LMS,'load',key,'--context-length','4096','--parallel','1','--gpu',gpu,'--identifier',identifier,'--yes']
                estimate=command([*load_args,'--estimate-only'])
                meta['preflight_estimate_returncode']=estimate.returncode
                (directory/(key+'_estimate.txt')).write_text(ANSI.sub('',estimate.stdout+'\n'+estimate.stderr),encoding='utf-8')
                if estimate.returncode:
                    raise RuntimeError('Preflight estimate failed; loading not attempted')
                meta['load_attempted']=True
                if guard:
                    load=guarded_load(load_args,directory/(key+'_load.txt'),meta)
                else:
                    load=command(load_args)
                    (directory/(key+'_load.txt')).write_text(ANSI.sub('',load.stdout).replace('\r','\n'),encoding='utf-8')
                meta.update(load_s=time.perf_counter()-load_start,load_success=load.returncode==0)
                if load.returncode:
                    meta['phase_error']={'type':'LoadNonzero','returncode':load.returncode}
                if load.returncode==0:
                    meta['loaded_state']=cli_json('ps','--json')
                    # First inference remains visible; no unreported scored warmup.
                    with (directory/(key+'_raw.jsonl')).open('x',encoding='utf-8') as f:
                        for i,sample in enumerate(samples):
                            if guard:
                                h=resource_headroom()
                                if h['ram_available_gib']<2 or h['gpu_free_mib']<512:
                                    meta['resource_guard_stop']=h
                                    raise RuntimeError('Insufficient headroom before inference')
                            result=(api_call if transport=='api' else cli_call)(identifier,sample)
                            row={'sample':sample,'local':result,'score':score(sample,result['output'])}
                            f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush(); rows.append(row)
                            print(f"{key} {i+1}/{n} correct={row['score']['correct']} seconds={result['latency_ms']/1000:.3f} error={result['error']}",flush=True)
                            if i>=5 and sum(bool(r['local']['error']) for r in rows)>=4:
                                meta['early_stop']='four errors among first requests'; break
        except (subprocess.TimeoutExpired,OSError,RuntimeError,ValueError) as exc:
            meta['phase_error']={'type':type(exc).__name__}
        finally:
            meta.update(monitor.summary()); meta['summary']=summarize(rows) if rows else None
            write(directory/(key+'_resources.json'),monitor.rows)
            manifest['models'][key]=meta; write(directory/'manifest.json',manifest)
            # Clean up only this task's exact identifier, including partial loads.
            try:
                current=cli_json('ps','--json')
                if meta.get('load_attempted') or any(m['identifier']==identifier for m in current):
                    unloaded=command([LMS,'unload',identifier])
                    meta['unload_success']=unloaded.returncode==0 and not any(m['identifier']==identifier for m in cli_json('ps','--json'))
                    if not meta['unload_success']:
                        manifest['state']='partial_cleanup_failed'; write(directory/'manifest.json',manifest)
                        raise RuntimeError('Own model could not be unloaded; stop before another model')
            except (subprocess.TimeoutExpired,OSError) as exc:
                manifest['state']='partial_cleanup_failed'; meta['cleanup_error']={'type':type(exc).__name__}
                write(directory/'manifest.json',manifest); raise RuntimeError('LM Studio cleanup failed') from None
            write(directory/'manifest.json',manifest)
            if meta.get('resource_guard_stop') or (meta.get('phase_error') and meta.get('load_attempted') and not meta['load_success']):
                # A cancelled CLI does not prove a backend loading job stopped.
                # Fail closed even after a successful exact-identifier unload.
                manifest['state']='stopped_after_uncertain_load'; manifest['finished_utc']=now()
                write(directory/'manifest.json',manifest)
                raise RuntimeError('Stopped after incomplete loading; inspect backend before another model')
        print('MODEL SUMMARY '+json.dumps({'model':key,**(meta['summary'] or {}),**monitor.summary()}),flush=True)
    manifest['state']='completed_with_model_failures' if any(m.get('phase_error') for m in manifest['models'].values()) else 'completed'
    manifest['finished_utc']=now(); write(directory/'manifest.json',manifest)
    print('RESULTS '+str(directory),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--n',type=int,default=12)
    parser.add_argument('--transport',choices=['cli','api'],default='cli')
    parser.add_argument('--models',nargs='+',default=[m[0] for m in CANDIDATES[:4]])
    parser.add_argument('--samples-path',type=Path)
    parser.add_argument('--all-text-models',action='store_true')
    parser.add_argument('--resource-guard',action='store_true')
    args=parser.parse_args(); run(args.n,[m[0] for m in CANDIDATES] if args.all_text_models else args.models,args.transport,args.samples_path,args.resource_guard)

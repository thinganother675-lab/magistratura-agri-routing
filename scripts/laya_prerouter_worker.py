"""Persistent CPU-only Laya worker; local JSON-lines transport, no hosted inference."""
from pathlib import Path
import os
import sys
import json
import time
import contextlib

ROOT=Path(__file__).resolve().parents[1]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',USE_TF='0',CUDA_VISIBLE_DEVICES='',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_TELEMETRY='1')
def offline_audit(event,args):
    if event=='socket.connect':
        address=args[1]
        if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1','localhost'):
            raise RuntimeError('External network disabled in local Laya worker')
sys.addaudithook(offline_audit)

def emit(value):
    print(json.dumps(value,ensure_ascii=True,allow_nan=False),flush=True)

def main():
    # Isolated CPU environment intentionally has no project HTTP adapter stack.
    # Only this permitted contract is consumed; sample/gold files are never read.
    questions=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['router_questions']
    import torch
    import psutil
    import laya
    torch.set_num_threads(4)
    torch.manual_seed(0)
    started=time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        agent=laya.load(str(ROOT/'.runtime/jev/models/laya-multilingual'),device='cpu',fast=False,compile=False,
                        expected_sha256={'model.safetensors':'9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204',
                                         'tokenizer/tokenizer.json':'609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f'})
        load=time.perf_counter()-started
        warm=time.perf_counter()
        agent.predict('Which soil? Context: loam.',questions,max_len=1024,head_max_len=256)
        warm=time.perf_counter()-warm
    process=psutil.Process()
    emit({'ready':True,'model':'convaiinnovations/laya-multilingual','revision':'e4e9ddf21a7b1903b7acffd8814ad4307bf63a67',
          'device':'cpu','dtype':'float32','threads':4,'load_s':load,'warmup_s':warm,'rss_bytes':process.memory_info().rss,
          'max_len':1024,'head_max_len':256,'external_inference_disabled':True,'temperature':[1.,1.,1.]})
    for line in sys.stdin:
        try:
            body=json.loads(line)
            if body.get('stop'): break
            began=time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                raw=agent.predict(body['state'],questions,max_len=1024,head_max_len=256)
            emit({'raw':raw,'latency_ms':(time.perf_counter()-began)*1000,'rss_bytes':process.memory_info().rss,
                  'error':None,'truncation_metadata':{k:raw.get('usage',{}).get(k) for k in ('truncated','state_tokens','state_tokens_dropped','truncated_questions')},
                  'truncation_note':'fixed1024 input/head256; inspect raw metadata, unreported truncation UNKNOWN'})
        except Exception as exc:
            emit({'error':{'type':type(exc).__name__},'raw':None})

if __name__=='__main__': main()

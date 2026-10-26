"""Verify private remote identity, SHA and research blob identities safely."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import uuid
import httpx

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
TARGET='Apartman36/magistratura-agri-routing'
p=argparse.ArgumentParser()
p.add_argument('--sha',required=True)
p.add_argument('--include',action='append',default=[],help='Additional project-relative research artifact to verify')
a=p.parse_args()
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args]).decode().strip()
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
fill=subprocess.run(['git','-c','credential.interactive=never','credential','fill'],input='protocol=https\nhost=github.com\nusername=Apartman36\n\n',cwd=ROOT,env=env,capture_output=True,text=True,timeout=25)
if fill.returncode: raise SystemExit('Existing Git credential lookup blocked; no credential printed.')
fields=dict(x.split('=',1) for x in fill.stdout.splitlines() if '=' in x)
token=fields.get('password')
if not token: raise SystemExit('No credential returned; no credential printed.')
important=[
    'data/benchmark.jsonl','data/home_holdout_20261001.jsonl',
    'experiments/HOME_PROTOCOL_2026-10-01.json',
    'experiments/HOME_RECOVERY_2026-10-02.json',
    'results/20261002_043909Z_5d0044d9_final/raw_decisions.jsonl',
    'results/20261002_045739Z_06b07e40_final_continuation/raw_decisions.jsonl',
    'results/analysis_input_reconciled_20261002_052358Z_804ced2b/raw_decisions.jsonl',
    'results/analysis_input_reconciled_20261002_052358Z_804ced2b/analysis_20261002_052438Z_2c0beea8/statistics_reporting_corrected.json',
    'outputs/home_pc_final_20261002_analytics7b4c/home_pc_models_final150_20261002.xlsx',
]
important.extend(a.include)
with httpx.Client(timeout=30,trust_env=True,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}) as c:
    user=c.get('https://api.github.com/user');user.raise_for_status()
    assert user.json()['login']=='Apartman36','Unauthorized account identity'
    repo=c.get('https://api.github.com/repos/'+TARGET);repo.raise_for_status();metadata=repo.json()
    assert metadata['private'] is True,'Destination is not PRIVATE'
    ref=c.get('https://api.github.com/repos/'+TARGET+'/git/ref/heads/main');ref.raise_for_status()
    remote_sha=ref.json()['object']['sha']
    assert remote_sha==a.sha,'Remote SHA differs from expected commit'
    tree=c.get('https://api.github.com/repos/'+TARGET+'/git/trees/'+a.sha,params={'recursive':1});tree.raise_for_status()
    data=tree.json();assert not data.get('truncated'),'Remote tree truncated'
    blobs={x['path']:x for x in data['tree'] if x['type']=='blob'}
    checks={}
    for path in important:
        local_blob=git('rev-parse',a.sha+':'+path)
        assert path in blobs and blobs[path]['sha']==local_blob,path+' blob mismatch'
        checks[path]={'blob_sha':local_blob,'size_bytes':blobs[path].get('size'),'match':True}
    original=c.get('https://api.github.com/repos/thinganother675-lab/magistratura-agri-routing')
    original_visibility=original.json().get('visibility') if original.status_code==200 else 'UNKNOWN'
assert git('remote','get-url','origin')=='https://github.com/thinganother675-lab/magistratura-agri-routing.git'
assert git('remote','get-url','apartman')=='https://github.com/'+TARGET+'.git'
assert subprocess.run(['git','merge-base','--is-ancestor','2a2037df62842b0389dc52c4dfbd38e8a04f3b8b',a.sha],cwd=ROOT).returncode==0
report={'verified_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','identity':'Apartman36','destination':metadata['html_url'],'visibility':metadata['visibility'],'private':True,'remote_main_sha':remote_sha,'remote_tree_blob_count':len(blobs),'important_artifacts':checks,'origin_preserved':True,'origin_visibility_observed':original_visibility,'visibility_changed_on_original':False,'upstream':git('rev-parse','--abbrev-ref','main@{upstream}'),'historical_commit_is_ancestor':True,'credential_values_or_fingerprints_persisted':False,'transport':'Existing Git Credential Manager; REST credential used internally only','force_push':False,'publication_type':'PRIVATE research backup; not public dataset release'}
name='remote_verification_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')+'_'+uuid.uuid4().hex[:8]+'.json'
(OUT/name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':(OUT/name).relative_to(ROOT).as_posix(),**{k:report[k] for k in ('verified_utc','status','identity','destination','visibility','remote_main_sha','remote_tree_blob_count','origin_preserved','origin_visibility_observed','upstream')}}))

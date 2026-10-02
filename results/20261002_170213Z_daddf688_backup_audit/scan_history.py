"""Scan Git history and prospective files without printing matched values.

Scope: all objects reachable from current refs, tracked current working files,
and nonignored untracked files. Exact project credentials are used in memory.
The conservative pattern scan is evidence, not a guarantee about unknown keys.
"""
from __future__ import annotations
from collections import Counter
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output-name', default='security_history_audit.json')
args=parser.parse_args()
if Path(args.output_name).name != args.output_name or not args.output_name.endswith('.json'):
    raise SystemExit('Output must be a plain JSON filename inside the audit directory.')
spec=importlib.util.spec_from_file_location('publication_scanner', ROOT/'scripts/scan_public_artifacts.py')
scanner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
allow=set(scanner.KEY_NAMES)|{'openrouter_api_key_2','OPENROUTER_API_KEY_2',
    'OPENROUTER_INFERENCE_KEY_ZERO_20261002'}
secrets=[]
credential_names=[]
for name in allow:
    if os.environ.get(name):
        secrets.append(os.environ[name].encode()); credential_names.append('process_env:'+name)
envfile=ROOT/'.env'
if envfile.is_file():
    for line in envfile.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name,value=line.split('=',1)
            if name.strip() in allow and value.strip().strip('\"\''):
                secrets.append(value.strip().strip('\"\'').encode())
                credential_names.append('project_env:'+name.strip())
secrets=list(set(secrets))
patterns={k:re.compile(v.pattern.encode(), v.flags & ~re.UNICODE) for k,v in scanner.PATTERNS.items()}
assignment=re.compile(scanner.ASSIGNMENT.pattern.encode().replace(b'openrouter_api_key|', b'openrouter_api_key_2|openrouter_api_key|'), scanner.ASSIGNMENT.flags & ~re.UNICODE)
findings=[]
archive_members=0
archive_bytes=0
def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])
def inspect(label, data, *, oid=None):
    global archive_members,archive_bytes
    base={'path':label}
    if oid: base['git_object']=oid
    if any(secret in data for secret in secrets):
        findings.append({**base,'rule':'configured_credential_exact_match'})
    for rule,pattern in patterns.items():
        if pattern.search(data): findings.append({**base,'rule':rule})
    for matched in assignment.finditer(data):
        if matched.group(1).decode('ascii','ignore').lower() not in scanner.PLACEHOLDERS:
            findings.append({**base,'rule':'literal_credential_assignment'})
    stream=io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                if info.file_size>64*1024*1024:
                    findings.append({**base,'rule':'archive_member_oversize_requires_review','member':info.filename}); continue
                payload=z.read(info)
                archive_members+=1;archive_bytes+=len(payload)
                if any(secret in payload for secret in secrets) or any(p.search(payload) for p in patterns.values()):
                    findings.append({**base,'rule':'credential_in_archive_member','member':info.filename})

paths={}
for record in git('rev-list','--objects','--all').decode().splitlines():
    pieces=record.split(' ',1)
    paths[pieces[0]]=pieces[1] if len(pieces)>1 else '<commit-or-tree>'
objects=[]
for record in subprocess.check_output(['git','-C',str(ROOT),'cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'], input=('\n'.join(paths)+'\n').encode()).decode().splitlines():
    oid,kind,size=record.split();objects.append((oid,kind,int(size)))
counts=Counter(kind for _,kind,_ in objects)
large=sorted([{'object':oid,'path':paths[oid],'size_bytes':size} for oid,kind,size in objects if kind=='blob'], key=lambda r:r['size_bytes'],reverse=True)
history_paths_sensitive=[]
for oid,kind,size in objects:
    if kind=='blob' and scanner.sensitive_filename(Path(paths[oid])):
        history_paths_sensitive.append({'object':oid,'path':paths[oid]})
    if kind not in ('blob','commit'): continue
    if size>64*1024*1024:
        findings.append({'path':paths[oid],'git_object':oid,'rule':'oversize_object_requires_review'});continue
    inspect(paths[oid],git('cat-file',kind,oid),oid=oid)
current={p.decode() for p in git('ls-files','--cached','--others','--exclude-standard','-z').split(b'\0') if p}
current_sensitive=[]
current_large=[]
current_hashes={}
for name in sorted(current):
    path=ROOT/name
    if not path.is_file(): continue
    if scanner.sensitive_filename(path): current_sensitive.append(name)
    if path.is_symlink(): findings.append({'path':name,'rule':'symlink_requires_review'});continue
    data=path.read_bytes()
    if len(data)>64*1024*1024:
        current_large.append({'path':name,'size_bytes':len(data)});continue
    inspect(name,data)
    current_hashes[name]=hashlib.sha256(data).hexdigest()
if history_paths_sensitive: findings.extend({**x,'rule':'sensitive_filename_history'} for x in history_paths_sensitive)
if current_sensitive: findings.extend({'path':x,'rule':'sensitive_filename_current'} for x in current_sensitive)
if current_large: findings.extend({**x,'rule':'oversize_current_requires_review'} for x in current_large)
report={
    'checked_utc':datetime.now(timezone.utc).isoformat(),
    'status':'PASS' if not findings else 'REVIEW_REQUIRED',
    'head':git('rev-parse','HEAD').decode().strip(),
    'refs':git('show-ref').decode().splitlines(),
    'scope':'all Git objects reachable from current refs; current tracked and nonignored untracked files',
    'reachable_object_counts':dict(counts),
    'historical_blobs_checked':counts['blob'],
    'commit_messages_checked':counts['commit'],
    'prospective_current_file_count':len(current_hashes),
    'credential_source_names_used_for_exact_in_memory_matching':sorted(set(credential_names)),
    'credential_values_or_fingerprints_persisted':False,
    'archive_members_checked':archive_members,'archive_uncompressed_bytes_checked':archive_bytes,
    'findings':findings,'sensitive_filenames_in_history':history_paths_sensitive,
    'largest_historical_blobs':large[:15],
    'git_large_file_threshold_50MiB_count':sum(x['size_bytes']>=50*1024*1024 for x in large),
    'git_hard_limit_100MiB_count':sum(x['size_bytes']>=100*1024*1024 for x in large),
    'file_sha256':current_hashes,
    'limitations':['Only project-configured credential exact matches and known token patterns are checked.',
                  'Unknown opaque credentials and binary image content cannot be ruled out by pattern scanning.',
                  'New files created after checked_utc require a fresh pre-commit scan.'],
}
(OUT/args.output_name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:report[key] for key in ('checked_utc','status','head','reachable_object_counts','historical_blobs_checked','commit_messages_checked','prospective_current_file_count','archive_members_checked','findings','git_large_file_threshold_50MiB_count','git_hard_limit_100MiB_count')}))

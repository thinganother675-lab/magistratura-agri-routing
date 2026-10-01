"""Validate recorded assets/protocol and reproduce final statistics from cache."""
import hashlib
import json
from pathlib import Path
import shutil
import uuid
from agro_route.analysis import analyze

ROOT=Path(__file__).resolve().parents[1]
run=ROOT/'results/20260930T182756Z_6703e43b'
manifest=json.loads((run/'manifest.json').read_text())
protocol=json.loads((ROOT/'data/protocol_frozen.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert manifest['state']=='completed' and manifest['n']==90
assert sha(ROOT/'data/benchmark.jsonl')==manifest['dataset_sha256']==protocol['dataset_sha256']
assert sha(ROOT/'data/protocol_frozen.json')==manifest['protocol_sha256']
core=['models.py','routing.py','evaluation.py','benchmark.py','tools.py','cli.py']
for name in core:
    p=ROOT/'src/agro_route'/name
    assert sha(p)==manifest['code_sha256'][str(p.relative_to(ROOT))], name+' changed since test'
(ROOT/'.cache/reproducibility').mkdir(parents=True,exist_ok=True)
copy=ROOT/'.cache/reproducibility'/('statistics_'+uuid.uuid4().hex[:8])
copy.mkdir(exist_ok=False)
for name in ['pairs.jsonl','normalized.jsonl']:
    shutil.copyfile(run/name,copy/name)
reproduced=analyze(copy)
original=json.loads((run/'analysis.json').read_text())
assert json.loads((copy/'analysis.json').read_text())==original, 'Serialized statistics are not exactly reproduced'
report={'final_run':run.name,'dataset_and_protocol_hashes_match':True,'core_model_policy_scoring_hashes_match':True,'cached_statistics_exactly_reproduced':True,'reproduction_folder':str(copy.relative_to(ROOT)),'post_start_changed_report_modules':[name for name in ['analysis.py','web.py'] if sha(ROOT/'src/agro_route'/name)!=manifest['code_sha256'][str((ROOT/'src/agro_route'/name).relative_to(ROOT))]],'note':'Additional reporting metrics and live UI validation/stages were added after test started; model prompt, core scoring, routing and thresholds unchanged.'}
(ROOT/'.runtime/reproducibility_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

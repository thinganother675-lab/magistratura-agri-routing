from pathlib import Path
import sys, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')
root = Path('C:/sarychev/Codex/magistratura')
sys.path.insert(0,str(root/'src'))
from agro_route.mera_adapter_20261003 import adapt_row
data=json.loads((root/'tmp/mera_examples/rows.json').read_text(encoding='utf-8'))
metrics=[]
for model in ['qwen3.5-9b','qwen3.8-27b']:
    metrics.append({r['item_id']:r for r in map(json.loads,(root/f'results/20261003_local_screen_571682f5/dev293/{model}_metrics.jsonl').read_text(encoding='utf-8').splitlines())})
checked=[]
for entry in data['rows']:
    row=entry['row']; item=adapt_row(row,'dev'); m9,m27=[m[item.item_id] for m in metrics]
    assert hashlib.sha256(item.prompt.encode()).hexdigest()==m9['prompt_sha256']==m27['prompt_sha256']
    if not m9['gold_valid']:continue
    checked.append((row,m9,m27))
for row,m9,m27 in checked:
    if m9['strict_set_em']!=m27['strict_set_em'] or row['meta']['id']==0:
        print(json.dumps({'id':row['meta']['id'],'domain':row['meta']['domain'],'q':row['inputs']['question'],'options':{k:v for k,v in row['inputs'].items() if k!='question' and v},'gold':row['outputs'],'em9':m9['strict_set_em'],'em27':m27['strict_set_em']},ensure_ascii=False))

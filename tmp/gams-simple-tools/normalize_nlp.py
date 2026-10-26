from pathlib import Path
import csv
root=Path('C:/sarychev/Codex/magistratura')
folder=root/'tmp/gams-simple-tools/normalized8/results'
folder.mkdir(parents=True,exist_ok=True)
rows=[]
for r in csv.DictReader((root/'coursework/gams-2026/STUDY_SIMPLE_VARIANT8/lab8/results.csv').open()):
    d=dict(r)
    d['scenario_id']=r['case_id']
    d['mk_hours']=r['mainline_hours']
    d['cream_hours']=r['creamline_hours']
    d['curds_hours']=r['curdsline_hours']
    d['objective_rub']=r['revenue_rub']
    for j in ['milk','kefir','cream','curds']:
        d['q_'+j]=r['x_'+j]
    rows.append(d)
assert len(rows)==63
best={}
for r in rows:
    key=r['scenario_id']
    if key not in best or float(r['objective_rub'])>float(best[key]['objective_rub']):best[key]=r

def write(name,data):
    with (folder/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(data)
write('base_results.csv',[best['base']])
write('base_starts.csv',[r for r in rows if r['scenario_id']=='base'])
write('scenario_results.csv',[r for key,r in best.items() if key!='base'])
write('scenario_starts.csv',[r for r in rows if r['scenario_id']!='base'])
source=(root/'tmp/gams-future-tools/verify_nlp.py').read_text(encoding='utf-8-sig')
source=source.replace("base=ROOT/'coursework/gams-2026/lab8-variant8'","base=ROOT/'tmp/gams-simple-tools/normalized8'")
(root/'tmp/gams-simple-tools/verify_nlp_simple.py').write_text(source,encoding='utf-8')

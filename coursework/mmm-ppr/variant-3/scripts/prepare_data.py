"""Validate editable scenario inputs and emit GAMS includes."""
from common import ROOT, write_csv, write_json
import csv, shutil, math

PRODUCTS = ['milk','kefir','cream','yogurt']
P = [24000,27000,138000,22000]
A = [1.01,1.01,9.45,.9]
EP = [-.033,-.034,-.060,-.051]
EA = [-.020,-.012,-.019,-.014]
LOW = [25,30,1.5,1]

def main():
    source = ROOT.parent / 'audit-2026-10-07/sources/dea-variant-3.csv'
    # The supplied, visually verified CSV is the portable input. The original
    # audit source is needed only when constructing a fresh workspace copy.
    if not (ROOT/'data/dea-variant-3.csv').exists():
        shutil.copyfile(source, ROOT/'data/dea-variant-3.csv')
    path = ROOT/'data/scenarios.csv'
    if not path.exists():
        configs=[('base',{})]
        for f in [.8,.9,1.1,1.2]: configs.append((f'raw_{int(100*f)}',{'raw_t':1400*f}))
        for f in [.8,.9,1.1]: configs.append((f'mk_time_{int(100*f)}',{'mk_hours':21*f}))
        for f in [.8,.9,1.1]: configs.append((f'cy_time_{int(100*f)}',{'cy_hours':18*f}))
        for prod,p in zip(PRODUCTS,P):
            for f in [.9,1.1]: configs.append((f'{prod}_price_{int(100*f)}',{f'p_{prod}':p*f}))
        configs.append(('combined',{'raw_t':1540,'mk_hours':18.9,'cy_hours':19.8}))
        rows=[]
        for sid,changes in configs:
            row=dict(scenario_id=sid,raw_t=1400,mk_hours=21,cy_hours=18)
            for prod,p in zip(PRODUCTS,P): row['p_'+prod]=p
            row.update(changes); rows.append(row)
        write_csv('data/scenarios.csv',rows)
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    assert len(rows)>=20, 'At least 20 scenarios required'
    assert len({r['scenario_id'] for r in rows})==len(rows), 'Duplicate scenario ID'
    assert len({tuple(r[k] for k in r if k!='scenario_id') for r in rows})==len(rows), 'Repeated input conditions'
    raw_min=sum(a*q*(q/100)**e for a,q,e in zip(A,LOW,EA))
    for row in rows:
        assert row['scenario_id'].replace('_','').isalnum(), 'Unsafe scenario ID'
        assert all(math.isfinite(float(v)) and float(v)>0 for k,v in row.items() if k!='scenario_id')
        assert float(row['raw_t'])>=raw_min and float(row['mk_hours'])>=1 and float(row['cy_hours'])>=1, 'Infeasible minimum output'
    keys=['raw_t','mk_hours','cy_hours']+['p_'+p for p in PRODUCTS]
    text='Set s / '+','.join(r['scenario_id'] for r in rows)+' /;\n'
    text+='Table cond(s,*)\n'+' '*24+''.join(f'{k:>18}' for k in keys)+'\n'
    text+='\n'.join(f"{r['scenario_id']:<24}"+''.join(f'{float(r[k]):18.8f}' for k in keys) for r in rows)+'\n;\n'
    (ROOT/'models/scenarios.inc').write_text(text,encoding='ascii')
    dea=list(csv.DictReader((ROOT/'data/dea-variant-3.csv').open(encoding='utf-8-sig')))
    assert len(dea)==25 and [int(r['firm']) for r in dea]==list(range(1,26))
    assert all(int(r[k])>=0 for r in dea for k in ['y1','y2','x1','x2'])
    text='Table d(i,*)\n'+' '*8+''.join(f'{k:>12}' for k in ['y1','y2','x1','x2'])+'\n'
    text+='\n'.join(f"{'f'+r['firm']:<8}"+''.join(f'{int(r[k]):12d}' for k in ['y1','y2','x1','x2']) for r in dea)+'\n;\n'
    (ROOT/'models/dea-data.inc').write_text(text,encoding='ascii')
    write_json('results/input_validation.json',{'variant':3,'scenarios':len(rows),'dea_firms':25,'minimum_raw_t':raw_min,'valid':True})
    print('Validated',len(rows),'scenarios and 25 DEA firms')

if __name__=='__main__': main()

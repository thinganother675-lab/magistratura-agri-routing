"""Compare GAMS to independent solvers and recompute feasibility from inputs."""
from common import ROOT,write_json,write_csv
import csv,json
import numpy as np
from prepare_data import PRODUCTS,A,EA,LOW,EP

def read(name): return list(csv.DictReader((ROOT/'results'/name).open(encoding='utf-8-sig')))
def accepted(rows,nlp=False):
    assert all(int(r['modelstat']) in ([1,2] if nlp else [1]) and int(r['solvestat'])==1 for r in rows)

def main():
    lp=read('lab2_gams.csv'); accepted(lp)
    expected=json.loads((ROOT/'results/lab2.json').read_text(encoding='utf-8'))
    actual=np.array([float(r['x_centner']) for r in lp]); diff=float(max(abs(actual-np.array(expected['x']))))
    assert diff<1e-7 and abs(float(lp[0]['revenue_rub'])-expected['objective_rub'])<1e-5
    gg=read('lab8_gams_scenarios.csv'); pp=read('lab8_python_scenarios.csv'); starts=read('lab8_gams_starts.csv')
    accepted(gg,True); accepted(starts,True)
    assert len(gg)>=20 and len(starts)==len(gg)*3
    pby={r['scenario_id']:r for r in pp}; inputby={r['scenario_id']:r for r in csv.DictReader((ROOT/'data/scenarios.csv').open(encoding='utf-8-sig'))}
    assert set(pby)==set(inputby)=={r['scenario_id'] for r in gg}
    checked=[]; maxobjgap=0.;maxqgap=0.
    for r in gg:
        pr=pby[r['scenario_id']]; inp=inputby[r['scenario_id']]
        assert all(abs(float(r[k])-float(v))<1e-6 for k,v in inp.items() if k!='scenario_id')
        q=np.array([float(r['q_'+p]) for p in PRODUCTS]); price=np.array([float(inp['p_'+p]) for p in PRODUCTS])
        rawuse=sum(np.array(A)*q*(q/100)**np.array(EA)); mk=q[0]/50+q[1]/60;cy=q[2]/3+q[3]/2
        violation=max(0.,rawuse-float(inp['raw_t']),mk-float(inp['mk_hours']),cy-float(inp['cy_hours']),float(max(np.array(LOW)-q)))
        assert violation<2e-5,(r['scenario_id'],violation)
        obj=float(sum(price*q*(q/100)**np.array(EP)))
        rel=abs(obj-float(pr['objective_rub']))/obj
        qgap=float(max(abs(q-np.array([float(pr['q_'+p]) for p in PRODUCTS]))))
        assert rel<1e-7 and abs(obj-float(r['objective_rub']))<.01
        assert float(pr['global_upper_bound_rub'])>=obj-.02
        assert (float(pr['global_upper_bound_rub'])-obj)/obj<1e-6
        assert int(r['convex_modelstat']) in [1,2] and int(r['convex_solvestat'])==1
        maxobjgap=max(maxobjgap,rel); maxqgap=max(maxqgap,qgap)
        result=dict(r)
        result.update(raw_used=rawuse,mk_used=mk,cy_used=cy,max_violation=violation,independent_objective_relative_gap=rel,global_upper_bound_rub=float(pr['global_upper_bound_rub']),global_gap_relative=(float(pr['global_upper_bound_rub'])-obj)/obj,status='GLOBAL_OPTIMUM_NUMERICALLY_VERIFIED')
        result.update(q0_t=100,speed_milk_t_per_h=50,speed_kefir_t_per_h=60,speed_cream_t_per_h=3,speed_yogurt_t_per_h=2)
        for p,a,ep,ea in zip(PRODUCTS,A,EP,EA):result.update({f'a_{p}':a,f'ep_{p}':ep,f'ea_{p}':ea})
        for p,lower in zip(PRODUCTS,LOW):result[f'lower_{p}_t']=lower
        checked.append(result)
    write_csv('results/lab8_final_scenarios.csv',checked)
    # Explicit text table required by teacher, UTF-8 TSV including all inputs.
    with (ROOT/'results/lab8_scenarios_table.txt').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(checked[0]),delimiter='\t');w.writeheader();w.writerows(checked)
    gd=read('lab10_gams_dea.csv');pd=read('lab10_python_dea.csv'); accepted(gd)
    assert len(gd)==len(pd)==25
    kgap=max(abs(float(a['efficiency'])-float(b['efficiency'])) for a,b in zip(gd,pd))
    assert [int(r['firm']) for r in gd]==list(range(1,26)) and kgap<1e-9
    # Check GAMS's own reference weights; Python phase2 peers may differ.
    matrix=np.array([[float(r[k]) for k in ['x1','x2','y1','y2']] for r in pd])
    peers=read('lab10_gams_peers.csv');maxpeer=0.
    for i,r in enumerate(gd):
        lam=np.zeros(25)
        for p in peers:
            if int(p['firm'])==i+1:lam[int(p['peer'])-1]=float(p['weight'])
        phi=float(r['phi']); target=matrix.T@lam
        violation=max(0,float(max(target[:2]-matrix[i,:2])),float(max(phi*matrix[i,2:]-target[2:])),abs(sum(lam)-1),float(-min(lam)))
        assert violation<1e-5; maxpeer=max(maxpeer,violation)
    out=dict(all_passed=True,lab2_max_variable_difference=diff,lab8_scenarios=len(gg),lab8_gams_original_runs=len(starts),lab8_transformed_runs=len(gg),lab8_max_objective_relative_difference=maxobjgap,lab8_max_q_absolute_difference_t=maxqgap,lab10_firms=25,lab10_max_efficiency_difference=kgap,lab10_max_gams_peer_violation=maxpeer,nlp_certificate_relative_tolerance=1e-6)
    write_json('results/verification.json',out)
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()

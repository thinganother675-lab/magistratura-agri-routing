from pathlib import Path
import sys,csv,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'coursework/mmm-ppr/variant-11/runtime/python_packages'))
import numpy as np
from scipy.optimize import minimize, nnls
base=ROOT/'coursework/gams-2026/lab8-variant8'
a0=np.array([1.01,1.01,9.45,14.])
ep=np.array([-.034,-.022,-.022,-.027])
ea=np.array([-.017,-.012,-.011,-.010])
qlo=np.array([25.,30.,1.5,1.25])
beta=(1+ep)/(1+ea); gamma=1/(1+ea)
assert np.all((beta>0)&(beta<1)) and np.all(gamma>1)

def check(row):
    prices=np.array([float(row['p_'+k]) for k in ('milk','kefir','cream','curds')])
    cap=np.array([float(row[k]) for k in ('raw_t','mk_hours','cream_hours','curds_hours')])
    q=np.array([float(row['q_'+k]) for k in ('milk','kefir','cream','curds')])
    qhi=np.array([50*cap[1],60*cap[1],3*cap[2],2.5*cap[3]])
    lo=a0*(qlo/100)**(1+ea); hi=a0*(qhi/100)**(1+ea)
    t=a0*(q/100)**(1+ea)
    def qty(v): return 100*(v/a0)**gamma
    def revenue(v): return float(np.sum(prices*100*(v/a0)**beta)/1e6)
    def grad(v): return prices*100*beta/a0*(v/a0)**(beta-1)/1e6
    def use(v):
        z=qty(v)
        return np.array([100*v.sum(),z[0]/50+z[1]/60,z[2]/3,z[3]/2.5])
    def jac(v):
        dq=100*gamma/a0*(v/a0)**(gamma-1)
        return np.array([np.ones(4)*100,[dq[0]/50,dq[1]/60,0,0],
                         [0,0,dq[2]/3,0],[0,0,0,dq[3]/2.5]])
    actual=revenue(t)*1e6
    assert int(float(row['solvestat']))==1 and int(float(row['modelstat'])) in (1,2)
    assert np.max(use(t)-cap)<1e-5 and np.min(q-qlo)>-1e-7
    assert abs(actual-float(row['objective_rub']))/actual<1e-9
    candidates=[]
    for start in [t,lo+.1*(hi-lo),lo+.65*(hi-lo)]:
        r=minimize(lambda v:-revenue(v),start,jac=lambda v:-grad(v),
            bounds=list(zip(lo,hi)),constraints=[{'type':'ineq',
            'fun':lambda v:1-use(v)/cap,'jac':lambda v:-jac(v)/cap[:,None]}],
            method='SLSQP',options={'ftol':1e-12,'maxiter':800})
        if r.success and np.max(use(r.x)-cap)<1e-5:
            candidates.append((revenue(r.x)*1e6,qty(r.x)))
    assert len(candidates)>=2, (row['scenario_id'],'independent solver insufficient successes')
    best=max(candidates,key=lambda z:z[0]); diff=abs(best[0]-actual)/actual
    assert diff<1e-6, (row['scenario_id'],diff)
    # Positive resource multipliers plus box normals fit stationarity.
    J=jac(t)/cap[:,None]; active=np.where(use(t)/cap>1-1e-6)[0]
    cols=[J[i] for i in active]
    for j in range(4):
        unit=np.eye(4)[j]
        if t[j]-lo[j]<1e-7*max(1,hi[j]-lo[j]): cols.append(-unit)
        if hi[j]-t[j]<1e-7*max(1,hi[j]-lo[j]): cols.append(unit)
    multipliers,_=nnls(np.array(cols).T,grad(t))
    lam=np.zeros(4); lam[active]=multipliers[:len(active)]
    g=use(t)/cap-1
    L=revenue(t)-lam@g
    slope=grad(t)-lam@J
    upper=L+np.maximum(slope*(lo-t),slope*(hi-t)).sum()+1e-8
    gap=(upper*1e6-actual)/actual
    assert gap>=-1e-8 and gap<1e-6,(row['scenario_id'],'upper bound gap',gap)
    return {'scenario_id':row['scenario_id'],'revenue_rub':actual,
        'independent_revenue_rub':best[0],'relative_difference':diff,
        'numerical_upper_bound_rub':upper*1e6,'relative_bound_gap':gap,
        'independent_successful_starts':len(candidates),'max_resource_violation':float(max(0,np.max(use(t)-cap)))}

rows=list(csv.DictReader((base/'results/scenario_results.csv').open()))
assert len(rows)==20 and len({r['scenario_id'] for r in rows})==20
condition_fields=['raw_t','mk_hours','cream_hours','curds_hours','p_milk','p_kefir','p_cream','p_curds']
assert len({tuple(r[k] for k in condition_fields) for r in rows})==20
base_rows=list(csv.DictReader((base/'results/base_results.csv').open()))
assert len(base_rows)==1
checked=[check(r) for r in rows+base_rows]
starts=list(csv.DictReader((base/'results/scenario_starts.csv').open()))
assert len(starts)==60
base_starts=list(csv.DictReader((base/'results/base_starts.csv').open()))
assert len(base_starts)==3
lookup={r['scenario_id']:r for r in rows+base_rows}
for s in starts+base_starts:
    r=lookup[s['scenario_id']]
    cap=np.array([float(r[k]) for k in ('raw_t','mk_hours','cream_hours','curds_hours')])
    prices=np.array([float(r['p_'+k]) for k in ('milk','kefir','cream','curds')])
    q=np.array([float(s['q_'+k]) for k in ('milk','kefir','cream','curds')])
    use=np.array([np.sum(a0*100*(q/100)**(1+ea)),q[0]/50+q[1]/60,q[2]/3,q[3]/2.5])
    objective=np.sum(prices*100*(q/100)**(1+ep))
    assert int(float(s['solvestat']))==1 and int(float(s['modelstat'])) in (1,2)
    assert np.max(use-cap)<1e-5 and np.min(q-qlo)>-1e-7
    assert abs(objective-float(s['objective_rub']))/objective<1e-9
out={'passed':True,'scenario_count':20,'start_count':63,
    'method':'independent convex-variable SLSQP from three starts; concave Lagrangian tangent numerical upper bounds on a box',
    'bound_scope':'Floating point numerical certificate with safety margin, not interval arithmetic proof',
    'beta':beta.tolist(),'gamma':gamma.tolist(),'rows':checked,
    'max_relative_solver_difference':max(r['relative_difference'] for r in checked),
    'max_relative_bound_gap':max(r['relative_bound_gap'] for r in checked)}
Path(__file__).with_name('verification_nlp.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))



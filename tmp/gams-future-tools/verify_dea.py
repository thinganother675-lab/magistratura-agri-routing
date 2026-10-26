from pathlib import Path
import sys, csv, json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'coursework/mmm-ppr/variant-11/runtime/python_packages'))
import numpy as np
from scipy.optimize import linprog
from scipy.stats import rankdata, t as student_t
base=ROOT/'coursework/gams-2026/lab10-variant8'
source=list(csv.DictReader((ROOT/'coursework/gams-2026/assignments/lab10-variant8.csv').open()))
assert len(source)==25 and {int(r['firm']) for r in source}==set(range(1,26))
assert all(r['variant']=='8' for r in source)
x=np.array([[float(r[k]) for k in ('x1','x2')] for r in source])
y=np.array([[float(r[k]) for k in ('y1','y2')] for r in source])/1000
scores=list(csv.DictReader((base/'efficiencies.csv').open()))
assert len(scores)==25
weights=np.zeros((25,25))
for r in csv.DictReader((base/'peers.csv').open()):
    weights[int(r['firm'].lstrip('f'))-1,int(r['peer'].lstrip('f'))-1]=float(r['lambda'])
rows=[]
for i,r in enumerate(scores):
    assert r['firm']==f'f{i+1}' and r['modelstat']=='1' and r['solvestat']=='1'
    # Independent output-oriented VRS primal LP, output units scaled by 1000.
    A=np.vstack([np.c_[x.T,np.zeros(2)],np.c_[-y.T,y[i]]])
    b=np.r_[x[i],np.zeros(2)]
    p=linprog(np.r_[np.zeros(25),-1],A_ub=A,b_ub=b,
        A_eq=np.array([np.r_[np.ones(25),0]]),b_eq=[1],
        bounds=[(0,None)]*25+[(None,None)],method='highs')
    # Separate multiplier dual: min v*x_i+w, u*y_i=1, v*x_j-u*y_j+w >=0.
    d=linprog(np.r_[x[i],0,0,1],A_ub=np.c_[-x,y,-np.ones(25)],b_ub=np.zeros(25),
        A_eq=np.array([[0,0,*y[i],0]]),b_eq=[1],
        bounds=[(0,None)]*4+[(None,None)],method='highs')
    assert p.success and d.success
    phi=-p.fun; actual=float(r['phi']); eff=float(r['efficiency'])
    residual=max(0,float(np.max(weights[i]@x-x[i])),
        float(np.max(actual*y[i]-weights[i]@y)),abs(weights[i].sum()-1),-weights[i].min())
    assert abs(phi-actual)<1e-8 and abs(d.fun-phi)<1e-8
    assert abs(eff-1/phi)<1e-8 and residual<1e-6
    rows.append({'firm':i+1,'phi':phi,'efficiency':1/phi,
        'gams_difference':abs(phi-actual),'dual_gap':abs(d.fun-phi),'peer_violation':residual})
e=np.array([r['efficiency'] for r in rows]); e[np.abs(e-1)<1e-9]=1
rng=np.random.default_rng(20261025)
B=49999
stats=[]
for label,v in [('size',x.sum(axis=1)),('lawyer_share',x[:,0]/x.sum(axis=1))]:
    a=rankdata(e); a-=a.mean(); b=rankdata(v); b-=b.mean()
    norm=np.linalg.norm(a)*np.linalg.norm(b); rho=float(a@b/norm)
    asym=float(2*student_t.sf(abs(rho)*np.sqrt(23/(1-rho*rho)),23))
    exceed=0; done=0
    while done<B:
        n=min(5000,B-done)
        idx=np.array([rng.permutation(25) for _ in range(n)])
        null=(a[idx]@b)/norm
        exceed+=int(np.sum(np.abs(null)>=abs(rho)-1e-14)); done+=n
    perm=(exceed+1)/(B+1)
    stats.append({'variable':label,'rho':rho,'p_t_approx':asym,
        'p_permutation_check':perm,'permutations':B,'seed':20261025,
        'reject_at_0_05':bool(perm<0.05)})
out={'passed':True,'method':'25 independent HiGHS primal LPs and 25 separate multiplier dual LPs; peer checks; ranks with ties and independent Monte Carlo',
    'rows':rows,'efficient_count':int(np.sum(np.abs(e-1)<1e-9)),'statistics':stats,
    'max_gams_difference':max(r['gams_difference'] for r in rows),
    'max_dual_gap':max(r['dual_gap'] for r in rows)}
Path(__file__).with_name('verification_dea.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))

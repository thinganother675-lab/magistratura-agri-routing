"""Independent LP, convex-NLP certificate, DEA duals and Spearman tests.
Run from any directory; GAMS outputs are checked separately after GAMS runs.
"""
from common import ROOT, write_csv, write_json
import csv, json, math
import numpy as np
from scipy.optimize import linprog, minimize, nnls
from scipy.stats import spearmanr, rankdata, t as student_t
from prepare_data import PRODUCTS,P,A,EP,EA,LOW

def lab2():
    c=np.array([2400.,2700,13800,7200])
    a=np.array([[1.01,1.01,9.45,15],[.2,1/6,0,0],[0,0,1/.3,0],[0,0,0,5.]])
    b=np.array([140.,21,16,16])
    r=linprog(-c,A_ub=a,b_ub=b,bounds=(0,None),method='highs')
    assert r.success
    dual=-r.ineqlin.marginals
    assert max(a@r.x-b)<1e-8 and np.min(a.T@dual-c)>-1e-8
    assert abs(b@dual + r.fun)<1e-7
    # Exact rational simplex tableau: initial slack basis, Bland pivots.
    from fractions import Fraction as F
    aa=[[F('1.01'),F('1.01'),F('9.45'),F(15)],[F(1,5),F(1,6),0,0],[0,0,F(10,3),0],[0,0,0,5]]
    tab=[list(map(F,row))+[F(int(i==j)) for j in range(4)]+[F(int(b[i]))] for i,row in enumerate(aa)]
    tab.append([-F(int(v)) for v in c]+[F(0)]*5)
    basis=[4,5,6,7]; tables=[]; iteration=0
    while True:
        tables.append({'iteration':iteration,'basis':['x'+str(i+1) if i<4 else 's'+str(i-3) for i in basis], 'table':[[str(v) for v in row] for row in tab]})
        entering=next((j for j in range(8) if tab[-1][j]<0),None)
        if entering is None: break
        candidates=[(tab[i][-1]/tab[i][entering],basis[i],i) for i in range(4) if tab[i][entering]>0]
        _,_,leaving=min(candidates)
        pivot=tab[leaving][entering]; tab[leaving]=[v/pivot for v in tab[leaving]]
        for i in range(5):
            if i!=leaving:
                factor=tab[i][entering]; tab[i]=[v-factor*w for v,w in zip(tab[i],tab[leaving])]
        basis[leaving]=entering; iteration+=1
        assert iteration<100
    exact=[F(0)]*4
    for i,j in enumerate(basis):
        if j<4: exact[j]=tab[i][-1]
    assert np.max(np.abs(np.array([float(x) for x in exact])-r.x))<1e-7
    rows=[dict(product=p,x_centner=float(x),revenue_rub=float(x*cc),exact=str(ex)) for p,x,cc,ex in zip(['milk','kefir','cream','curd_bars'],r.x,c,exact)]
    write_csv('results/lab2_python.csv',rows)
    write_json('results/lab2.json',{'objective_rub':float(-r.fun),'x':r.x.tolist(),'resource_use':(a@r.x).tolist(),'resource_slack':(b-a@r.x).tolist(),'shadow_prices':dual.tolist(),'dual_objective_rub':float(b@dual),'simplex_iterations':iteration,'simplex_tableaux':tables,'solver':'SciPy HiGHS','verified':True})
    # Fractional and decimal versions of all tableaux.
    out=[]
    for t in tables:
        out.append('ITERATION '+str(t['iteration'])+' BASIS '+','.join(t['basis']))
        out.append('row\tx1\tx2\tx3\tx4\ts1\ts2\ts3\ts4\tRHS')
        for name,row in zip(t['basis']+['R'],t['table']): out.append(name+'\t'+'\t'.join(row))
        out.append('')
    (ROOT/'results/lab2_simplex_exact.txt').write_text('\n'.join(out),encoding='utf-8')
    return -r.fun

def lab8():
    scenarios=list(csv.DictReader((ROOT/'data/scenarios.csv').open(encoding='utf-8-sig')))
    aa=np.array(A); bb=1+np.array(EA); ss=(1+np.array(EP))/bb
    lo=aa*(np.array(LOW)/100)**bb
    summaries=[]; runrows=[]; certs=[]
    for row in scenarios:
        raw=float(row['raw_t']); tm=float(row['mk_hours']); ts=float(row['cy_hours'])
        pp=np.array([float(row['p_'+p]) for p in PRODUCTS]); cc=pp/10000
        qmax=np.array([50*tm,60*tm,3*ts,2*ts]); up=aa*(qmax/100)**bb
        def q(t): return 100*(t/aa)**(1/bb)
        def dq(t): return q(t)/(bb*t)
        def f(t): return np.sum(cc*(t/aa)**ss)
        def df(t): return cc*(t/aa)**ss*ss/t
        def g(t):
            z=q(t)
            return np.array([sum(t)/(raw/100)-1,(z[0]/50+z[1]/60)/tm-1,(z[2]/3+z[3]/2)/ts-1])
        def jg(t):
            z=dq(t)
            return np.array([[100/raw]*4,[z[0]/50/tm,z[1]/60/tm,0,0],[0,0,z[2]/3/ts,z[3]/2/ts]])
        trials=[]
        for start in [.15,.45,.75]:
            t0=lo+start*(up-lo)/4
            while max(g(t0))>0: t0=(t0+lo)/2
            rr=minimize(lambda z:-f(z),t0,jac=lambda z:-df(z),bounds=list(zip(lo,up)),constraints=[{'type':'ineq','fun':lambda z:-g(z),'jac':lambda z:-jg(z)}],method='SLSQP',options={'ftol':1e-12,'maxiter':2000})
            assert max(g(rr.x))<1e-7, (row['scenario_id'],rr.message,g(rr.x))
            # Sometimes SLSQP returns status8 with a numerically optimal point;
            # feasibility and a rigorous tangent dual bound decide acceptance.
            active=np.flatnonzero(g(rr.x)>-1e-7)
            free=np.flatnonzero((rr.x-lo>1e-6)&(up-rr.x>1e-6))
            lam=np.zeros(3)
            if len(active): lam[active]=nnls(jg(rr.x)[active][:,free].T,df(rr.x)[free])[0]
            tangent=df(rr.x)-lam@jg(rr.x)
            bound=f(rr.x)-lam@g(rr.x)+np.sum(np.maximum(tangent*(lo-rr.x),tangent*(up-rr.x)))
            # Explicit floating-point allowance, 1e-8 of objective (~0.3 RUB).
            # Avoid presenting a bound microscopically below the feasible value.
            bound+=1e-8*max(1.,float(f(rr.x)))
            gap=max(0.,bound-f(rr.x))
            assert gap/max(1,f(rr.x))<1e-6,(row['scenario_id'],gap,rr.message)
            trials.append((rr,lam,bound,gap))
            runrows.append(dict(scenario_id=row['scenario_id'],start_fraction=start,objective_rub=float(f(rr.x)*1e6),scipy_success=bool(rr.success),scipy_status=int(rr.status),max_scaled_violation=float(max(0,max(g(rr.x)))),global_gap_relative=float(gap/f(rr.x)),iterations=int(rr.nit)))
        values=[float(f(t[0].x)) for t in trials]
        spread=(max(values)-min(values))/max(values)
        assert spread<.001
        rr,lam,bound,gap=max(trials,key=lambda t:f(t[0].x)); z=q(rr.x)
        tangent=df(rr.x)-lam@jg(rr.x)
        output={k:float(v) if k!='scenario_id' else v for k,v in row.items()}
        for i,p in enumerate(PRODUCTS):
            output['q_'+p]=float(z[i]); output['price_'+p]=float(pp[i]*(z[i]/100)**EP[i]); output['input_'+p]=float(aa[i]*(z[i]/100)**EA[i])
            output['a_'+p]=A[i]; output['ep_'+p]=EP[i]; output['ea_'+p]=EA[i]
        output.update(objective_rub=float(f(rr.x)*1e6),raw_used=float(sum(rr.x)*100),mk_used=float(z[0]/50+z[1]/60),cy_used=float(z[2]/3+z[3]/2),global_upper_bound_rub=float(bound*1e6),gap_rub=float(gap*1e6),start_spread_relative=spread,status='GLOBAL_CERTIFIED',marginal_raw_rub_per_t=float(lam[0]*1e6/raw),marginal_mk_rub_per_h=float(lam[1]*1e6/tm),marginal_cy_rub_per_h=float(lam[2]*1e6/ts))
        summaries.append(output)
        certs.append({'scenario_id':row['scenario_id'],'t_raw_div100':rr.x.tolist(),'multipliers_scaled':lam.tolist(),'tangent_residual':tangent.tolist(),'upper_bound_rub':float(bound*1e6),'lower_bound_rub':float(f(rr.x)*1e6),'relative_gap':float(gap/f(rr.x))})
    write_csv('results/lab8_python_scenarios.csv',summaries)
    write_csv('results/lab8_python_starts.csv',runrows)
    write_json('results/lab8_certificates.json',{'transformation':'t_j=a0_j*(q_j/100)^(1+ea_j); raw_j=100*t_j','objective_powers':ss.tolist(),'proof':'Concave revenue and convex line times in t. Lagrangian tangent bounds objective on entire bounding box. Nonnegative multipliers give valid upper bound.','numerical_rounding_allowance_relative':1e-8,'acceptance_gap_relative':1e-6,'certificates':certs})
    return summaries[0]

def dea():
    data=list(csv.DictReader((ROOT/'data/dea-variant-3.csv').open(encoding='utf-8-sig')))
    xx=np.array([[float(r['x1']),float(r['x2'])] for r in data]); yy=np.array([[float(r['y1']),float(r['y2'])] for r in data]); n=25
    results=[]; peerrows=[]; allk=[]
    for i in range(n):
        # Scale outputs to thousands only for conditioning; phi is invariant.
        y=yy/1000
        mat=np.vstack([np.column_stack([xx.T,np.zeros(2)]),np.column_stack([-y.T,y[i]])])
        rhs=np.r_[xx[i],np.zeros(2)]
        c=np.r_[np.zeros(n),-1.]
        eq=np.array([np.r_[np.ones(n),0.]])
        r=linprog(c,A_ub=mat,b_ub=rhs,A_eq=eq,b_eq=[1],bounds=[(0,None)]*n+[(1,None)],method='highs')
        assert r.success
        phi=float(r.x[-1]); k=1/phi
        # Explicit multiplier dual, independent matrix construction.
        # Variables v1,v2,u1,u2,w; min v*Xi+w.
        rd=linprog(np.r_[xx[i],0,0,1.],A_ub=np.column_stack([-xx,y,-np.ones(n)]),b_ub=np.zeros(n),A_eq=[np.r_[0,0,y[i],0]],b_eq=[1],bounds=[(0,None)]*4+[(None,None)],method='highs')
        assert rd.success and abs(rd.fun-phi)<1e-7
        # Second stage: maximize normalized input+output slacks at fixed phi.
        sc=np.sum(xx/np.max(xx,axis=0),axis=1)-np.sum(yy/np.max(yy,axis=0),axis=1)
        sl=linprog(sc,A_ub=mat[:,:n],b_ub=np.r_[xx[i],-phi*y[i]],A_eq=np.ones((1,n)),b_eq=[1],bounds=(0,None),method='highs')
        assert sl.success
        lam=sl.x; ins=xx[i]-xx.T@lam; outs=yy.T@lam-phi*yy[i]
        violation=max(0,float(max(xx.T@lam-xx[i])),float(max(phi*yy[i]-yy.T@lam)),abs(sum(lam)-1))
        assert violation<1e-6
        assert 0<k<=1+1e-8
        if abs(k-1)<1e-9: k=1. # Make mathematical ties exact before rank tests.
        peers=[f'{j+1}:{v:.6f}' for j,v in enumerate(lam) if v>1e-8]
        strong=k==1. and max(abs(ins))<1e-7 and max(abs(outs))<1e-5
        results.append(dict(firm=i+1,y1=yy[i,0],y2=yy[i,1],x1=xx[i,0],x2=xx[i,1],size=sum(xx[i]),lawyer_share=xx[i,0]/sum(xx[i]),phi=phi,efficiency=k,radial_growth_percent=(phi-1)*100,radially_efficient=k==1.,strongly_efficient=strong,slack_x1=ins[0],slack_x2=ins[1],slack_y1=outs[0],slack_y2=outs[1],max_violation=violation,dual_gap=abs(rd.fun-phi),peers=';'.join(peers)))
        for j,v in enumerate(lam):
            if v>1e-8: peerrows.append(dict(firm=i+1,peer=j+1,weight=float(v)))
        allk.append(k)
    stats=[]
    rng=np.random.default_rng(20261007); perms=200000
    for name,variable in [('size',xx.sum(axis=1)),('lawyer_share',xx[:,0]/xx.sum(axis=1))]:
        rho,p=spearmanr(allk,variable)
        tt=float(rho*np.sqrt((n-2)/(1-rho*rho)))
        assert abs(2*student_t.sf(abs(tt),n-2)-p)<1e-12
        rx=rankdata(allk); ry=rankdata(variable); rx-=rx.mean(); ry-=ry.mean()
        denom=np.linalg.norm(rx)*np.linalg.norm(ry); exceed=0
        for _ in range(perms//5000):
            perm=np.array([rng.permutation(rx) for _ in range(5000)])
            exceed+=int(np.sum(np.abs(perm@ry/denom)>=abs(rho)-1e-12))
        pp=(exceed+1)/(perms+1)
        stats.append(dict(variable=name,n=n,rho=float(rho),t_stat=tt,df=n-2,p_asymptotic=float(p),p_permutation=pp,permutations=perms,seed=20261007,permutation_mc_se=math.sqrt(pp*(1-pp)/(perms+1)),alpha=.05,reject_h0=bool(p<.05),reject_h0_permutation=bool(pp<.05),ties_method='average ranks; efficiencies within 1e-9 of 1 rounded to 1'))
    write_csv('results/lab10_python_dea.csv',results)
    write_csv('results/lab10_python_peers.csv',peerrows)
    write_json('results/lab10_stats.json',stats)
    return stats, int(sum(r['radially_efficient'] for r in results)),int(sum(r['strongly_efficient'] for r in results))

if __name__=='__main__':
    out={'lab2_objective':float(lab2()),'lab8_base':lab8(),'lab10':dea()}
    write_json('results/independent_summary.json',out)
    print(json.dumps(out,ensure_ascii=False,indent=2))

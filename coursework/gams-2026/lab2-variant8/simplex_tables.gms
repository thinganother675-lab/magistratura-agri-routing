$title Variant 8 laboratory 2.2 - complete primal simplex tableaux
* Standalone educational calculation in GAMS; no external numeric script.
* Quantity: centners/day; objective: thousand RUB/day.
* Tableau convention: -c in objective row, optimal when all >= 0.
Sets
    r rows /rawmilk,mainline,creamline,assortment,obj/
    i(r) constraints /rawmilk,mainline,creamline,assortment/
    j columns /milk,kefir,cream,skim,sraw,sline,scream,sassort,rhs/
    v(j) variables /milk,kefir,cream,skim,sraw,sline,scream,sassort/
    p(j) products /milk,kefir,cream,skim/
    enter(j), leave(r), basic(r,j)
    it iteration_limit /it1*it100/;
Alias (j,k);
Parameters a(r,j), b(r), c(j), tab(r,j), prow(j), multiplier(r),
           ratio(r), solution(j), usage(r), slack(r);
Scalars tol /1e-9/, iter /0/, eligible, enterOrder, leaveOrder,
        minratio, pivot, revenueSimplex, revenueDiff, maxViolation,
        basicError, expectedRevenue /321.517777777778/;

a('rawmilk','milk')=1.01; a('rawmilk','kefir')=1.01;
a('rawmilk','cream')=9.45; a('rawmilk','skim')=0.31;
a('mainline','milk')=1/5; a('mainline','kefir')=1/6;
a('mainline','skim')=1/6;
a('creamline','cream')=1/0.3;
a('assortment','kefir')=1; a('assortment','skim')=-2;
b('rawmilk')=140; b('mainline')=21; b('creamline')=16;
b('assortment')=0;
c('milk')=2.4; c('kefir')=2.7; c('cream')=13.8; c('skim')=0.79;
basic('rawmilk','sraw')=yes; basic('mainline','sline')=yes;
basic('creamline','scream')=yes; basic('assortment','sassort')=yes;
tab(i,j)=a(i,j); tab(i,j)$basic(i,j)=1;
tab(i,'rhs')=b(i); tab('obj',v)=-c(v);

File tables /simplex_tables.txt/;
put tables;
put 'COMPLETE PRIMAL SIMPLEX TABLEAUX - VARIANT 8'/;
put 'Units: centners/day; revenue thousand RUB/day.'/;
put 'Row: sum(tableau coefficients * variables) = RHS.'/;
put 'Objective row: z + sum(objective coefficients * variables) = RHS.'/;
put 'Bland order: milk,kefir,cream,skim,sraw,sline,scream,sassort.'/;
put 'Entering: first negative objective coefficient; leaving: minimum ratio,'/;
put 'ties: smallest ordered BASIC variable. Zero ratio pivots are allowed.'/;
put 'Round only the displayed tables; internal arithmetic uses full precision.'/;

put /'TABLE 0 - INITIAL'/;
put 'Nonbasic: '; loop(v$(sum(i$basic(i,v),1)=0),put v.tl:12); put /;
put 'row':14 'basic':12; loop(j,put j.tl:15); put /;
loop(r,
    put r.tl:14;
    if(i(r),loop(j$basic(r,j),put j.tl:12); else put 'z':12;);
    loop(j,put tab(r,j):15:6); put /;
);

loop(it$(smin(v,tab('obj',v)) < -tol),
    iter=iter+1;
    enter(j)=no; leave(r)=no;
    enterOrder=smin(v$(tab('obj',v)<-tol),ord(v));
    enter(v)$(ord(v)=enterOrder)=yes;
    multiplier(r)=sum(j$enter(j),tab(r,j));
    eligible=sum(i$(multiplier(i)>tol),1);
    abort$(eligible=0) 'Unbounded LP detected';
    ratio(i)=inf;
    ratio(i)$(multiplier(i)>tol)=max(0,tab(i,'rhs'))/multiplier(i);
    minratio=smin(i,ratio(i));
    leaveOrder=smin((i,v)$(basic(i,v) and abs(ratio(i)-minratio)<tol),ord(v));
    leave(i)$(sum(v$(ord(v)=leaveOrder and basic(i,v)),1)>0)=yes;
    pivot=sum(i$leave(i),multiplier(i));
    abort$(abs(pivot)<tol or card(leave)<>1 or card(enter)<>1) 'Invalid pivot';
    put /'PIVOT ':0 iter:0:0 ': enter ';
    loop(j$enter(j),put j.tl:0);
    put ', leave '; loop((i,j)$(leave(i) and basic(i,j)),put j.tl:0);
    put ', pivot=' pivot:0:9 ', ratio=' minratio:0:9/;
    put 'Eligible ratios: ';
    loop(i$(multiplier(i)>tol),put i.tl:0 '=' ratio(i):0:9 '  '); put /;
    prow(j)=sum(i$leave(i),tab(i,j))/pivot;
    tab(r,j)=tab(r,j)-multiplier(r)*prow(j);
    tab(i,j)$leave(i)=prow(j);
    basic(i,j)$leave(i)=no;
    basic(i,j)$(leave(i) and enter(j))=yes;

    basicError=0;
    loop((i,k)$basic(i,k),
        basicError=max(basicError,abs(tab(i,k)-1),
            smax(r$(not sameas(i,r)),abs(tab(r,k))));
    );
    abort$(basicError>1e-7 or smin(i,tab(i,'rhs')) < -1e-7) 'Tableau invariant failed';
    put /'TABLE ' iter:0:0/;
    put 'Nonbasic: '; loop(v$(sum(i$basic(i,v),1)=0),put v.tl:12); put /;
    put 'row':14 'basic':12; loop(j,put j.tl:15); put /;
    loop(r,
        put r.tl:14;
        if(i(r),loop(j$basic(r,j),put j.tl:12); else put 'z':12;);
        loop(j,put tab(r,j):15:6); put /;
    );
);
abort$(smin(v,tab('obj',v)) < -tol) 'Iteration limit reached';
solution(v)=sum(i$basic(i,v),tab(i,'rhs'));
revenueSimplex=sum(p,c(p)*solution(p));
usage(i)=sum(p,a(i,p)*solution(p)); slack(i)=b(i)-usage(i);
maxViolation=max(0,smax(i,usage(i)-b(i)),-smin(v,solution(v)));
abort$(maxViolation>1e-7 or abs(revenueSimplex-tab('obj','rhs'))>1e-7)
    'Original constraints or objective do not match tableau';

* Independent GAMS/CPLEX verification using exactly the same A, b, c.
Positive Variables x(p);
Variable z;
Equations referenceObjective, referenceConstraints(i);
referenceObjective.. z =e= sum(p,c(p)*x(p));
referenceConstraints(i).. sum(p,a(i,p)*x(p)) =l= b(i);
Model reference /referenceObjective,referenceConstraints/;
option lp=cplex;
solve reference using lp maximizing z;
abort$(reference.modelstat<>1 or reference.solvestat<>1) 'Reference LP failed';
revenueDiff=abs(revenueSimplex-z.l);
abort$(revenueDiff>1e-7 or smax(p,abs(solution(p)-x.l(p)))>1e-7
    or abs(revenueSimplex-expectedRevenue)>1e-7) 'Simplex differs from lab2 LP';

put /'FINAL TABLE = TABLE ' iter:0:0/;
put 'solution (product and slack variables):'/;
loop(v,put v.tl:14 solution(v):18:9/);
put 'Revenue, thousand RUB/day: ' revenueSimplex:0:9/;
put 'Resource':16 'Limit':16 'Used':16 'Remaining':16/;
loop(i,put i.tl:16 b(i):16:9 usage(i):16:9 slack(i):16:9/);
put 'Verification: original constraints and nonnegativity PASS'/;
put 'Verification: objective = CPLEX LP = original lab2 LP PASS'/;
put 'CPLEX objective difference: ' revenueDiff:0:12/;
put 'Maximum original constraint violation: ' maxViolation:0:12/;
putclose tables;
display solution,revenueSimplex,slack,iter,revenueDiff,maxViolation;


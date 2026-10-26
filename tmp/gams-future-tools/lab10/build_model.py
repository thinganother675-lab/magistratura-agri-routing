from pathlib import Path
import csv
root=Path(r'C:/sarychev/Codex/magistratura')
out=root/'coursework/gams-2026/lab10-variant8'
rows=list(csv.DictReader((root/'coursework/gams-2026/assignments/lab10-variant8.csv').open()))
table='\n'.join(f"{'f'+z['firm']:<8}"+ ''.join(f'{z[k]:>8}' for k in ['y1','y2','x1','x2']) for z in rows)
code='''Sets j /f1*f25/, r /y1,y2,x1,x2/;
Alias(j,m);
Sets outputs(r) /y1,y2/, inputs(r) /x1,x2/;
Table data(j,r)
              y1      y2      x1      x2
TABLE
;
Parameter target(r), result(m,*), weights(m,j), used(m,r);
Positive Variable lambda(j);
Variable phi;
phi.lo=1;
Equations inputLimit(r), outputTarget(r), convexity;
inputLimit(inputs).. sum(j, data(j,inputs)*lambda(j)) =l= target(inputs);
outputTarget(outputs).. sum(j, data(j,outputs)*lambda(j)) =g= phi*target(outputs);
convexity.. sum(j,lambda(j)) =e= 1;
Model dea /all/;
option lp=cplex;
File scores /efficiencies.csv/, peers /peers.csv/, source /input_data.csv/;
put source 'firm,y1,y2,x1,x2' /;
loop(j, put source j.tl:0 ',' data(j,'y1'):0:0 ',' data(j,'y2'):0:0 ','
    data(j,'x1'):0:0 ',' data(j,'x2'):0:0 /;);
putclose source;
put scores 'firm,phi,efficiency,modelstat,solvestat,max_violation' /;
put peers 'firm,peer,lambda' /;
loop(m,
    target(r)=data(m,r);
    solve dea using lp maximizing phi;
    abort$(dea.modelstat<>1 or dea.solvestat<>1) 'DEA solve failed',m;
    result(m,'phi')=phi.l;
    result(m,'efficiency')=1/phi.l;
    result(m,'modelstat')=dea.modelstat;
    result(m,'solvestat')=dea.solvestat;
    weights(m,j)=lambda.l(j);
    used(m,r)=sum(j,data(j,r)*lambda.l(j));
    result(m,'violation')=max(0,smax(inputs,used(m,inputs)-target(inputs)),
       smax(outputs,phi.l*target(outputs)-used(m,outputs)),
       abs(sum(j,lambda.l(j))-1),1-phi.l,-smin(j,lambda.l(j)));
    abort$(result(m,'violation')>1e-6) 'DEA residual failed',m;
    put scores m.tl:0 ',' phi.l:0:15 ',' result(m,'efficiency'):0:15 ','
       dea.modelstat:0:0 ',' dea.solvestat:0:0 ',' result(m,'violation'):0:15 /;
    loop(j$(lambda.l(j)>1e-8),put peers m.tl:0 ',' j.tl:0 ',' lambda.l(j):0:15 /;);
);
putclose scores;
putclose peers;
display result,weights,used;
'''.replace('TABLE',table)
(out/'lab10.gms').write_text(code,encoding='ascii')
print(out/'lab10.gms')

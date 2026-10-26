from pathlib import Path
root=Path(r'C:/sarychev/Codex/magistratura')
old=root/'coursework/gams-2026/lab10-variant8/lab10.gms'
out=root/'coursework/gams-2026/STUDY_SIMPLE_VARIANT8/lab10'
prefix=old.read_text().split('Parameter target')[0]
code=prefix+'''Parameter target(r), result(m,*);
Positive Variable lambda(j);
Variable phi;
phi.lo = 1;
Equations inputLimit(r), outputTarget(r), convexity;
inputLimit(inputs).. sum(j, data(j,inputs)*lambda(j)) =l= target(inputs);
outputTarget(outputs).. sum(j, data(j,outputs)*lambda(j)) =g= phi*target(outputs);
convexity.. sum(j,lambda(j)) =e= 1;
Model dea /all/;
option lp = cplex;

File scores /efficiencies.csv/, peers /peers.csv/, source /input_data.csv/;
put source 'firm,y1,y2,x1,x2' /;
loop(j,
    put source j.tl:0 ',' data(j,'y1'):0:0 ',' data(j,'y2'):0:0 ','
        data(j,'x1'):0:0 ',' data(j,'x2'):0:0 /;
);
putclose source;
put scores 'firm,phi,efficiency,modelstat,solvestat' /;
put peers 'firm,peer,lambda' /;

loop(m,
    target(r) = data(m,r);
    solve dea using lp maximizing phi;
    result(m,'phi') = phi.l;
    result(m,'efficiency') = 1/phi.l;
    result(m,'modelstat') = dea.modelstat;
    result(m,'solvestat') = dea.solvestat;
    put scores m.tl:0 ',' result(m,'phi'):0:15 ','
        result(m,'efficiency'):0:15 ',' result(m,'modelstat'):0:0 ','
        result(m,'solvestat'):0:0 /;
    loop(j,
        put peers m.tl:0 ',' j.tl:0 ',' lambda.l(j):0:15 /;
    );
);
putclose scores;
putclose peers;
display result;
'''
(out/'lab10.gms').write_text(code,encoding='ascii')
print('Total lines:',len(code.splitlines()))
print('Nonblank:',sum(bool(s.strip()) for s in code.splitlines()))
print('Without 25 data rows:',len(code.splitlines())-25)
print('Nonblank without 25 data rows:',sum(bool(s.strip()) for s in code.splitlines())-25)

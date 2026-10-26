Sets j /f1*f25/, r /y1,y2,x1,x2/;
Alias(j,m);
Sets outputs(r) /y1,y2/, inputs(r) /x1,x2/;
Table data(j,r)
              y1      y2      x1      x2
f1           474     352       5       9
f2           444     582       5      12
f3           698     652       7      15
f4           531     669       6      14
f5           718     599       8      14
f6           326     662       4      13
f7           443     903       4      18
f8           818     933       9      20
f9           392     767       5      15
f10          582     411       7      10
f11          414     448       4      10
f12          683    1002       6      21
f13          597     658       7      14
f14          855     588       8      15
f15          382     730       5      14
f16          361     570       4      12
f17          535     902       6      18
f18          653     913       6      19
f19          431     108       6       4
f20          693     544       7      13
f21          432     599       6      12
f22          725     503       9      12
f23          438    1003       5      19
f24          679     728       7      16
f25          464     918       5      18
;
Parameter target(r), result(m,*);
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

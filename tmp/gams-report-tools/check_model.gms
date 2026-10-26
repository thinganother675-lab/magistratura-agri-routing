$include "C:/sarychev/Codex/magistratura/coursework/gams-2026/lab2-variant8/lab2.gms"
abort$(dairy.modelstat <> 1 or dairy.solvestat <> 1) 'Status check failed';
abort$(abs(revenue.l-321.517777777778)>1e-8) 'Revenue check failed';
abort$(abs(x.l('milk'))>1e-8 or abs(x.l('kefir')-84)>1e-8
    or abs(x.l('cream')-4214/945)>1e-8 or abs(x.l('skim')-42)>1e-8)
    'Product check failed';
abort$(smax(r,sum(j,a(r,j)*x.l(j))-capacity(r))>1e-8) 'Feasibility failed';
File results /'C:/sarychev/Codex/magistratura/coursework/gams-2026/lab2-variant8/gams_result.csv'/;
put results 'milk,kefir,cream,skim,revenue_thousand_rub,modelstat,solvestat'/;
put x.l('milk'):0:12 ',' x.l('kefir'):0:12 ',' x.l('cream'):0:12 ','
    x.l('skim'):0:12 ',' revenue.l:0:12 ',' dairy.modelstat:0:0 ',' dairy.solvestat:0:0/;
putclose results;

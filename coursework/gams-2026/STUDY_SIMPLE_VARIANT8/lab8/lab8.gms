Sets
    j /milk, kefir, cream, curds/
    r /mainline, creamline, curdsline/
    s /base, s01*s20/
    k /start1*start3/;

Parameters
    a0(j) /milk 1.01, kefir 1.01, cream 9.45, curds 14/
    ep(j) /milk -.034, kefir -.022, cream -.022, curds -.027/
    ea(j) /milk -.017, kefir -.012, cream -.011, curds -.010/
    minimum(j) /milk 25, kefir 30, cream 1.5, curds 1.25/
    price(j), capacity(r), plan(s,k,j), result(s,k,*), spread(s);
Scalars rawCapacity, violation;

Table time(r,j)
                milk    kefir    cream    curds
    mainline     .02        0        0        0
    creamline      0        0        0        0
    curdsline      0        0        0       .4;
time('mainline','kefir') = 1/60;
time('creamline','cream') = 1/3;

Table initial(k,j)
             milk   kefir  cream  curds
    start1     25      30    1.5   1.25
    start2    300     500     30      5
    start3    800     100     45     35;

Table conditions(s,*)
         raw  mainline  creamline  curdsline   milk  kefir   cream  curds
    base 1400       21         18         18  24000  27000  138000  78000
    s01  1120       21         18         18  24000  27000  138000  78000
    s02  1260       21         18         18  24000  27000  138000  78000
    s03  1540       21         18         18  24000  27000  138000  78000
    s04  1680       21         18         18  24000  27000  138000  78000
    s05  1400       18         18         18  24000  27000  138000  78000
    s06  1400       24         18         18  24000  27000  138000  78000
    s07  1400       21         15         18  24000  27000  138000  78000
    s08  1400       21         21         18  24000  27000  138000  78000
    s09  1400       21         18         15  24000  27000  138000  78000
    s10  1400       21         18         21  24000  27000  138000  78000
    s11  1400       21         18         18  21600  27000  138000  78000
    s12  1400       21         18         18  26400  27000  138000  78000
    s13  1400       21         18         18  24000  24300  138000  78000
    s14  1400       21         18         18  24000  29700  138000  78000
    s15  1400       21         18         18  24000  27000  124200  78000
    s16  1400       21         18         18  24000  27000  151800  78000
    s17  1400       21         18         18  24000  27000  138000  70200
    s18  1400       21         18         18  24000  27000  138000  85800
    s19  1120       18         15         15  21600  24300  124200  70200
    s20  1680       24         21         21  26400  29700  151800  85800;

Positive Variable x(j);
Variable revenue;
Equations objective, raw, resource(r);
objective.. revenue =e= sum(j,price(j)*x(j)*rPower(x(j)/100,ep(j)))/1e6;
raw.. sum(j,a0(j)*x(j)*rPower(x(j)/100,ea(j))) =l= rawCapacity;
resource(r).. sum(j,time(r,j)*x(j)) =l= capacity(r);
Model dairy /all/;
x.lo(j) = minimum(j);
option nlp=conopt, optcr=1e-9, optca=1e-9;

File settings /conopt.opt/;
put settings 'Tol_Feas_Max 1e-10' / 'Tol_Feas_Min 1e-12' / 'Tol_Optimality 1e-11' /;
putclose settings;
dairy.optfile = 1;

loop(s,
    rawCapacity = conditions(s,'raw');
    capacity(r) = conditions(s,r);
    price(j) = conditions(s,j);
    loop(k,
        x.l(j) = initial(k,j);
        x.m(j) = 0;
        revenue.l = sum(j,price(j)*x.l(j)*rPower(x.l(j)/100,ep(j)))/1e6;
        solve dairy using nlp maximizing revenue;
        abort$((dairy.modelstat<>1 and dairy.modelstat<>2) or dairy.solvestat<>1) 'Solve failed: inspect lab8.lst',s,k;
        violation = max(0,sum(j,a0(j)*x.l(j)*rPower(x.l(j)/100,ea(j)))-rawCapacity);
        violation = max(violation,smax(r,sum(j,time(r,j)*x.l(j))-capacity(r)));
        violation = max(violation,smax(j,minimum(j)-x.l(j)));
        abort$(violation>1e-5) 'Constraint violated: inspect lab8.lst',s,k;
        plan(s,k,j) = x.l(j);
        result(s,k,'revenue') = revenue.l*1e6;
        result(s,k,'modelstat') = dairy.modelstat;
        result(s,k,'solvestat') = dairy.solvestat;
        result(s,k,'violation') = violation;
    );
    spread(s) = (smax(k,result(s,k,'revenue'))-smin(k,result(s,k,'revenue')))/max(1,abs(result(s,'start1','revenue')));
    spread(s) = max(spread(s),smax(j,(smax(k,plan(s,k,j))-smin(k,plan(s,k,j)))/max(1,abs(plan(s,'start1',j)))));
    abort$(spread(s)>.001) 'Starts differ >0.1 percent: tighten CONOPT tolerances and rerun',s;
);

File output /results.csv/;
output.pw = 32767;
output.nz = 0;
put output 'case_id,start_id,raw_t,mainline_hours,creamline_hours,curdsline_hours,p_milk,p_kefir,p_cream,p_curds,x_milk,x_kefir,x_cream,x_curds,revenue_rub,modelstat,solvestat,max_violation,spread_relative' /;
loop((s,k),
    put s.tl:0 ',' k.tl:0 ',' conditions(s,'raw'):0:12 ',';
    loop(r,put conditions(s,r):0:12 ',';);
    loop(j,put conditions(s,j):0:12 ',';);
    loop(j,put plan(s,k,j):0:12 ',';);
    put result(s,k,'revenue'):0:12 ',' result(s,k,'modelstat'):0:0 ',' result(s,k,'solvestat'):0:0 ',';
    put result(s,k,'violation'):0:12 ',' spread(s):0:12 /;
);
putclose output;
display plan, result, spread;

Sets
    j /milk, kefir, cream, curds/
    r /mainline, creamline, curdsline/;

Parameters
    p0(j) /milk 24000, kefir 27000, cream 138000, curds 78000/
    a0(j) /milk 1.01, kefir 1.01, cream 9.45, curds 14/
    ep(j) /milk -.034, kefir -.022, cream -.022, curds -.027/
    ea(j) /milk -.017, kefir -.012, cream -.011, curds -.010/
    qmin(j) /milk 25, kefir 30, cream 1.5, curds 1.25/
    hours(r) /mainline 21, creamline 18, curdsline 18/
    price(j), time(r,j);

Table speed(r,j)
                milk    kefir    cream    curds
    mainline      50       60        0        0
    creamline      0        0        3        0
    curdsline      0        0        0      2.5;

Scalar rawCapacity /1400/, q0 /100/;
price(j) = p0(j);
time(r,j)$speed(r,j) = 1/speed(r,j);

Positive Variable q(j);
Variable revenue;
Equations objective, raw, line(r);

objective.. revenue =e= sum(j,price(j)*q0*rPower(q(j)/q0,1+ep(j)))/1e6;
raw.. sum(j,a0(j)*q0*rPower(q(j)/q0,1+ea(j))) =l= rawCapacity;
line(r).. sum(j,time(r,j)*q(j)) =l= hours(r);

Model dairy /all/;
q.lo(j) = qmin(j);
option nlp=conopt, optcr=1e-9, optca=1e-9, reslim=60;


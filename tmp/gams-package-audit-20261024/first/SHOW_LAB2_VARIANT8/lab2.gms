Sets
    j /milk, kefir, cream, skim/
    r /rawmilk, mainline, creamline, assortment/;

Parameters
    price(j) /milk 2.4, kefir 2.7, cream 13.8, skim 0.79/
    capacity(r) /rawmilk 140, mainline 21, creamline 16, assortment 0/;

Table a(r,j)
                  milk       kefir       cream        skim
    rawmilk       1.01        1.01        9.45        0.31
    mainline      0.20        0.00        0.00        0.00
    creamline     0.00        0.00        0.00        0.00
    assortment    0.00        1.00        0.00       -2.00;

a('mainline','kefir') = 1/6;
a('mainline','skim') = 1/6;
a('creamline','cream') = 1/0.3;

Positive Variable x(j);
Variable revenue;
Equations objective, resource(r);

objective.. revenue =e= sum(j, price(j)*x(j));
resource(r).. sum(j, a(r,j)*x(j)) =l= capacity(r);

Model dairy /all/;
option lp=cplex;
solve dairy using lp maximizing revenue;
display x.l, revenue.l;

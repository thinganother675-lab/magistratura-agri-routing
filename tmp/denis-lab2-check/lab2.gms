* Исходные данные
$include base_data.inc

Sets
    reportProduct(j) / milk   'Молоко',
                       kefir  'Кефир',
                       cream  'Сметана',
                       yogurt 'Йогурт' /
    reportResource(r) / raw   'Сырое молоко',
                        line1 'Первая линия',
                        line2 'Вторая линия' /
    reportUnit(r) / raw   'ц/сут',
                    line1 'ч/сут',
                    line2 'ч/сут' /;

* Математическая модель
Positive Variable x(j);
Variable revenue;

Equations
    objective
    resource(r);

objective..   revenue =e= sum(j, price(j) * x(j));
resource(r).. sum(j, a(r,j) * x(j)) =l= capacity(r);
x.lo(j) = lower(j);
x.up(j)$bounded(j) = upper(j);
x.l(j) = initial(j);
Model dairy /all/;

* Настройка решателя и поиск оптимума
$onecho > highs.opt
solver = simplex
presolve = off
$offecho
option lp=highs;
dairy.optfile=1;
solve dairy using lp maximizing revenue;
abort$(dairy.modelstat<>1 or dairy.solvestat<>1) 'Оптимальное решение не найдено';
display x.l, revenue.l, resource.m;

* Результаты
$if not dexist results $call mkdir results
File report /'results/base_result.csv'/;
report.pw=32767;
put report 'model_status;solve_status;revenue_rub_day';
loop(r, put ';cap_' r.tl:0);
loop(j, put ';price_' j.tl:0);
loop(j, put ';lower_' j.tl:0);
loop(j, put ';x_' j.tl:0);
put / dairy.modelstat:0:0 ';' dairy.solvestat:0:0 ';' revenue.l:0:8;
loop(r, put ';' capacity(r):0:8);
loop(j, put ';' price(j):0:8);
loop(j, put ';' lower(j):0:8);
loop(j, put ';' x.l(j):0:8);
putclose;

Parameter usedResource(r);
usedResource(r) = sum(j, a(r,j) * x.l(j));
File readable /'results/lab2_summary.txt'/;
readable.pw = 32767;
put readable 'ИСХОДНАЯ МОДЕЛЬ' / 'Решение: оптимально' /;
put 'Максимальная выручка: ' revenue.l:0:2 ' руб./сут' / /;
put 'ВЫПУСК ПРОДУКЦИИ' /;
loop(j,
    if(reportProduct(j), put reportProduct.te(j):0;
    else put j.tl:0;);
    put ': ' x.l(j):0:6 ' ц/сут';
    put ' | минимум: ' x.lo(j):0:6;
    if(bounded(j), put ' | максимум: ' x.up(j):0:6;
    else put ' | максимум: не задан';);
    put /;
);
put / 'РЕСУРСЫ: использовано / доступно' /;
loop(r,
    if(reportResource(r), put reportResource.te(r):0;
    else put r.tl:0;);
    put ': ' usedResource(r):0:6 ' / ' capacity(r):0:6 ' ';
    if(reportUnit(r), put reportUnit.te(r):0;
    else put 'ед./сут';);
    put ' | остаток: ' (capacity(r) - usedResource(r)):0:6 /;
);
putclose readable;
abort$(readable.errors) 'Ошибка записи текстового итога';

put_utility 'log' / '========== ИСХОДНАЯ МОДЕЛЬ ==========';
put_utility 'log' / 'Решение: оптимально';
put_utility 'log' / 'Максимальная выручка: ' revenue.l:0:2 ' руб./сут';
loop(j,
    if(reportProduct(j),
        put_utility 'log' / reportProduct.te(j):0 ': ' x.l(j):0:6 ' ц/сут';
    else
        put_utility 'log' / j.tl:0 ': ' x.l(j):0:6 ' ц/сут';
    );
);
put_utility 'log' / 'Ресурсы: использовано / доступно';
loop(r,
    if(reportResource(r),
        put_utility 'log' / reportResource.te(r):0 ': ' usedResource(r):0:2 ' / ' capacity(r):0:2 ' ' reportUnit.te(r):0;
    else
        put_utility 'log' / r.tl:0 ': ' usedResource(r):0:2 ' / ' capacity(r):0:2;
    );
);
put_utility 'log' / 'Текстовый итог: results/lab2_summary.txt';

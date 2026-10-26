from pathlib import Path
import sys,csv,json
root=Path(r'C:/sarychev/Codex/magistratura')
sys.path.insert(0,str(root/'coursework/mmm-ppr/variant-11/runtime/python_packages'))
import numpy as np
from scipy.stats import rankdata,spearmanr
from scipy.optimize import linprog
out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'coursework/gams-2026/lab10-variant8'
data=list(csv.DictReader((out/'input_data.csv').open()))
scores=list(csv.DictReader((out/'efficiencies.csv').open()))
assert len(data)==len(scores)==25, 'Expected 25 input and score rows'
assert [z['firm'] for z in data]==[z['firm'] for z in scores], 'Input and score firm order mismatch'
Y=np.array([[float(z['y1']),float(z['y2'])] for z in data])
X=np.array([[float(z['x1']),float(z['x2'])] for z in data])
eff=np.array([float(z['efficiency']) for z in scores]); eff[np.abs(eff-1)<1e-9]=1
independent=[]
for i in range(25):
 A=np.vstack([np.column_stack([X.T,np.zeros(2)]),np.column_stack([-Y.T,Y[i]])])
 res=linprog(np.r_[np.zeros(25),-1],A_ub=A,b_ub=np.r_[X[i],np.zeros(2)],A_eq=np.array([np.r_[np.ones(25),0]]),b_eq=[1],bounds=[(0,None)]*25+[(1,None)],method='highs')
 assert res.success
 independent.append({'firm':f'f{i+1}','highs_phi':res.x[-1],'gams_phi':float(scores[i]['phi']),'absolute_difference':abs(res.x[-1]-float(scores[i]['phi']))})
with (out/'independent-check.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=independent[0]);w.writeheader();w.writerows(independent)
size=X.sum(axis=1); share=X[:,0]/size
er=rankdata(eff,method='average'); xc=er-er.mean(); xc=xc/np.linalg.norm(xc)
B=199999; seed=20261024; tests=[]
for name,arr in [('size',size),('share',share)]:
 rho,pa=spearmanr(eff,arr); yr=rankdata(arr,method='average'); yc=yr-yr.mean();yc/=np.linalg.norm(yc)
 rng=np.random.default_rng(seed);count=0
 for start in range(0,B,10000):
  n=min(10000,B-start)
  perms=np.array([rng.permutation(xc) for _ in range(n)])
  count+=np.count_nonzero(np.abs(perms@yc)>=abs(rho)-1e-12)
 tests.append(dict(predictor=name,n=25,rho=float(rho),p_permutation=(count+1)/(B+1),p_asymptotic=float(pa),B=B,seed=seed,extreme_count=int(count),alpha=.05,reject=bool((count+1)/(B+1)<.05)))
with (out/'spearman.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=tests[0]);w.writeheader();w.writerows(tests)
with (out/'ranks.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['firm','efficiency_for_statistics','size','share','rank_efficiency','rank_size','rank_share'])
 for i in range(25):w.writerow([f'f{i+1}',eff[i],size[i],share[i],er[i],rankdata(size)[i],rankdata(share)[i]])
result={'DEA_independent_max_phi_difference':max(z['absolute_difference'] for z in independent),'efficient_count':int(sum(eff==1)),'minimum_efficiency':float(min(eff)),'tests':tests}
(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

source='''Лабораторная работа 10 пункты 1 2 3 Вариант 8
Сарычев Антоний Евгеньевич Группа ДЭ39-26

Цель: оценить технологическую эффективность 25 консалтинговых фирм и проверить её ранговую связь с размером и долей юристов.
Исходные данные: y1 есть доход юридических услуг, y2 есть доход реинжиниринга, тыс. руб.; x1 есть число юристов, x2 есть число экономистов, человек.
Источник: методичка Лабораторные работы, PDF страница 29, печатная страница 57. Все 25 строк варианта 8 визуально сверены с таблицей. Разрешённый выбор модели: ориентация на выпуск, переменная отдача масштаба (VRS).
Задание: 1) построить собственную DEA модель и рассчитать эффективность в GAMS; 2) проверить корреляцию Спирмена эффективности с размером x1+x2; 3) проверить корреляцию Спирмена эффективности с долей юристов x1/(x1+x2). Уровень значимости 0.05.
Таблица фактически запущенной модели экспортируется GAMS в input_data.csv. Статистика читает именно этот файл и проверяет совпадение порядка firm с efficiencies.csv.
'''
(out/'01_УСЛОВИЕ.txt').write_text(source,encoding='utf-8')
report=source+'''
Математическая модель
Для каждой оцениваемой фирмы m решается отдельная LP на общей индексированной модели. j пробегает 25 фирм; r пробегает y1,y2,x1,x2.
max phi_m
sum_j lambda_j*x1_j <= x1_m
sum_j lambda_j*x2_j <= x2_m
sum_j lambda_j*y1_j >= phi_m*y1_m
sum_j lambda_j*y2_j >= phi_m*y2_m
sum_j lambda_j = 1
lambda_j >= 0, phi_m >= 1.
Эффективность E_m = 1/phi_m, от 0 до 1. phi является свободной переменной с нижней границей 1. Ограничение суммы lambda задаёт VRS. phi показывает максимально допустимое пропорциональное увеличение обоих выпусков при наблюдаемых ресурсах. E=1 означает радиальную эффективность; без второй фазы анализа остатков это не доказывает сильную Парето-эффективность.

Исходные данные и результаты
Фирма y1 y2 x1 x2 phi E
'''
for i,z in enumerate(data):report+=' '.join([z['firm']]+[z[k] for k in ['y1','y2','x1','x2']]+[f"{float(scores[i]['phi']):.5g}",f'{eff[i]:.5g}'])+'\n'
report+='''
Решение GAMS
Одна модель dea использует таблицу data(j,r) и переменные интенсивности lambda(j). Одна семья inputLimit(r), одна outputTarget(r) и convexity генерируют ограничения. Цикл m подставляет данные оцениваемой фирмы и выполняет 25 LP решателем CPLEX. lab10.gms полностью самодостаточен; исходная таблица внутри него. Для всех 25 задач Model Status = 1, Solver Status = 1. Неотрицательность, phi>=1, входы, выходы и сумма lambda проверяются после каждого solve с допуском 1e-6. Выведенные peers содержат веса больше 1e-8; возможны альтернативные оптимальные наборы эталонов.
'''
report+=f"Независимая проверка 25 LP SciPy HiGHS: максимальное расхождение phi с GAMS {result['DEA_independent_max_phi_difference']:.3g}. Радиально эффективных фирм {result['efficient_count']} из 25; минимальная эффективность {min(eff):.5g} у фирмы 16.\n"
report+='''
Корреляция Спирмена
Для равных значений назначены средние ранги. Коэффициент есть корреляция Пирсона средних рангов, а не формула без поправок на связи. Погрешности |E-1|<1e-9 приведены к 1 только при статистическом анализе, чтобы численная погрешность LP не разбивала группу эффективных фирм.
Нулевая гипотеза перестановочного теста: обменяемость значений эффективности относительно фиксированного признака, то есть независимость двух рядов. Альтернатива двусторонняя. Выполнено B=199999 случайных перестановок рангов эффективности; генератор NumPy default_rng, seed=20261024 отдельно для каждого признака. Число b учитывает |rho_perm| >= |rho_observed| с вычислительным допуском 1e-12. p=(b+1)/(B+1). Это оценка Монте-Карло, не точное перечисление всех перестановок. Дополнительно приведено асимптотическое p из scipy.stats.spearmanr: t=rho*sqrt((n-2)/(1-rho^2)), распределение Стьюдента с 23 степенями свободы. Основное решение принимается по перестановочному p.
'''
for t in tests:
 report+=f"{t['predictor']}: n=25; rho={t['rho']:.5g}; p перестановочное={t['p_permutation']:.5g}; p асимптотическое={t['p_asymptotic']:.5g}; b={t['extreme_count']}. "
 report+=('Нулевая гипотеза отвергается.\n' if t['reject'] else 'На уровне 0.05 нулевая гипотеза не отвергается.\n')
report+='Вывод: статистически значимой связи эффективности с размером фирмы и долей юристов в этой выборке не обнаружено. Отсутствие значимости не доказывает отсутствие любой зависимости. Корреляционный анализ не устанавливает причинного влияния. DEA оценки зависят от общей выборки эталонов; обычные перестановочные p здесь используются как учебная описательная проверка без специальной коррекции зависимости DEA оценок.\n'
(out/'02_ХОД_И_РЕЗУЛЬТАТЫ.txt').write_text(report,encoding='utf-8')
(out/'STUDIO_README_RU.txt').write_text('''GAMS Studio
1. Открыть lab10.gms и выбрать эту папку как рабочий каталог.
2. Запустить F9. Требуется решатель CPLEX.
3. В lab10.lst проверить 25 секций решения: SOLVER STATUS 1, MODEL STATUS 1.
4. efficiencies.csv содержит phi, E=1/phi, статусы и максимальную невязку. peers.csv содержит положительные веса эталонных фирм.
5. После завершения F9 запустить 04_RECALCULATE_STATS.cmd. Статистика читает input_data.csv и efficiencies.csv фактического запуска, проверяет порядок фирм. До запуска статистики сохранить изменения модели и обязательно выполнить F9. 03_OPEN_GAMS.cmd открывает модель в GAMS Studio на этом ПК.
6. Статистика рассчитана отдельно в Python по разрешённому заданием инструменту. spearman.csv содержит обе проверки; ranks.csv позволяет повторить анализ средних рангов в Excel. Скрипт воспроизведения находится в tmp/gams-future-tools/lab10/analyze.py относительно корня проекта, вне папок GAMS. Зависимости scipy/numpy берутся из существующего runtime/python_packages варианта 11 без изменения старых файлов.
Команда GAMS: gams lab10.gms lo=3
Проверка: independent-check.csv и verification.json. Эти файлы не заменяют основное решение GAMS.
''',encoding='utf-8')



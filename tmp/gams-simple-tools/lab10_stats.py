from pathlib import Path
import sys,subprocess,csv,json
root=Path(r'C:/sarychev/Codex/magistratura')
out=root/'coursework/gams-2026/STUDY_SIMPLE_VARIANT8/lab10'
subprocess.run([sys.executable,str(root/'tmp/gams-future-tools/lab10/analyze.py'),str(out)],check=True)
old=list(csv.DictReader((root/'coursework/gams-2026/lab10-variant8/efficiencies.csv').open()))
new=list(csv.DictReader((out/'efficiencies.csv').open()))
assert [r['firm'] for r in old]==[r['firm'] for r in new]
assert all(r['modelstat']=='1' and r['solvestat']=='1' for r in new)
gap=max(abs(float(a['phi'])-float(b['phi'])) for a,b in zip(old,new))
assert gap<1e-9
t=(out/'02_ХОД_И_РЕЗУЛЬТАТЫ.txt').read_text(encoding='utf-8')
t=t.replace('Неотрицательность, phi>=1, входы, выходы и сумма lambda проверяются после каждого solve с допуском 1e-6. Выведенные peers содержат веса больше 1e-8; возможны альтернативные оптимальные наборы эталонов.','В упрощённой модели проверки вынесены из GAMS во внешний расчёт. Независимое решение всех 25 LP выполнено в SciPy HiGHS. peers.csv содержит все 625 весов, включая нулевые; возможны альтернативные оптимальные наборы эталонов.')
(out/'02_ХОД_И_РЕЗУЛЬТАТЫ.txt').write_text(t,encoding='utf-8')
stats=json.loads((out/'verification.json').read_text())
(out/'COMPARISON.txt').write_text(f'Сравнение с исходной ЛР10\n25 статусов 1/1.\nМаксимальное расхождение phi с исходной GAMS моделью: {gap:.3g}.\nРадиально эффективных фирм: {stats["efficient_count"]}.\nКоэффициенты Спирмена и p сохранены; подробности spearman.csv.\n',encoding='utf-8')
print('GAMS comparison PASS; max phi difference:',gap)

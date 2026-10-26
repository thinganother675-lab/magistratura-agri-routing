from pathlib import Path
import csv, shutil
base=Path('coursework/mmm-ppr/variant-11')
dest=base.with_name('variant-3')
for directory in ['scripts','models','data','results','logs','submission']:
    (dest/directory).mkdir(parents=True,exist_ok=True)
for file in ['.gitignore','requirements.txt','run_all.ps1']:
    shutil.copyfile(base/file,dest/file)
for file in (base/'scripts').glob('*.py'):
    text=file.read_text(encoding='utf-8').replace('variant-11','variant-3').replace('variant11','variant3').replace("'variant':11","'variant':3")
    if file.name=='common.py':
        text=text.replace("sys.path.insert(0, str(ROOT / 'runtime/python_packages'))", "sys.path.insert(0, str(ROOT.parent / 'variant-11/runtime/python_packages'))\nsys.path.insert(0, str(ROOT / 'runtime/python_packages'))")
    if file.name=='prepare_data.py':
        text=text.replace('138000,25000','138000,22000').replace('9.45,.85','9.45,.9').replace('[-.062,-.062,-.022,-.047]','[-.033,-.034,-.060,-.051]').replace('[-.014,-.012,-.015,-.017]','[-.020,-.012,-.019,-.014]').replace('[25,30,1.5,.75]','[25,30,1.5,1]')
    if file.name=='independent_check.py':
        text=text.replace('13800,7500','13800,7200').replace('9.45,16','9.45,15').replace('[0,0,0,4.]','[0,0,0,5.]').replace('[140.,21,16,17]','[140.,21,16,16]').replace("F('9.45'),F(16)","F('9.45'),F(15)").replace('[0,0,0,4]]','[0,0,0,5]]').replace('1.5*ts','2*ts').replace('z[3]/1.5','z[3]/2')
    if file.name=='verify_gams.py':
        text=text.replace('q[3]/1.5','q[3]/2').replace('speed_yogurt_t_per_h=1.5','speed_yogurt_t_per_h=2')
    (dest/'scripts'/file.name).write_text(text,encoding='utf-8')
for file in (base/'models').glob('*.gms'):
    text=file.read_text().replace('variant 11','variant 3')
    if file.name=='lab2.gms':
        text=text.replace('curd_bars 7500','curd_bars 7200').replace('curd_bars 16','curd_bars 15').replace('/0.25 =l= 17','/0.2 =l= 16').replace('/.25-17','/.2-16').replace("/.25):0:10 ',17,'","/.2):0:10 ',16,'")
    if file.name=='lab8.gms':
        text=text.replace('yogurt .85','yogurt .9').replace('milk -.062,kefir -.062,cream -.022,yogurt -.047','milk -.033,kefir -.034,cream -.060,yogurt -.051').replace('milk -.014,kefir -.012,cream -.015,yogurt -.017','milk -.020,kefir -.012,cream -.019,yogurt -.014').replace('cream 1.5,yogurt .75','cream 1.5,yogurt 1').replace("q('yogurt')/1.5","q('yogurt')/2").replace("q.l('yogurt')/1.5","q.l('yogurt')/2").replace("/(1+ea('yogurt')))/1.5","/(1+ea('yogurt')))/2").replace("q.up('yogurt')=1.5*ts","q.up('yogurt')=2*ts")
    (dest/'models'/file.name).write_text(text,encoding='ascii')
with (base.parent/'audit-2026-10-07/sources/dea-all-variants.csv').open(encoding='utf-8-sig') as f:
    rows=[r for r in csv.DictReader(f) if r['variant']=='3']
assert len(rows)==25
with (dest/'data/dea-variant-3.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['firm','y1','y2','x1','x2']);w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in rows)
text=(dest/'run_all.ps1').read_text(encoding='utf-8')
text=text.replace("else {$GamsExe=(Get-Command gams -ErrorAction Stop).Source}","elseif (Test-Path -LiteralPath (Join-Path $taskRoot '../variant-11/runtime/gams/54.5/gams.exe')) {$GamsExe=(Resolve-Path (Join-Path $taskRoot '../variant-11/runtime/gams/54.5/gams.exe')).Path}\n    else {$GamsExe=(Get-Command gams -ErrorAction Stop).Source}")
(dest/'run_all.ps1').write_text(text,encoding='utf-8-sig')
print('Variant 3 prepared with 25 visually verified firms')

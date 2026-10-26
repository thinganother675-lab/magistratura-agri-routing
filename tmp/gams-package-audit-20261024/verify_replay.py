from pathlib import Path
from zipfile import ZipFile
import csv,re,json,hashlib
root=Path('C:/sarychev/Codex/magistratura')
original=root/'coursework/gams-2026'
audit=root/'tmp/gams-package-audit-20261024'
comparisons=[]
for lab in ['lab8-variant8','lab10-variant8']:
    old=original/lab; new=audit/'remaining'/lab
    files=['results/base_results.csv','results/scenario_results.csv'] if lab.startswith('lab8') else ['efficiencies.csv','spearman.csv','input_data.csv']
    for name in files:
        a=list(csv.DictReader((old/name).open(encoding='utf-8-sig')))
        b=list(csv.DictReader((new/name).open(encoding='utf-8-sig')))
        assert len(a)==len(b),(lab,name)
        err=0
        for ra,rb in zip(a,b):
            assert ra.keys()==rb.keys()
            for k in ra:
                try:
                    x,y=float(ra[k]),float(rb[k]); err=max(err,abs(x-y)/max(1,abs(x)))
                except ValueError: assert ra[k]==rb[k],(lab,name,k)
        assert err<1e-8,(lab,name,err)
        comparisons.append({'lab':lab,'file':name,'rows':len(a),'max_relative_difference':err})
status_counts={}
for rel,count in [('first/SHOW_LAB2_VARIANT8/audit_lab2.lst',1),('remaining/lab8-variant8/audit_base.lst',3),('remaining/lab8-variant8/audit_scenarios.lst',60),('remaining/lab10-variant8/audit_lab10.lst',25)]:
    text=(audit/rel).read_text(encoding='utf-8',errors='replace')
    found=re.findall(r'MODEL STATUS\s+(\d+)',text)
    assert len(found)==count,(rel,len(found))
    assert all(v==('2' if 'lab8-' in rel else '1') for v in found)
    status_counts[rel]=len(found)
for fn in ['Lab2_Variant8_Sarychev.zip','Remaining_Labs_Variant8.zip']:
    z=ZipFile(original/fn); assert z.testzip() is None
    assert not any(n.endswith('.py') for n in z.namelist())
for folder in ['SHOW_LAB2_VARIANT8','lab8-variant8','lab10-variant8']:
    for file in (original/folder).glob('*.cmd'):
        text=file.read_text(encoding='ascii')
        if 'GAMS_DIR=' in text:
            d=re.search(r'set "GAMS_DIR=(.*?)"',text).group(1)
            assert (Path(d)/'studio/studio.exe').exists()
            assert 'cd /d "%~dp0"' in text
for n in ['report.pdf','report.docx','lab2.gms']:
    assert (original/'SHOW_LAB2_VARIANT8'/n).read_bytes()==(audit/'first/SHOW_LAB2_VARIANT8'/n).read_bytes()
result={'passed':True,'replay_status_counts':status_counts,'comparisons':comparisons,'first_report_and_model_unchanged':True,'launcher_paths_verified':True,'archives_valid':True}
(audit/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

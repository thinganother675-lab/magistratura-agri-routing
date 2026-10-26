"""Build review/submission bundles. No software binaries, license or original book."""
from common import ROOT,PROJECT_ROOT,IN_PROJECT,write_json
import shutil,hashlib,json,zipfile
from pathlib import Path

def main():
    assert json.loads((ROOT/'results/verification.json').read_text())['all_passed']
    docxdir=PROJECT_ROOT/f'output/docx/mmm-ppr-variant-{ROOT.name.split("-")[-1]}' if IN_PROJECT else ROOT/'reports'
    pdfdir=PROJECT_ROOT/'output/pdf/mmm-ppr-variant-11' if IN_PROJECT else ROOT/'reports'
    groups={
      'lab2':['models/lab2.gms','results/lab2_gams.csv','results/lab2_gams_resources.csv','results/lab2_simplex_exact.txt','logs/lab2.lst','MODEL_LAB2_FOR_TEACHER_RU.txt'],
      'lab8':['models/lab8.gms','models/scenarios.inc','data/scenarios.csv','results/lab8_scenarios_table.txt','results/lab8_final_scenarios.csv','results/lab8_gams_starts.csv','results/lab8_python_scenarios.csv','results/lab8_certificates.json','logs/lab8.lst'],
      'lab10':['models/lab10.gms','models/dea-data.inc','data/dea-variant-11.csv','results/lab10_gams_dea.csv','results/lab10_gams_peers.csv','results/lab10_python_dea.csv','results/lab10_python_peers.csv','results/lab10_stats.json','logs/lab10.lst']}
    manifests={}
    for lab,files in groups.items():
        target=ROOT/'submission'/lab;target.mkdir(parents=True,exist_ok=True)
        # Preserve model-relative paths: flattening gms/inc/results breaks reruns.
        manifest=[]
        for name in files+['DEFENSE_RU.txt','START_HERE_RU.txt','RESEARCH_RU.txt','results/verification.json']:
            src=ROOT/name;dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
            manifest.append({'name':name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        for script in ['common.py','prepare_data.py','independent_check.py','verify_gams.py']:
            src=ROOT/'scripts'/script;dest=target/'scripts'/script;dest.parent.mkdir(exist_ok=True);shutil.copyfile(src,dest)
            manifest.append({'name':'scripts/'+script,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        pdf=pdfdir/f'{lab}_variant11_report.pdf';dest=target/pdf.name;shutil.copyfile(pdf,dest)
        manifest.append({'name':pdf.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        docx=docxdir/pdf.name.replace('.pdf','.docx');dest=target/docx.name;shutil.copyfile(docx,dest)
        manifest.append({'name':docx.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        assert len(manifest)<=20,(lab,len(manifest))
        assert all(x['bytes']<(10_000_000 if lab=='lab10' else 1_000_000) for x in manifest)
        with zipfile.ZipFile(ROOT/'submission'/f'{lab}_variant11.zip','w',zipfile.ZIP_DEFLATED) as z:
            for item in manifest:z.write(target/item['name'],item['name'])
        manifests[lab]={'files':manifest,'count':len(manifest),'zip_bytes':(ROOT/'submission'/f'{lab}_variant11.zip').stat().st_size}
    write_json('results/submission_manifest.json',manifests)
    output=PROJECT_ROOT/'output/mmm-ppr-variant11-package.zip' if IN_PROJECT else ROOT/'mmm-ppr-variant11-package.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for directory in ['models','data','results','scripts']:
            for path in (ROOT/directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(ROOT))
        for name in ['START_HERE_RU.txt','DEFENSE_RU.txt','MODEL_LAB2_FOR_TEACHER_RU.txt','RESEARCH_RU.txt','run_all.ps1','requirements.txt']:z.write(ROOT/name,name)
        for path in pdfdir.glob('*.pdf'):z.write(path,'reports/'+path.name)
        for path in docxdir.glob('*.docx'):z.write(path,'editable/'+path.name)
        for lab in groups:
            for suffix in ['log','lst']:
                path=ROOT/'logs'/f'{lab}.{suffix}';z.write(path,'logs/'+path.name)
    print('Package:',output,'bytes:',output.stat().st_size)
    print('Submission file counts:',{k:v['count'] for k,v in manifests.items()})

if __name__=='__main__':main()

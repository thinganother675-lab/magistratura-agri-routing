from pathlib import Path
import os,subprocess,json,re
from pypdf import PdfReader
from PIL import Image,ImageOps,ImageDraw
workspace=Path(__file__).resolve().parents[1]
python='C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
pdftoppm='C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe'
tmp=workspace/'tmp/coursework-render';tmp.mkdir(exist_ok=True)
os.environ['TEMP']=str(tmp);os.environ['TMP']=str(tmp);os.environ['PYTHONIOENCODING']='utf-8'
qa=[]
for v in [3,11]:
    for lab in [2,8,10]:
        name=f'lab{lab}_variant{v}_report'
        out=workspace/'tmp/docx'/f'variant{v}'/f'lab{lab}'
        subprocess.run([python,str(workspace/'tmp/render_docx.py'),str(workspace/'output/docx'/f'mmm-ppr-variant-{v}'/(name+'.docx')),'--output_dir',str(out),'--dpi','100','--emit_pdf'],check=True)
        pdf=workspace/'output/pdf'/f'mmm-ppr-variant-{v}'/(name+'.pdf')
        pdir=workspace/'tmp/pdfs'/f'mmm-ppr-variant-{v}'/'final'/f'lab{lab}';pdir.mkdir(parents=True,exist_ok=True)
        subprocess.run([pdftoppm,'-r','100','-png',str(pdf),str(pdir/'page')],check=True)
        text='\n'.join(p.extract_text() for p in PdfReader(pdf).pages)
        wordpdf=workspace/'tmp/docx'/f'variant{v}'/'native'/(name+'.pdf')
        wordtext='\n'.join(p.extract_text() for p in PdfReader(wordpdf).pages)
        person='Шестернин Денис' if v==3 else 'Сарычев Антоний Евгеньевич'
        assert person in text and person in wordtext
        assert 'ДЭ 39-26' in text and 'ДЭ 39-26' in wordtext
        assert 'Сведения о студенте' not in text+wordtext
        assert 'Вариант '+str(14-v) not in text+wordtext
        if v==3 and lab==8:
            assert '34 022 234,28' in text and '34 022 234,28' in wordtext
            assert '31 849 393' not in text+wordtext
        if v==11 and lab==8:assert '31 849 393,02' in text+wordtext
        for source,folder in [('PDF',pdir),('Word',out)]:
            imgs=sorted(folder.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
            assert len(imgs)==len(PdfReader(pdf).pages),(source,v,lab,len(imgs))
            # Full page contact sheets retain 100 dpi; no content resize.
            for pairidx in range(0,len(imgs),2):
                pages=[Image.open(p).convert('RGB') for p in imgs[pairidx:pairidx+2]]
                width=sum(p.width for p in pages);height=max(p.height for p in pages)+32
                sheet=Image.new('RGB',(width,height),'#e8e8e8');draw=ImageDraw.Draw(sheet)
                x=0
                for pidx,page in enumerate(pages):
                    sheet.paste(page,(x,32));draw.text((x+12,7),f'{source} variant {v} lab {lab} page {pairidx+pidx+1}',fill='black');x+=page.width
                sheet.save(tmp/f'{source.lower()}-v{v}-lab{lab}-pair{pairidx//2+1}.png')
        qa.append(dict(variant=v,lab=lab,pdf_pages=len(PdfReader(pdf).pages),word_pages=len(PdfReader(wordpdf).pages),identity_checked=True))
        print(v,lab,'rendered and identity checked',flush=True)
(tmp/'qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')

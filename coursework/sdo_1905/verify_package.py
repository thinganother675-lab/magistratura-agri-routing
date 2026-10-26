from pathlib import Path
import re,json
from urllib.parse import unquote
from PIL import Image, ImageOps, ImageDraw
import pypdfium2 as pdfium
R=Path(__file__).parent
Q=R/'qa'; Q.mkdir(exist_ok=True)
sheet=Image.new('RGB',(1600,1200),'#e8e8e8')
draw=ImageDraw.Draw(sheet)
for n,pages in enumerate(([0,26,68,94],[0,21,64,94],[0,29,69,93],[0,8,50,92],[0,25,51,81]),1):
    doc=pdfium.PdfDocument(R/'originals'/f'Лекция {n}.pdf')
    for col,p in enumerate(pages):
        image=doc[p].render(scale=.65).to_pil().convert('RGB')
        image.thumbnail((392,208))
        x=col*400;y=(n-1)*240
        sheet.paste(image,(x,y+22))
        draw.text((x+4,y+3),f'Lecture {n}, slide {p+1}',fill='black')
sheet.save(Q/'lecture_sample_contact.jpg',quality=90)
files=sorted((R/'originals').glob('*.png'))
sheet=Image.new('RGB',(1500,1200),'#eeeeee'); draw=ImageDraw.Draw(sheet)
for i,p in enumerate(files):
    image=Image.open(p).convert('RGB');image.thumbnail((490,272))
    x=(i%3)*500;y=(i//3)*300
    draw.text((x+5,y+3),p.name,fill='black');sheet.paste(image,(x,y+24))
sheet.save(Q/'diagram_contact.jpg',quality=90)
broken=[]
for p in [*R.glob('*.md'),*R.joinpath('summaries').glob('*.md')]:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if '://' not in target and not (p.parent/unquote(target.split('#')[0])).exists():
            broken.append({'file':str(p.relative_to(R)),'target':target})
assert not broken,broken
assert len(list(R.joinpath('summaries').glob('LECTURE_*.md')))==5
assert len(list(R.joinpath('summaries').glob('PZ_*.md')))==14
v=json.loads((R/'verification.json').read_text(encoding='utf-8'))
v.update(summary_count=19,broken_local_links=broken,visual_qa='20 sample lecture pages and 11 provided PNG diagrams rendered to contact sheets; source files not edited',
    lecture_reading_scope='Every slide indexed from extracted text; source concepts and practical references reviewed. Not a visual inspection of all 500 slides.')
(R/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
print('19 summaries, local links valid; visual contact sheets ready.')

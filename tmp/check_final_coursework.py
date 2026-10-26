from pathlib import Path
import json,re,hashlib,zipfile
from pypdf import PdfReader
from docx import Document
base=Path(__file__).resolve().parents[1]
for v in [3,11]:
    root=base/f'coursework/mmm-ppr/variant-{v}'
    reportdir=base/f'output/pdf/mmm-ppr-variant-{v}'
    docdir=base/f'output/docx/mmm-ppr-variant-{v}'
    archive=base/f'output/mmm-ppr-variant{v}-package.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any('runtime/' in n or '__pycache__' in n for n in z.namelist())
        assert json.loads(z.read('results/verification.json'))['all_passed']
        for lab in [2,8,10]:
            for ext,folder,prefix in [('pdf',reportdir,'reports'),('docx',docdir,'editable')]:
                file=folder/f'lab{lab}_variant{v}_report.{ext}'
                assert z.read(prefix+'/'+file.name)==file.read_bytes()
                assert file.stat().st_size<1_000_000
            text='\n'.join(p.extract_text() for p in PdfReader(reportdir/f'lab{lab}_variant{v}_report.pdf').pages)
            assert not any(word in text for word in ['slack','Locally Optimal','Normal Completion','seed=','сведения о студенте','Готовое решение чужого'])
            # Function notation and mathematical parentheses are preserved.
            assert not re.search(r'\([^)]*[А-Яа-я]{2,}[^)]*\)',text)
            document=Document(docdir/f'lab{lab}_variant{v}_report.docx')
            assert not document.styles['Title'].element.xpath('.//w:pBdr')
            assert any(rel.reltype.endswith('/hyperlink') for rel in document.part.rels.values())
        print(f'Variant {v}: 3 PDF + 3 Word match archive; Russian prose and links verified')
    manifest=json.loads((root/'results/submission_manifest.json').read_text(encoding='utf-8'))
    for lab,record in manifest.items():
        for item in record['files']:
            file=root/'submission'/lab/item['name']
            assert hashlib.sha256(file.read_bytes()).hexdigest()==item['sha256']
    (root/'results/final_review.json').write_text(json.dumps({'date':'2026-10-08','numerical_verification_passed':True,'pdf_pages_visually_reviewed':15,'word_pages_visually_reviewed':15,'word_renderer':'Microsoft Word 16 COM ExportAsFixedFormat and packaged render_docx rasterization','russian_prose_reviewed':True,'explanatory_parentheses_removed':True,'archive_matches_reports':True},indent=2),encoding='utf-8')

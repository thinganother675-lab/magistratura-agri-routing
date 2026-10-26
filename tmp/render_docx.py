"""Use the packaged renderer with Microsoft Word's native PDF conversion.
The packaged LibreOffice conversion is unavailable on this Windows host.
Microsoft Word COM exports are produced by render_coursework_word.ps1.
Only conversion is replaced; page rasterization is the packaged renderer.
"""
import importlib.util,sys,shutil
from pathlib import Path
source=Path('C:/Users/User/.codex/plugins/cache/openai-primary-runtime/documents/26.1007.11041/skills/documents/render_docx.py')
spec=importlib.util.spec_from_file_location('packaged_docx_renderer',source)
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
def native_conversion(doc_path,user_profile,convert_tmp_dir,stem,verbose):
    filename=Path(sys.argv[1]).stem
    variant=filename.split('variant')[1].split('_')[0]
    pdf=Path(__file__).parent/'docx'/f'variant{variant}'/'native'/f'{filename}.pdf'
    assert pdf.exists(),f'Microsoft Word PDF missing: {pdf}'
    target=Path(convert_tmp_dir)/f'{stem}.pdf';shutil.copyfile(pdf,target)
    return str(target),'Converted by Microsoft Word 16 COM ExportAsFixedFormat'
renderer.convert_to_pdf=native_conversion
renderer.main()

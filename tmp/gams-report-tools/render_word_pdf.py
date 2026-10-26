import os,sys,importlib.util
from pathlib import Path
root=Path(__file__).parent
os.environ['TEMP']=os.environ['TMP']=str(root)
import tempfile
tempfile.tempdir=str(root)
spec=importlib.util.spec_from_file_location('renderer',r'C:/Users/User/.codex/plugins/cache/openai-primary-runtime/documents/26.1020.11348/skills/documents/render_docx.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
pdf=Path(r'C:/sarychev/Codex/magistratura/tmp/gams-report-tools/final-report.pdf')
m.convert_to_pdf=lambda *a,**k:(str(pdf),'Word COM export used because LibreOffice is unavailable')
sys.argv=['render_docx.py',r'C:/sarychev/Codex/magistratura/coursework/gams-2026/lab2-variant8/report/lab2-variant8-sarychev.docx','--output_dir',str(root/'render'),'--dpi','120']
m.main()

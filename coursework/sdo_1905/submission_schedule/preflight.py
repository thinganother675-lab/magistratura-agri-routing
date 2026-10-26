from pathlib import Path
from datetime import datetime,timezone,timedelta
from zipfile import ZipFile
from pypdf import PdfReader
import json,hashlib,tomllib
R=Path(__file__).resolve().parent
plan=json.loads((R/'plan.json').read_text(encoding='utf-8'))
checks=[]
for slot in plan['slots']:
    for f in slot['files']:
        p=Path(f['path'])
        assert p.is_file(),p
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest==f['sha256'],p
        if p.suffix in ('.docx','.xlsx'):
            with ZipFile(p) as z:assert z.testzip() is None
        else:
            assert p.suffix=='.pdf'
            assert len(PdfReader(p).pages)==4
        checks.append(dict(pz=slot['pz'],file=p.name,bytes=p.stat().st_size,sha256_match=True,readable=True))
cfg=tomllib.loads(Path('C:/Users/User/.codex/automations/1905-1-6-16-19/automation.toml').read_text(encoding='utf-8'))
assert cfg['status']=='ACTIVE'
assert cfg['rrule']==plan['automations'][0]['rrule']
assert plan['slots'][0]['scheduled_at']=='2026-10-16T13:05:00+03:00'
report=dict(checked_at=datetime.now(timezone(timedelta(hours=3))).isoformat(),files_checked=len(checks),practicals=14,all_pass=True,
  checks=checks,first_slot=plan['slots'][0]['scheduled_at'],automation_status=cfg['status'],
  browser_check=dict(activity_url='https://sdo.timacad.ru/mod/assign/view.php?id=93649',
    method='Свежая навигация разрешённым браузерным инструментом; DOM страницы задания',
    identity='Антоний Сарычев',login_active=True,assignment='Практическое задание 1',
    due='22 декабря 2026, 00:00',submission_status='Ответы на задание еще не представлены',add_submission_button_visible=True),
  uploads_performed=0,submission_controls_clicked=False,
  limitation='Вход подтверждён на момент проверки; перед отправкой нужен повторный контроль сессии.')
(R/'evidence/preflight_20261016.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(checked_at=report['checked_at'],files_checked=len(checks),all_pass=True,login_active=True,first_slot=report['first_slot'],uploads_performed=0),ensure_ascii=False))

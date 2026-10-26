from pathlib import Path
import json,re,hashlib,zipfile
from urllib.parse import quote
ROOT=Path(__file__).parent
BASE='https://sdo.timacad.ru'
PZ_IDS=[93649,93651,93652,93653,93655,93656,93657,93659,93660,93661,93662,93663,93664,93665]
PZ_CONTEXT=[515512,515514,515515,515516,515518,515519,515520,515522,515523,515525,515537,515538,515539,515540]
LECTURES=[
('Предприятие и информационная система',93644,515507),
('Архитектура предприятия',93645,515508),
('Бизнес-архитектура и AS-IS',93646,515509),
('Данные, приложения, интеграции, технологии и безопасность',93647,515510),
('Варианты, GAP-анализ, проверка и оценка эффекта',93648,515511)]
def file_group(name):
    if name.startswith('Лекция '):
        n=int(re.search(r'\d+',name)[0]); return f'Лекция {n}',LECTURES[n-1][1],LECTURES[n-1][2],name
    if name in ('00_Start.docx','01_Case.docx','Case_for_AI.txt'):return 'Общая инструкция',93650,515513,name
    if name=='All_examples.drawio':return 'ПЗ-01',PZ_IDS[0],PZ_CONTEXT[0],name
    n=int(re.search(r'(?:PZ|pz)(\d{2})',name)[1]); original='Operations.csv' if name.startswith('Operations_') else name
    return f'ПЗ-{n:02}',PZ_IDS[n-1],PZ_CONTEXT[n-1],original
manifest=json.loads((ROOT/'file_manifest.json').read_text(encoding='utf-8'))
for row in manifest:
    group,activity,context,original=file_group(row['name'])
    row.update(group=group,activity_url=f'{BASE}/mod/assign/view.php?id={activity}',source_name=original,
        source_url=f'{BASE}/pluginfile.php/{context}/mod_assign/introattachment/0/{quote(original)}?forcedownload=1',local_path='originals/'+row['name'])
(ROOT/'file_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Реестр исходных материалов курса 1905','',
'Источник: https://sdo.timacad.ru/course/view.php?id=1905. Сверено 16 октября 2026 года в авторизованной сессии. Все 20 элементов и 77 вложений просмотрены в списках сайта. Срок элементов: 22 декабря 2026, 00:00 (как отображает СДО).',
'','Скачивание выполнено через браузер. Оригиналы сохранены без изменения содержимого. Два вложения Operations.csv сохранены под разными локальными именами для сохранения происхождения.',
'','| Раздел | Локальный файл | Размер, байт | Источник |','|---|---|---:|---|']
for row in manifest:
    lines.append(f"| {row['group']} | [{row['name']}](originals/{quote(row['name'])}) | {row['bytes']} | [Вложение]({row['source_url']}) |")
(ROOT/'SOURCES_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
verification={'date':'2026-10-16','course_id':1905,'activities':20,'expected_attachments':77,'local_files':len(manifest),'pdf_pages':sum(x.get('pages',0) for x in manifest),
    'zero_byte_files':[x['name'] for x in manifest if x['bytes']==0],
    'zip_integrity':{},'source_sha256_valid':all(hashlib.sha256((ROOT/x['local_path']).read_bytes()).hexdigest()==x['sha256'] for x in manifest),
    'csv_copies_identical':(ROOT/'originals/Operations_PZ12.csv').read_bytes()==(ROOT/'originals/Operations_PZ13.csv').read_bytes(),
    'assignment_execution':'not_started','submission':'not_performed'}
for p in (ROOT/'originals').iterdir():
    if p.suffix in ('.docx','.xlsx'):
        with zipfile.ZipFile(p) as z:verification['zip_integrity'][p.name]=z.testzip()
assert len(manifest)==77 and not verification['zero_byte_files'] and verification['source_sha256_valid']
assert all(x is None for x in verification['zip_integrity'].values())
(ROOT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in verification.items() if k!='zip_integrity'},ensure_ascii=False))

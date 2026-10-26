from pathlib import Path
from datetime import datetime,timedelta,timezone
import json,csv,re,hashlib,shutil,zipfile,html
from urllib.parse import quote
from dateutil.rrule import rrulestr

R=Path(__file__).resolve().parent
S=R/'submission_schedule'; S.mkdir(exist_ok=True)
D=R/'denis_preparation_20261016';D.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def href(p,label):return '<a href="'+quote(str(p).replace('\\','/'),safe='/')+'">'+html.escape(label)+'</a>'
tz=timezone(timedelta(hours=3))
ids=[93649,93651,93652,93653,93655,93656]
slots=[]
for n,aid in enumerate(ids,1):
    date='2026-10-16' if n<=3 else '2026-10-19'
    hour=14+n if n<=3 else 11+n
    start=datetime.fromisoformat(f'{date}T{hour}:00:00+03:00')
    f=R/'run_20261016/submission'/f'PZ{n:02}_Сарычев_ДЭ39-26.docx';assert f.exists()
    assert start<datetime.fromisoformat('2026-12-22T00:00:00+03:00')
    slots.append(dict(pz=n,scheduled_at=start.isoformat(),start_window_ends_at=(start+timedelta(minutes=15)).isoformat(),
      activity_url=f'https://sdo.timacad.ru/mod/assign/view.php?id={aid}',file=str(f),sha256=sha(f),bytes=f.stat().st_size,
      expected_identity='Антоний Сарычев',group='ДЭ 39-26',status='scheduled',submitted_at=None))
rule='FREQ=WEEKLY;BYDAY=MO,FR;BYHOUR=15,16,17;BYMINUTE=0;BYSECOND=0;COUNT=6'
generated=list(rrulestr(rule,dtstart=datetime(2026,10,16,11,7,tzinfo=tz)))
assert [x.isoformat() for x in generated]==[x['scheduled_at'] for x in slots]
plan=dict(automation_id='1905-1-6-16-19',timezone='Asia/Riyadh (UTC+3), совпадает с Москвой',
 user_authorized=True,authorization_date='2026-10-16',course='https://sdo.timacad.ru/course/view.php?id=1905',
 visible_due_at_last_check='2026-12-22 00:00, отображение СДО',deadline_check='run_20261016/audit_20261016/deadlines.json',
 validation_at_each_run=['Текущая дата и окно','Файл и SHA256','Правильный пользователь и задание','Доступность сдачи','Нет уже отправленного ответа','Итоговый статус после отправки'],
 missed_slot_policy='Не догонять вне 15-минутного окна; сообщить пропуск. Иные ПЗ и даты не разрешены.',
 stop_after='2026-10-19T17:15:00+03:00',evidence_directory=str(S/'evidence'),slots=slots)
if (S/'plan.json').exists() and read(S/'plan.json').get('revision',0)>=2:
    # Rebuilding Denis's materials must not restore the superseded six-slot plan.
    plan=read(S/'plan.json')
else:
    write(S/'plan.json',plan)
(S/'evidence').mkdir(exist_ok=True)
if not (S/'slot_log.json').exists():write(S/'slot_log.json',dict(created_at=datetime.now(tz).isoformat(),events=[],note='Отправок ещё не было. Факт подтверждается только интерфейсом СДО.'))

# This package contains source material and preparation only, never filled answers.
manifest=read(R/'file_manifest.json');assert len(manifest)==77
for folder in ['originals','extracted','summaries']:
    dest=D/'materials'/folder;dest.mkdir(parents=True,exist_ok=True)
    for p in (R/folder).iterdir():
        if p.is_file():shutil.copy2(p,dest/p.name)
for entry in manifest:
    p=D/'materials'/entry['local_path'];assert sha(p)==entry['sha256'],p
source_manifest=[]
for x in manifest:
    y=dict(x);y['local_path']='materials/'+x['local_path'];source_manifest.append(y)
write(D/'source_manifest.json',source_manifest)
aliases={}
for x in source_manifest:
    name=x['name']
    if name.startswith('Answer_'):aliases['Answers/'+name]=x['local_path']
    elif name.startswith('Prompt_'):aliases['Prompts/'+name]=x['local_path']
    elif name.startswith('pz') or name=='All_examples.drawio':aliases['Diagrams/'+name]=x['local_path']
    elif name in ['PZ12_Model.xlsx','PZ13_Effect.xlsx']:aliases['Data/'+name]=x['local_path']
aliases['Data/Operations.csv']='materials/originals/Operations_PZ12.csv'
assert sha(D/'materials/originals/Operations_PZ12.csv')==sha(D/'materials/originals/Operations_PZ13.csv')
write(D/'planning/source_path_aliases.json',dict(note='Пути из авторского пакета сопоставлены скачанным вложениям. Оба CSV прикреплены к разным заданиям и совпадают побайтно; исходники не переименованы.',aliases=aliases))

facts=(R/'extracted/01_Case.docx.txt').read_text(encoding='utf-8')
sections={}
matches=list(re.finditer(r'^К(\d{2})\. (.+)$',facts,re.M))
for i,m in enumerate(matches):
    sections['К'+m.group(1)]=dict(title=m.group(2),source_excerpt=facts[m.end():matches[i+1].start() if i+1<len(matches) else len(facts)].strip())
assert len(sections)==10
write(D/'planning/case_source_sections.json',dict(provenance='Дословные К01–К10 из 01_Case.docx, без авторских ответов',sections=sections))
write(D/'planning/variant_A_brief.json',dict(status='preparation_only',recommendation='A',basis=['К08','К09','PZ11_Instruction.docx'],
 source_parameters=dict(one_time_rub=24000,monthly_rub=1000,forecast_active_minutes=40,sensitivity_active_minutes=60),
 implementation_not_selected=['Конкретный способ блокировки версий','Структура рабочего контролируемого шаблона','Порядок замещения и принятия исправлений','Размещение независимой копии','Детальные критерии переключения'],
 dependencies=['ПЗ-1–10 устанавливают собственные AS-IS и требования','ПЗ-11 обосновывает выбор A','ПЗ-12 отдельно проверяет модель','ПЗ-13 считает A и чувствительность','ПЗ-14 согласует итог с A'],
 constraints=['Сохранить APP-04','Бюджет не более 120000 руб.','Создание и подтверждение разделены','Повторы/пропуски/конфликты и неполнота видимы','Не заявлять неподтверждённые испытания'],
 not_done=['Ответы ПЗ-1–14','Авторские схемы и заполненные таблицы Дениса','Запуск Excel и заполнение фактов Дениса','Расчёт эффекта для сдачи','Выбор d','Отправка в СДО']))
decisions=[
 dict(id='identity',question='Подтвердить полные ФИО и группу для титулов. В прошлых материалах встречается Шестернин Денис; не переносить автоматически.',required_before='заполнение документов'),
 dict(id='variant',question='Подтвердить рекомендуемый путь A на учебном кейсе либо назвать обоснованную причину B/собственного объекта.',required_before='проектные решения'),
 dict(id='d',question='Выбрать d от 0 до 9 для ПЗ-12; прошлый d Антония не наследуется.',required_before='ожидания и запуск ПЗ-12'),
 dict(id='verification',question='Личная проверка Денисом или явно согласованный агентный эксперимент? Результаты подписывать по фактическому исполнителю.',required_before='протокол ПЗ-12'),
 dict(id='tools',question='Какой табличный редактор доступен на компьютере Дениса и пересчитывает исходный XLSX?',required_before='фактические проверки'),
 dict(id='final_format',question='Выбрать итоговую форму ПЗ-14: PDF на 6–8 слайдов либо записку на 3–4 страницы; проверить разрешённое расширение в СДО.',required_before='оформление итога'),
]
write(D/'planning/decisions_before_execution.json',decisions)

requirements=[]
for n in range(1,15):
    text=(R/'extracted'/f'PZ{n:02}_Instruction.docx.txt').read_text(encoding='utf-8');lines=text.splitlines()
    def line(prefix):return next((x[len(prefix):].strip() for x in lines if x.startswith(prefix)),'')
    ai=lines.index('Оценка: 10 рабочих баллов');rubric=lines[ai+1:ai+5]
    ni=lines.index('Новый случай: покажите перенос знания');newcase=lines[ni+1]
    brief=(R/'summaries'/f'PZ_{n:02}_RU.md').read_text(encoding='utf-8')
    cm=re.search(r'\*\*(\d)/5',brief)
    requirements.append(dict(pz=n,title=lines[0],inputs=line('Исходные материалы:'),repeat=line('Повторить:'),
       deliverable=line('Сдать:'),difficulty=int(cm.group(1)) if cm else None,new_case_question=newcase,
       criteria=rubric,source=f'materials/originals/PZ{n:02}_Instruction.docx',blank=f'materials/originals/Answer_PZ{n:02}.docx',
       summary=f'materials/summaries/PZ_{n:02}_RU.md',status='not_started'))
write(D/'planning/practicals_requirements.json',requirements)
with (D/'planning/practicals_checklist.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f,delimiter=';');w.writerow(['ПЗ','Название','Сложность из 5','Исходные материалы','Повторить','Результат','Новое условие','Критерий 3 балла','Критерий 3 балла','Критерий 2 балла','Критерий 2 балла','Статус'])
    for x in requirements:w.writerow([x['pz'],x['title'],x['difficulty'],x['inputs'],x['repeat'],x['deliverable'],x['new_case_question'],*x['criteria'],'Не начато'])
write(D/'planning/readiness.json',dict(prepared_at=datetime.now(tz).isoformat(),originals=77,lectures=5,practical_instructions=14,
 summaries=19,blank_templates=14,filled_answers=0,tests_executed_for_denis=0,submitted=0,
 source_files_sha256_match=True,all_14_requirements_extracted=True,
 tools=dict(minimum=['Word или LibreOffice Writer','Excel или LibreOffice Calc с фактическим пересчётом','draw.io или Draw'],
 no_required_server=True,no_required_paid_subscription=True),
 important_limits=['Примеры и контрольные числа преподавателя — исходные материалы, не собственный запуск Дениса.',
 'Шаблон учебной модели проверяет OP/количество/статус, но не весь контракт и не многопользовательские права.',
 'Материалы A и B в К09 — прогнозы; собственный вариант должен сравниваться по одним критериям.',
 'Новые условия каждого ПЗ локальны и не переписывают исходный кейс для следующих ПЗ автоматически.',
 'В лекциях и практикуме различаются идентификаторы примеров; приоритет численным условиям К01–К10.',
 'Авторский пример JSON может опускать unit; сверять пример с обязательными полями контракта.',
 'Самостоятельность, разрешение на командную работу и режим агентного эксперимента не подтверждаются автоматически.']))

prompt='''ПОДГОТОВКА ДЕНИСА К КУРСУ 1905
Это пакет исходников и планирования, а не выполненные работы. Сначала открой PREPARATION_RU.html и planning/readiness.json. Прочитай planning/decisions_before_execution.json. Если отдельной команды выполнять работы ещё нет, ограничься чтением и уточнением этих вопросов.

После явной команды выполнить: используй материалы из materials/originals как источник; извлечённый текст и конспекты помогают искать, но рисунки и таблицы сверяй с оригиналом. Рекомендуется учебный кейс К01–К10 и вариант A. Перед заполнением уточни ФИО, группу, d и кто фактически выполняет проверку ПЗ-12. Не наследуй личные параметры Антония и не используй его заполненные работы. Они в пакет не включены.

Каждое ПЗ выполняй по его оригинальной инструкции, бланку, четырём критериям, новому условию и зависимостям из planning/practicals_requirements.json. Примеры преподавателя имеют статус образца; не выдавай их контрольные наблюдения за свой запуск. Не создавай выдуманный сервер, API, замер или успешный пилот. Факты, выводы, предложения, ожидания и наблюдения различай.

ПЗ-12: запиши ожидания до запуска, сохрани неизменный оригинал, используй копию модели и реально пересчитывающий редактор; не заменяй формулы ожидаемыми числами. Выбранный d и режим личной/агентной проверки должны быть явно зафиксированы. Сохрани входы, факты, ошибки и время. ПЗ-13 считай для A и чувствительности до 60 минут на основании К07–К09; это ещё предстоит сделать.

Готовые документы сохраняй в новой папке выполнения Дениса. Схемы и таблицы включай внутрь основного документа. Проверь вёрстку, согласованность кодов, источники, все новые условия и итоговый комплект. Без отдельного разрешения ничего не отправляй в СДО и никому не передавай. Коды доступа и переписка в этот пакет не включены.
'''
(D/'START_NEXT_RUN.txt').write_text(prompt,encoding='utf-8')

cards=[]
for x in requirements:
    cr=''.join('<li>'+html.escape(y)+'</li>' for y in x['criteria'])
    cards.append(f'''<article id="pz{x['pz']:02}"><h3>{html.escape(x['title'])}</h3><p><b>Статус:</b> не начато. <b>Сложность:</b> {x['difficulty']}/5.</p><p><b>Вход:</b> {html.escape(x['inputs'])}</p><p><b>Повторить:</b> {html.escape(x['repeat'])}</p><p><b>Подготовить позже:</b> {html.escape(x['deliverable'])}</p><p>{href(x['source'],'Оригинал инструкции')} · {href(x['blank'],'Пустой бланк')} · {href(x['summary'],'Краткий разбор')} · {href(f"materials/originals/Prompt_PZ{x['pz']:02}.txt",'Запрос преподавателя')}</p><details><summary>Четыре критерия и новое условие</summary><ul>{cr}</ul><p><b>Вопрос для будущего ответа:</b> {html.escape(x['new_case_question'])}</p></details></article>''')
lectures=''.join('<li>'+href(f'materials/originals/Лекция {n}.pdf',f'Лекция {n} PDF')+' — '+href(f'materials/summaries/LECTURE_{n:02}_RU.md','конспект')+'</li>' for n in range(1,6))
files=''.join('<li>'+href(x['local_path'],x['name'])+'</li>' for x in source_manifest)
questions=''.join('<li>'+html.escape(x['question'])+'</li>' for x in decisions)
page=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Денис Подготовка курса 1905</title><style>body{{font:17px/1.6 system-ui,sans-serif;background:#f4f6f5;color:#18312d;margin:0}}main{{max-width:1060px;margin:auto;padding:36px}}h1,h2,h3{{line-height:1.25}}article,.box{{background:white;border:1px solid #cad6d0;border-radius:10px;padding:22px;margin:18px 0}}a{{color:#08605e}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{border:1px solid #c9d5d0;padding:12px;text-align:left}}.tag{{font-weight:700;color:#754500}}summary{{cursor:pointer}}nav a{{margin-right:18px}}@media print{{body{{background:white}}main{{padding:0}}article{{break-inside:avoid}}}}</style><main>
<h1>Денис Подготовка к четырнадцати практическим</h1><p class="tag">Только материалы и планирование · 16 октября 2026 · ответы не выполнялись</p><p>Курс Олега Моторина «Архитектура предприятий и информационных систем», СДО 1905. Пакет можно перенести на другой компьютер. В нём 77 оригинальных вложений преподавателя, полные извлечённые тексты, 5 конспектов лекций, 14 кратких разборов, пустые бланки и требования. Внутри оригиналов есть учебные образцы преподавателя; это не выполненные работы Дениса.</p>
<nav><a href="#variant">Выбор A</a><a href="#questions">До выполнения</a><a href="#lectures">Лекции</a><a href="#works">Все ПЗ</a><a href="#files">77 исходников</a></nav>
<section class="box" id="variant"><h2>Рекомендуемый путь A</h2><p>Один учебный объект К01–К10, контролируемые файлы, шаблон, справочник и регламент. Это рабочий выбор для подготовки. Окончательную архитектуру, таблицы, схемы и ответы предстоит разработать отдельно. A и B допустимы по инструкции; обязательного распределения по фамилиям в материалах нет. C нарушает ограничения, а собственный объект требует достаточных разрешённых исходных данных.</p>
<table><tr><th>Условие К09</th><th>A</th><th>B для сравнения</th></tr><tr><td>Разовые затраты</td><td>24 000 руб.</td><td>90 000 руб.</td></tr><tr><td>Поддержка в месяц</td><td>1 000 руб.</td><td>3 000 руб.</td></tr><tr><td>Прогноз активной подготовки</td><td>40 минут</td><td>20 минут</td></tr><tr><td>Чувствительность в ПЗ-13</td><td>60 минут</td><td>40 минут</td></tr><tr><td>Основной предмет проектирования</td><td>Версии, подтверждение, контрольный шаблон и регламент</td><td>Сервис, права, история и локальная очередь</td></tr></table><p>Это параметры преподавателя, не измерения Дениса. Расчёт эффекта для сдачи ещё не выполнен. Минимальный набор инструментов — Writer/Word, Calc/Excel и Draw/draw.io; отдельный сервер не требуется. Примерная сложность пути A — 3/5, но правила версий и подтверждений придётся обосновать.</p></section>
<section class="box" id="questions"><h2>Что решить перед выполнением</h2><ol>{questions}</ol><p>{href('START_NEXT_RUN.txt','Инструкция для следующего запуска')} · {href('planning/practicals_checklist.csv','Таблица требований CSV')} · {href('planning/practicals_requirements.json','Требования и критерии JSON')} · {href('planning/readiness.json','Состав и ограничения')}</p></section>
<section class="box"><h2>Порядок чтения и продолжения</h2><ol><li>Общая инструкция 00_Start, затем кейс 01_Case или Case_for_AI.</li><li>Лекция 1 → ПЗ-1; лекция 2 → ПЗ-2; лекция 3 → ПЗ-3–5; лекция 4 → ПЗ-6–10; лекция 5 → ПЗ-11–14.</li><li>Для каждого ПЗ открыть оригинал инструкции, бланк и четыре критерия; конспект не заменяет рисунки и условия оригинала.</li><li>До будущего ПЗ-12 проверить доступный редактор и режим личной/агентной проверки; ожидания записать до запуска.</li><li>Новый случай каждого ПЗ разобрать отдельно. Он не изменяет автоматически базовый кейс следующих ПЗ.</li></ol><p>По проверке СДО 16 октября общий отображаемый срок — 22 декабря 2026, 00:00. Перед фактической сдачей заново проверить срок своей группы. Файлы в СДО сдавать по отдельным ПЗ; этот архив служит подготовке.</p></section>
<section id="lectures"><h2>Пять лекций</h2><ul>{lectures}</ul></section><section id="works"><h2>Все четырнадцать заданий</h2>{''.join(cards)}</section>
<section id="files"><h2>Все оригинальные вложения</h2><p>SHA256 каждого оригинала проверен по исходному манифесту. {href('source_manifest.json','Манифест источников и ссылок')}</p><details><summary>Показать все 77 файлов</summary><ul>{files}</ul></details></section>
<p>Заполненные работы Антония, его запуск Excel, личный d и коды записи в курс сюда не включены. Работы Дениса, его фактические наблюдения и отправка в СДО не выполнялись.</p></main></html>'''
(D/'PREPARATION_RU.html').write_text(page,encoding='utf-8')
all_files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='package_verification.json')
verification=dict(status='PASS',files=len(all_files),originals=len(manifest),summaries=19,practical_cards=14,source_hashes_match=True,filled_answers=0,tests_executed_for_denis=0,submitted=0,
 files_manifest=[dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in all_files])
write(D/'package_verification.json',verification)
out=R/'Denis_SDO1905_variant_A_preparation.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for p in D.rglob('*'):
        if p.is_file():assert z.read(p.relative_to(D).as_posix())==p.read_bytes()
    assert not any('run_20261016' in x or '/submission/' in x or 'Сарычев' in x for x in z.namelist())
write(S/'denis_package_receipt.json',dict(file=str(out),bytes=out.stat().st_size,sha256=sha(out),integrity='PASS',files=len(verification['files_manifest'])+1))
print(json.dumps(dict(schedule_slots=[dict(pz=x['pz'],time=x['scheduled_at']) for x in slots],denis_files=len(verification['files_manifest'])+1,source_originals=77,archive_bytes=out.stat().st_size,filled_answers=0,status='PASS'),ensure_ascii=False))

from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile
R=Path(__file__).resolve().parent
vpath=R/'evidence/verification.json';v=json.loads(vpath.read_text(encoding='utf-8'))
assert [x['pages'] for x in v['files']]==[2,2,2]
v.update(status='PASS',visual_review='Просмотрены все шесть страниц после рендера Word/PDFium; после окончательного уточнения вопроса проекта повторно просмотрена изменённая страница ПЗ-1.')
vpath.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.now(timezone.utc)
log=dict(started_at='2026-10-16T09:00:10+00:00',completed_at=now.isoformat(),duration_seconds=round((now-datetime.fromisoformat('2026-10-16T09:00:10+00:00')).total_seconds(),2),
 scope='Первые три ПЗ Дениса на учебном кейсе, направление A; отдельный тестовый комплект',
 files=v['files'],pages=6,source_integrity_count=77,
 corrections=['Первый рендер ПЗ-2/3 дал четыре страницы; убраны избыточные разрывы.','В следующем рендере последние страницы были слабо заполнены; подобраны ширины колонок и убраны повторы без удаления обязательного содержания.','Вопрос проекта ПЗ-1 сформулирован через результат, а не выбранное средство.'],
 calculations_checked=['(75+90+80+70+85)/5=80','15+20+35+10=80'],
 observation_limit='Личные действия и измерения Дениса не заявляются; ПЗ-12 не выполнялось, d не выбирался.',
 antoniy_files_unchanged=True,antoniy_schedule_changed=False,submitted_to_sdo=False)
(R/'evidence/run_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
readme='''ДЕНИС — ТЕСТОВЫЕ ПЗ 1–3 КУРСА 1905
Шестернин Денис, ДЭ 39-26. 16 октября 2026.
Учебный кейс К01–К10. Направление A: контролируемые файлы, шаблон, справочник и регламент.

Состав:
1. PZ01_Шестернин_ДЭ39-26.docx — паспорт объекта, входы/выходы, основания, диагноз, новый случай.
2. PZ02_Шестернин_ДЭ39-26.docx — четыре домена, пять участников, две цепочки, новый случай.
3. PZ03_Шестернин_ДЭ39-26.docx — цели и три функции, показатели, среднее 80 минут, дерево целей и новый случай.
Каждый документ содержит две страницы. Схемы уже вставлены внутрь; редактируемые draw.io находятся в schemes.

Это первые три работы для теста, подготовленные агентом Codex. В ПЗ-1–3 рассматривается общий AS-IS учебного кейса; предложения согласованы с будущим направлением A. Окончательный выбор архитектуры и сравнение A/B относятся к последующим ПЗ.
Личная проверка Денисом, интервью, внедрение и результаты будущих испытаний не заявляются. В СДО эти работы не отправлялись. ПЗ-4–14 здесь не выполнены, d для ПЗ-12 не выбран.
Фамилия, имя и группа взяты из ранее сохранённых учебных материалов. Отчество не подтверждено и не добавлено; при необходимости Денис может дополнить оформление перед учебной сдачей.

Для чтения и редактирования открой DOCX в Word либо LibreOffice Writer. Схемы draw.io необязательны для просмотра документов. Исходные лекции, инструкции и пустые бланки находятся в отдельном ранее подготовленном архиве Denis_SDO1905_variant_A_preparation.zip.
'''
(R/'README_FOR_DENIS.txt').write_text(readme,encoding='utf-8-sig')
out=R.parent/'Denis_SDO1905_A_PZ01-03_test.zip'
paths=[(R/'submission'/x['file'],x['file']) for x in v['files']]
paths.append((R/'README_FOR_DENIS.txt','README_FOR_DENIS.txt'))
paths.extend((p,'schemes/'+p.name) for p in sorted((R/'evidence/diagrams').glob('*.drawio')))
assert len(paths)==7
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p,name in paths:z.write(p,name)
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert len(z.namelist())==7
    for p,name in paths:assert z.read(name)==p.read_bytes()
receipt=dict(file=str(out),entries=7,docx=3,pages=6,bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),integrity='PASS')
(R/'evidence/archive_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(archive=out.name,docx=3,pages=6,entries=7,bytes=receipt['bytes'],seconds=log['duration_seconds'],status='PASS'),ensure_ascii=False))

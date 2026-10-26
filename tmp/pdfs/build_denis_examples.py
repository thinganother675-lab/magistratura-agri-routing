import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/denis_dataset_examples_20261007.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
cases = {c['id']:c for c in json.loads((ROOT/'data/study_c_technical_20261003.json').read_text(encoding='utf-8'))['cases']}
traces = [json.loads(x) for x in (ROOT/'results/20261004_study_c_live/traces.jsonl').read_text(encoding='utf-8').splitlines()]
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial', boldItalic='Arial-Bold')
INK=colors.HexColor('#172D3E'); GREEN=colors.HexColor('#227568'); MUTED=colors.HexColor('#52616C')
S={
 'title':ParagraphStyle('title',fontName='Arial-Bold',fontSize=23,leading=28,textColor=INK,spaceAfter=8),
 'sub':ParagraphStyle('sub',fontName='Arial',fontSize=10.5,leading=14,textColor=MUTED,spaceAfter=10),
 'h':ParagraphStyle('h',fontName='Arial-Bold',fontSize=12,leading=16,textColor=GREEN,spaceAfter=5),
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10.5,leading=13.6,textColor=INK,spaceAfter=4),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=8.6,leading=11,textColor=MUTED,spaceAfter=4),
}
story=[]
def p(t,s='body'): return Paragraph(t,S[s])
def add(t,s='body'): story.append(p(t,s))
def card(title,source,question,inputs,answer,meaning,observed=None):
    parts=[p(title+' <font size="8" color="#52616C">('+escape(source.split('•')[-1].strip())+')</font>','h'),p('<b>Задание:</b> '+escape(question))]
    if inputs: parts.append(p('<b>Дано:</b> '+inputs))
    parts.append(p('<b>Ожидаемый ответ:</b> '+answer))
    parts.append(p('<b>Что проверяем:</b> '+meaning))
    if observed: parts.append(p('<b>В нашем запуске:</b> '+observed,'small'))
    story.append(KeepTogether(parts+[Spacer(1,8)]))
def ccard(n,cid,title,inputs,answer,meaning,observed=None):
    c=cases[cid]
    card(f'{n}. {title}',f'Собственное расчётное задание • {cid}',c['request']['question_ru'],inputs,answer,meaning,observed)
def result(cid,arm):
    r=next(r for r in traces if r['id']==cid and r['model_key']=='qwen3.5-9b' and r['arm']==arm)
    return json.loads(r['final_output'])
assert result('study_c_001','model_only')['numeric']==38
assert result('study_c_001','live_application_tools')['numeric']==8

add('10 примеров: что мы тестировали','title')
add('Денису для показа преподавателю • 7 октября 2026<br/>1 / 3: аграрные знания и простые расчёты','sub')
add('<b>Здесь два разных блока.</b> Примеры 1–2 - короткие цитаты из открытой части MERA ruTXTAgroBench; 3–10 - наши сконструированные задания расчётного эксперимента. Это иллюстрации типов задач, не рейтинг и не случайная выборка для оценки точности.')
card('1. Ботаника: из чего состоит почка','MERA ruTXTAgroBench • открытая часть • ID 0',
     'Из каких структур состоит вегетативная почка?',None,
     'По эталону набора: <b>A, C, D, E</b>.',
     'Знание ботаники и выбор всех правильных вариантов. Пропуск хотя бы одной требуемой буквы делает строгий ответ неверным.')
# Put the source options immediately before the answer in the first two cards.
first=story[-1]._content
first.insert(2,p('A. из конуса нарастания<br/>B. из зачатков цветка<br/>C. из зачаточной пазушной почки<br/>D. из зачатков листьев<br/>E. из почечных чешуй'))
card('2. Ботаника: функции черешка','MERA ruTXTAgroBench • открытая часть • ID 1',
     'Какие из перечисленных функций не относятся к функциям черешка листа?',None,
     'По эталону набора: <b>B, C, D</b>.',
     'Понимание отрицания «не относятся» и нескольких правильных вариантов. Оценивается совпадение с эталоном набора.')
story[-1]._content.insert(2,p('A. ориентация листа по отношению к источнику света<br/>B. отложение питательных веществ<br/>C. закрепление в субстрате<br/>D. половое размножение'))
ccard(3,'study_c_001','Сумма эффективных температур за день',
      'Tmin = 10 °C; Tmax = 26 °C; базовая температура = 10 °C.',
      '<b>8 °C·сут</b>: max(0, (10 + 26) / 2 - 10).',
      'Счёт по явно заданной формуле и правильная единица.',
      '9B без функции выдала 38; с реальным выполнением функции - 8, правильный результат.')
ccard(4,'study_c_003','Сумма тепла за три дня',
      'Tmin: 0, 6, 10 °C; Tmax: 10, 14, 20 °C; база = 5 °C.',
      '<b>15 °C·сут</b>: вклады дней 0 + 5 + 10.',
      'Нужно применить формулу к каждому дню и затем сложить вклады.')
add('Источник примеров 1–2: <link href="https://huggingface.co/datasets/MERA-evaluation/ruTXTAgroBench/viewer/default/train" color="#227568">открытая часть ruTXTAgroBench на Hugging Face</link>. Здесь приведены два коротких примера с атрибуцией; полный сторонний набор не выгружен.','small')

story.append(PageBreak())
add('Расчётные задачи','title')
add('2 / 3: числа, единицы и проверяемые формулы','sub')
ccard(5,'study_c_007','Дефицит давления водяного пара (VPD)',
      'Температура = 20 °C; относительная влажность = 50 %.',
      '<b>1,169140635 кПа</b> (округлено для показа); полный эталон - 1,169140635463723 кПа.',
      'Расчёт по температуре и влажности для одного наблюдения. Это не среднее значение за сутки.',
      '9B без функции: 1,326 кПа, неверно; с функцией: 1,169140635463723 кПа, верно.')
ccard(6,'study_c_011','Эталонная эвапотранспирация (ET0)',
      'T = 16,9 °C; чистая радиация Rn = 13,28 МДж/(м²·сут); поток тепла G = 0 МДж/(м²·сут); ветер u2 = 2,078 м/с на высоте 2 м; es = 1,997 кПа; ea = 1,409 кПа; наклон кривой Δ = 0,122 кПа/°C; психрометрическая постоянная γ = 0,0666 кПа/°C.',
      '<b>Около 3,88 мм/сут</b>; заданный допуск эталона - 0,01 мм/сут.',
      'Подстановка всех параметров в формулу FAO-56. ET0 описывает эталонную поверхность; это ещё не доза полива конкретной культуры.',
      '9B без функции: 4,823791 мм/сут, неверно; с функцией: 3,877117063268325 мм/сут, верно.')
ccard(7,'study_c_013','Разность цели и осадков',
      'Условная цель = 10 мм; осадки = 3 мм.',
      '<b>7 мм</b>: max(0, 10 - 3).',
      'Простая арифметика по условию. Эта условная разность не означает, что нужно внести 7 мм поливной воды.',
      '9B дала правильные 7 мм в обоих режимах. Не любой расчёт требует исправления инструментом.')
add('<b>Как объяснить преподавателю.</b> «Мы проверяли не только знание формулы. Модель должна передать корректные аргументы, программа - выполнить расчёт, а итоговый ответ - содержать правильное число и единицу».')
add('Формулировки заданий взяты из собственного набора. Входы и эталоны проверены по data/study_c_technical_20261003.json; приведённые ответы 9B - по сохранённому запуску от 04.10.2026. Показанные округления предназначены для чтения, не заменяют точности исходной оценки.','small')

story.append(PageBreak())
add('Когда данных недостаточно','title')
add('3 / 3: уточнение, единицы и границы ответа','sub')
ccard(8,'study_c_016','Не задана базовая температура',
      'Tmin = 10 °C; Tmax = 26 °C; базовая температура отсутствует.',
      '<b>Запросить базовую температуру</b>, не выбирать типичную величину самостоятельно.',
      'Умение остановить расчёт при отсутствии обязательного параметра. Численный ответ здесь не требуется.',
      'В сохранённом запуске 9B правильно запросила базу в обоих режимах.')
ccard(9,'study_c_022','Радиация в неподходящих единицах',
      'Те же численные входы, что в примере 6, но единица радиации указана как <b>Вт/м²</b>, вместо МДж/(м²·сут). Значение Rn = 13,28.',
      '<b>Запросить данные в нужных суточных единицах / явное преобразование</b>, прежде чем применять суточную формулу.',
      'Умение обнаружить несовместимость единиц и правильно оформить запрос уточнения по заданному контракту. Простого числа вместо уточнения быть не должно.',
      '9B заметила проблему единиц, но не выполнила строгий контракт ответа в обоих режимах; с инструментами также указала неверный идентификатор функции. Поэтому оба ответа оценены как неверные.')
ccard(10,'study_c_026','Нельзя гарантировать урожай по одной температуре',
      'Температура = 20 °C; культура, поле и остальные условия неизвестны.',
      '<b>Отказаться от гарантии точного урожая</b>: задача не поддерживается имеющимися данными и инструментами.',
      'Способность не выдумывать результат за пределами задачи. Правильный отказ тоже является успешным ответом.',
      '9B правильно отказалась от гарантии в обоих режимах.')
add('<b>Что эти примеры иллюстрируют.</b> Точные функции исправили численные расчёты: в полном опыте обе модели решили 16 из 16 численных заданий. Но правильная арифметика не устраняет ошибки выбора функции и оформления уточнений. Поэтому отдельно оценивали числа, аргументы, единицы и действия при нехватке данных.')
add('Примеры 3–10 взяты из собственного набора из 27 заданий разработки; он не является независимой экспертной проверкой. Общие результаты и статья: <link href="https://github.com/Apartman36/magistratura-agri-routing" color="#227568">репозиторий проекта</link>.','small')

def footer(c,doc):
    c.saveState(); c.setStrokeColor(colors.HexColor('#D8E1E7')); c.line(48,42,A4[0]-48,42)
    c.setFont('Arial',8.5); c.setFillColor(MUTED)
    c.drawString(48,28,'Антоний и Денис • Примеры заданий для обсуждения исследования')
    c.drawRightString(A4[0]-48,28,f'{doc.page} / 3'); c.restoreState()
SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=38,bottomMargin=54,title='10 примеров заданий: аграрные знания и расчётные инструменты',author='Антоний Сарычев, Денис Шестернин').build(story,onFirstPage=footer,onLaterPages=footer)
r=PdfReader(OUT)
assert len(r.pages)==3, f'Expected 3 pages, got {len(r.pages)}'
print(f'{OUT} | {len(r.pages)} pages')

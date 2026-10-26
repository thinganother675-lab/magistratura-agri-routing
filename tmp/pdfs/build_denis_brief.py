from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/denis_research_brief_20261007.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial', boldItalic='Arial-Bold')
INK = colors.HexColor('#172D3E')
ACCENT = colors.HexColor('#227568')
MUTED = colors.HexColor('#52616C')
LIGHT = colors.HexColor('#EDF5F3')
styles = {
 'title': ParagraphStyle('title', fontName='Arial-Bold', fontSize=24, leading=28, textColor=INK, spaceAfter=9),
 'sub': ParagraphStyle('sub', fontName='Arial', fontSize=10.5, leading=14, textColor=MUTED, spaceAfter=8),
 'h': ParagraphStyle('h', fontName='Arial-Bold', fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=7, spaceAfter=4),
 'body': ParagraphStyle('body', fontName='Arial', fontSize=10.6, leading=13.6, textColor=INK, spaceAfter=5),
 'small': ParagraphStyle('small', fontName='Arial', fontSize=9, leading=12, textColor=MUTED, spaceAfter=4),
 'cell': ParagraphStyle('cell', fontName='Arial', fontSize=10.4, leading=13.5, textColor=INK),
 'headcell': ParagraphStyle('headcell', fontName='Arial-Bold', fontSize=10.4, leading=13.5, textColor=colors.white),
 'quote': ParagraphStyle('quote', fontName='Arial', fontSize=10.8, leading=14, textColor=INK, spaceAfter=0),
}
story = []
def p(text, style='body'):
    return Paragraph(text, styles[style])
def add(text, style='body'):
    story.append(p(text, style))
def bullet(text):
    add('• ' + text)
def section(title):
    add(title, 'h')
def box(text):
    t = Table([[p(text, 'quote')]], colWidths=[491])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#CDDFDA')),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story.append(t)
def table(rows, widths):
    cells = [[p(t, 'headcell' if i == 0 else 'cell') for t in row] for i,row in enumerate(rows)]
    t = Table(cells, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F2F5F7'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,-1),(-1,-1),0.5,colors.HexColor('#D8E1E7'))]))
    story.append(t)

add('Денису: суть исследования', 'title')
add('Памятка к разговору с Анастасией Греченевой • 7 октября 2026<br/>Страница 1: что сделали и что получилось', 'sub')
box('<b>Главная мысль.</b> Проверили, насколько небольшая языковая модель на обычном ПК уступает более крупной в аграрных вопросах и помогает ли ей подключение точных расчётных функций. Меньшая модель быстрее и экономнее по памяти; для чисел полезны формулы, но ошибки понимания задачи остаются.')

section('1. Какая проблема и что за проект')
add('Аграрному ИИ-ассистенту нужно и отвечать на вопросы, и считать. Большая модель требует больше ресурсов; связный ответ ещё не гарантирует правильного числа. Мы собрали программный стенд, который запускает модели, проверяет ответы, измеряет время и память и подключает расчётные функции.')
add('<b>Сравнивали:</b> Qwen3.5-9B и Qwen3.8-27B. 9B и 27B означают примерно 9 и 27 млрд параметров. Обе работают локально. ПК: RTX 5060 Ti с 16 ГБ видеопамяти, около 32 ГБ оперативной памяти. Сравнение относится к этим конкретным конфигурациям.')

section('2. На каких данных проверяли знания')
add('<b>ruTXTAgroBench платформы MERA:</b> 2 935 русскоязычных вопросов с выбором ответа по 10 аграрным дисциплинам. По описанию создателей, вопросы подготовлены и проверены экспертами. Мы использовали <b>293 открытых задания</b>; закрытую тестовую часть не запускали.')
table([
 ['На открытой выборке', 'Модель 9B', 'Модель 27B'],
 ['Полностью верный выбор вариантов', '141 из 289<br/>48,79 %', '150 из 289<br/>51,90 %'],
], [247,122,122])
add('Четыре эталона имели неоднозначные обозначения букв, поэтому основной расчёт сделан по 289. Большая модель дала на 9 верных ответов больше: разница <b>3,11 процентного пункта</b>. Проверка строгая: должны совпасть все выбранные варианты.', 'small')

section('3. Отдельно измерили скорость и память')
add('На <b>40 вопросах</b> в отдельном режиме типичное время запроса составило <b>0,269 с у 9B и 1,434 с у 27B</b>: 9B быстрее примерно в <b>5,3 раза</b>. Качество именно здесь: 22/39 и 24/39; один эталон спорный. Пик занятой оперативной памяти всей системы: 20,86 и 28,47 GiB. Это отдельный замер, его настройки отличались от полного прогона.')

section('4. Проверили реальные расчётные функции')
add('<b>27 собственных заданий:</b> 16 численных и 11 на уточнение данных / обработку ограничений. Примеры: сумма эффективных температур, дефицит давления пара, эталонная эвапотранспирация по FAO-56. Сравнили ответ модели самой и работу с функцией: модель передаёт данные, программа проверяет их и считает.')
add('<b>Численные задачи:</b> 9B без функций решила <b>1/16</b>, 27B - <b>6/16</b>; с фактическим выполнением функций обе дали <b>16/16</b>. По всем 27 заданиям: 9B <b>7 → 18</b> верных, 27B <b>15 → 25</b>. Выполнены 32 реальных расчёта. У 9B ошибки уточнения данных сохранились; расчётный режим требует дополнительного обращения к модели.')

story.append(PageBreak())
add('Как рассказать на паре', 'title')
add('Страница 2: готовая речь, вопросы преподавателю и ответы на уточнения', 'sub')
section('Речь примерно на минуту: достаточно сказать это')
box('«Мы провели предварительное исследование локальных языковых моделей для аграрных задач. Сравнили две модели Qwen: на 9 и 27 миллиардов параметров. Взяли 293 открытых вопроса аграрного набора MERA; из 289 оцениваемых меньшая модель ответила правильно на 141, большая - на 150. В отдельном замере на 40 вопросах меньшая отвечала примерно в пять раз быстрее и занимала меньше памяти.<br/><br/>Ещё проверили расчёты по агрометеорологическим формулам. Когда модели считали сами, ошибок было много; с реальным выполнением программных функций обе решили все 16 численных задач. Но при нехватке данных ошибки остались.<br/><br/>Пока вывод такой: небольшая модель интересна по ресурсам, а точные расчёты лучше передавать проверяемым функциям. Хотели бы уточнить, достаточно ли такого эксперимента для статьи, корректна ли методика и какую дополнительную проверку вы бы посоветовали».')

section('Если решите показать статью')
add('«Результаты уже оформлены в <b>рабочий черновик, бета-версию</b>, на русском и английском. Это одна работа. Хотим обсудить с вами данные, методику и выводы, получить замечания и доработать текст».')
add('Можно начать с результатов, а текст показать при обсуждении. Проведённые тесты называем проведёнными; независимую проверку - планируемой.', 'small')

section('Что уточнить у Греченевой')
bullet('<b>Фокус:</b> подходит ли тема локальных моделей, их ресурсов и расчётных инструментов?')
bullet('<b>Данные:</b> достаточно ли открытой выборки MERA или нужен независимый набор и проверка агрономом?')
bullet('<b>Методика:</b> приемлемо ли сравнение разных конфигураций; что исправить в оценке ответов и расчётов?')
bullet('<b>Следующий шаг:</b> какие доработки приоритетны и под какой учебный или публикационный формат готовить текст?')

section('Если спросят подробнее: короткие ответы')
add('<b>«Получилось 94 % точности?»</b> Нет: точность 9B - 48,79 %. 94 % - отношение 141 к 150. Равенство качества не доказано.')
add('<b>«Можно уже рекомендовать полив?»</b> Полевых испытаний не было. Верное число по формуле не подтверждает безопасность совета. Нужна независимая проверка; открытые задания уже использовались при выборе моделей.')
add('<b>«А облако?»</b> В прежнем отдельном опыте на 150 заданиях каскад сократил обращения к облаку со 100 до 20, но дал 133 верных ответа против 139 у режима «инструменты + облако». Критерий сохранения качества не выполнен.')
add('<b>«Почему так быстро?»</b> ИИ помогал с кодом, анализом и текстом; это раскрыто в статье. Авторы должны проверить итоговый текст.')

add('Основа: RU (r2) и EN от 05.10.2026, сохранённые результаты. <link href="https://github.com/Apartman36/magistratura-agri-routing" color="#227568">Проект и статьи на GitHub</link> • <link href="https://mera.a-ai.ru/ru/industrial/tasks/1" color="#227568">Описание набора</link>', 'small')

def footer(c, doc):
    c.saveState()
    c.setStrokeColor(colors.HexColor('#D8E1E7'))
    c.line(52,43,A4[0]-52,43)
    c.setFont('Arial',8.5)
    c.setFillColor(MUTED)
    c.drawString(52,29,'Антоний и Денис • Памятка для обсуждения исследования')
    c.drawRightString(A4[0]-52,29,f'{doc.page} / 2')
    c.restoreState()

doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=52, leftMargin=52, topMargin=41, bottomMargin=56, title='Денису: суть исследования и разговор с преподавателем', author='Антоний Сарычев, Денис Шестернин', pageCompression=1)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)

from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/denis_research_brief_simple_20261007.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial', boldItalic='Arial-Bold')
INK = colors.HexColor('#172D3E')
GREEN = colors.HexColor('#227568')
S = {
    'title': ParagraphStyle('title', fontName='Arial-Bold', fontSize=23, leading=28, textColor=INK, spaceAfter=11),
    'body': ParagraphStyle('body', fontName='Arial', fontSize=12, leading=17, textColor=INK, spaceAfter=8),
    'h': ParagraphStyle('h', fontName='Arial-Bold', fontSize=14, leading=18, textColor=GREEN, spaceBefore=11, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Arial', fontSize=10, leading=14, textColor=colors.HexColor('#52616C'), spaceAfter=5),
}
story = []
def add(text, style='body'):
    story.append(Paragraph(text, S[style]))

add('Что сделали и что получилось', 'title')
add('<b>Цель:</b> проверить, может ли небольшая нейросеть на нашем компьютере отвечать на аграрные вопросы и считать по формулам. Сравнили две модели Qwen: маленькую <b>9B</b> и большую <b>27B</b>. Обе запускали на одном ПК, без облака.')

add('1. Проверили знания', 'h')
add('<b>Как:</b> дали обеим моделям одни и те же <b>293 вопроса</b> из аграрного набора MERA ruTXTAgroBench. Это вопросы с вариантами ответа, например по ботанике и растениеводству. Сравнили выбранные варианты с готовыми правильными ответами.')
add('<b>Результат:</b> маленькая модель ответила верно на <b>141 из 289</b> вопросов, большая - на <b>150 из 289</b>. Это примерно <b>49 % и 52 %</b>. Большая дала на 9 верных ответов больше. Четыре вопроса не вошли в оценку из-за неоднозначных букв в эталоне.')

add('2. Измерили скорость и память', 'h')
add('<b>Как:</b> отдельно запустили обе модели на <b>40 вопросах</b>, засекли время ответов и измерили занятую память компьютера.')
add('<b>Результат:</b> типичное время запроса у маленькой модели - <b>0,27 секунды</b>, у большой - <b>1,43 секунды</b>. Маленькая отвечала примерно <b>в 5 раз быстрее</b>. Пик занятой оперативной памяти всей системы: около <b>21 и 28,5 ГБ</b>. В этом отдельном замере настройки отличались от первого теста.')

add('3. Проверили расчёты', 'h')
add('<b>Как:</b> составили <b>27 заданий</b>: 16 на вычисления и 11 на нехватку данных и другие ограничения. Например, нужно было посчитать сумму температур или испарение по заданной формуле. Сначала модель считала сама. Затем подключили программные функции: модель передаёт им данные, программа считает и возвращает результат.')
add('<b>Результат:</b> без функций маленькая модель верно решила <b>1 из 16</b> численных задач, большая - <b>6 из 16</b>. С функциями обе решили <b>16 из 16</b>. Но ошибки при нехватке данных и выборе функции остались.')

story.append(Spacer(1, 8))
conclusion = Paragraph('<b>Главный вывод:</b> маленькая модель быстрее и занимает меньше памяти, большая немного лучше ответила на вопросы. Расчёты по формулам стали правильными после подключения программных функций. Это ещё не делает систему надёжным агрономом.', S['body'])
box = Table([[conclusion]], colWidths=[499])
box.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF5F3')),
    ('LEFTPADDING', (0,0), (-1,-1), 11), ('RIGHTPADDING', (0,0), (-1,-1), 11),
    ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
]))
story.append(box)
story.append(Spacer(1, 9))
add('Пока это предварительные тесты: открытые вопросы уже использовались при выборе моделей. Проверка на независимом наборе и в реальном хозяйстве ещё не проведена.', 'small')

def footer(c, doc):
    c.saveState()
    c.setStrokeColor(colors.HexColor('#D8E1E7'))
    c.line(48, 39, A4[0]-48, 39)
    c.setFillColor(colors.HexColor('#52616C'))
    c.setFont('Arial', 8.5)
    c.drawString(48, 26, 'Антоний и Денис • Кратко об исследовании • 07.10.2026')
    c.drawRightString(A4[0]-48, 26, '1 / 1')
    c.restoreState()

SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=48, rightMargin=48, topMargin=38, bottomMargin=50,
                  title='Исследование простыми словами: как проводили и что получили',
                  author='Антоний Сарычев, Денис Шестернин').build(story, onFirstPage=footer, onLaterPages=footer)
r = PdfReader(OUT)
assert len(r.pages) == 1, f'Expected one page, got {len(r.pages)}'
print(OUT)

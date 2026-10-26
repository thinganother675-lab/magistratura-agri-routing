import json, html, hashlib, sys
from pathlib import Path

root=Path('C:/sarychev/Codex/magistratura')
sys.path.insert(0,str(root/'src'))
from agro_route.mera_adapter_20261003 import adapt_row
rows={e['row']['meta']['id']:e['row'] for e in json.loads((root/'tmp/mera_examples/rows.json').read_text(encoding='utf-8'))['rows']}
models=['qwen3.5-9b','qwen3.8-27b']
metrics=[{r['item_id']:r for r in map(json.loads,(root/f'results/20261003_local_screen_571682f5/dev293/{m}_metrics.jsonl').read_text(encoding='utf-8').splitlines())} for m in models]
examples=[
    (0,'Обе модели дали полный правильный ответ',[
        'A - точка роста побега', 'B - будущий цветок', 'C - будущая почка в пазухе', 'D - будущая листва', 'E - защитные чешуи почки'],
        'Эталон включает четыре варианта: A, C, D, E. Обе модели выбрали полный набор без лишних вариантов. Этот пример показывает, что в MERA бывает несколько правильных ответов.'),
    (168,'Правильно ответила только модель 27B',[
        'A - совокупностью всех необходимых условий', 'B - только влагой', 'C - влагой и доступным питанием', 'D - газообменом и доступным питанием'],
        'Эталон - A. Модель 27B совпала с эталоном, модель 9B не совпала. Пример показывает различие результатов на вопросе о совокупности условий роста. Причину ошибки по одной оценке установить нельзя.'),
    (187,'Правильно ответила только модель 9B',[
        'A - культура для получения подсолнечного масла', 'B - кукурузная культура, выращиваемая для зерна', 'C - свёкла для сахарного производства', 'D - пшеница с осенним посевом'],
        'Эталон - D, озимая пшеница. Модель 9B совпала с эталоном, модель 27B не совпала. Это пример преимущества небольшой модели на отдельном вопросе, хотя её суммарный результат в нашей выборке ниже.'),
]
cards=[]
for n,(item_id,title,options,comment) in enumerate(examples,1):
    row=rows[item_id]; item=adapt_row(row,'dev')
    m9,m27=[m[item_id] for m in metrics]
    digest=hashlib.sha256(item.prompt.encode('utf-8')).hexdigest()
    assert digest==m9['prompt_sha256']==m27['prompt_sha256']
    assert m9['gold_valid'] and m27['gold_valid']
    result=lambda m:'Правильный полный ответ' if m['strict_set_em']==1 else 'Нет полного совпадения с эталоном'
    cards.append(f'''<section><div class="meta">Пример {n} · ID {item_id} · {html.escape(row['meta']['domain'])}</div>
<h2>{title}</h2><blockquote>{html.escape(row['inputs']['question'])}</blockquote>
<p class="muted">Варианты ниже пересказаны своими словами. Буквы сохранены.</p>
<ul>{''.join('<li>'+html.escape(o)+'</li>' for o in options)}</ul>
<p><strong>Эталон набора: {html.escape(row['outputs'])}.</strong></p>
<table><thead><tr><th>Конфигурация</th><th>Сохранённый результат</th></tr></thead><tbody>
<tr><td>Qwen3.5-9B, Q8_0</td><td>{result(m9)}</td></tr>
<tr><td>Qwen3.8-27B, UD-Q4_K_M</td><td>{result(m27)}</td></tr></tbody></table>
<p>{comment}</p></section>''')
source='https://huggingface.co/datasets/MERA-evaluation/ruTXTAgroBench'
document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Три примера MERA из нашей статьи</title><style>
body{font:17px/1.6 Georgia,serif;background:#f4f6f3;color:#20302a;margin:0}main{max-width:880px;margin:35px auto;padding:0 22px}h1{font-size:31px;line-height:1.25}h2{font-size:23px;line-height:1.3}section{background:white;padding:25px;margin:24px 0;border:1px solid #d8dfd6;border-radius:10px}blockquote{margin:20px 0;padding:12px 18px;border-left:4px solid #45745b;background:#eef4ee;font-size:20px}.meta,.muted{font:14px/1.5 Arial,sans-serif;color:#58665e}table{border-collapse:collapse;width:100%;font:15px/1.5 Arial,sans-serif}th,td{border:1px solid #d8dfd6;padding:10px;text-align:left}th{background:#eef4ee}a{color:#285d48}code{overflow-wrap:anywhere;font-size:13px}@media print{body{background:white}main{margin:0;max-width:none}section{break-inside:avoid}h1{font-size:26px}}
</style><main><h1>Три показательных примера из MERA</h1>
<p>Подборка для обсуждения статьи Антония Сарычева и Дениса Шестернина. Подготовлена 14 октября 2026 года.</p>
<p>Использован аграрный набор ruTXTAgroBench платформы MERA. Это чужой набор данных, применённый в нашем исследовании. Выбраны три разных результата, а не три самых трудных вопроса.</p>
'''+''.join(cards)+f'''
<section><h2>Как объяснить эти примеры</h2><p>Оценка требует полного совпадения выбранных букв с эталоном. В общей выборке с однозначно разобранными эталонами 9B дала 141 правильный ответ из 289, 27B - 150 из 289. Эти три вопроса выбраны для иллюстрации и не заменяют общую оценку.</p>
<p>Вопросы MERA проверяют предметные знания. Эксперимент с расчётными функциями в статье проводился на отдельном наборе из 27 заданий. Эти примеры не являются доказательством эффекта расчётных инструментов.</p>
<p>Буквы эталона приведены по набору; отдельную агрономическую экспертизу этих вопросов мы не проводили. Для ошибочных ответов показана сохранённая оценка: точные выбранные моделью буквы не восстановлены, поскольку исходные ответы в доступной локальной копии отсутствуют.</p></section>
<section><h2>Источники и проверка</h2><p><a href="{source}">Официальный набор ruTXTAgroBench</a>. Тексты вопросов восстановлены из открытой выборки. Для каждого из трёх примеров контрольная сумма сформированного запроса совпала с обеими сохранёнными сериями от 3 октября 2026 года. Таким образом, вопросы соответствуют использованным в эксперименте.</p>
<p class="muted">Результаты: results/20261003_local_screen_571682f5/dev293/qwen3.5-9b_metrics.jsonl и qwen3.8-27b_metrics.jsonl. Использован показатель strict_set_em. Формулировки вопросов сохранены; варианты пересказаны для пояснения. Подборка предназначена для личного обсуждения работы.</p></section></main></html>'''
out=root/'outputs/mera_examples_20261014'; out.mkdir(parents=True,exist_ok=True)
p=out/'MERA_top3_examples_RU.html'; p.write_text(document,encoding='utf-8')
assert document.count('<blockquote>')==3
assert '\u2014' not in document and '\u2013' not in document
print(str(p))

"""Render living Russian research documents from immutable final analysis."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = '20260930T182756Z_6703e43b'
analysis = json.loads((ROOT/'results'/RUN/'analysis.json').read_text())
rows = analysis['summary']
table = '\n'.join(f"| {r['method']} | {round(r['quality']*r['n'])}/{r['n']} ({r['quality']*100:.1f}%) | {r['quality_ci95'][0]*100:.1f}–{r['quality_ci95'][1]*100:.1f}% | {round(r['cloud_call_rate']*r['n'])} | {r['latency_mean_ms']/1000:.3f} / {r['latency_p50_ms']/1000:.3f} / {r['latency_p95_ms']/1000:.3f} | {r['cost_total_usd']:.8f}{' + unknown' if r['unknown_cost_requests'] else ''} | {round(r['critical_error_rate']*r['n'])} |" for r in rows)

results = f'''# Результаты выполненного эксперимента

Дата: 30.09.2026. Основной test — **{RUN}**, 90 пар ответов Qwen3.5-2B GGUF Q4_K_M и **mercury-2.5**. Корпус содержит 360 запросов; реальные model calls выполнены на 36 + 36 dev и 90 test. Train 180 не прогонялся, обученного router нет. Протокол зафиксирован в 18:27:25 UTC, test начат в 18:27:56 UTC. Dataset SHA-256: `03ce1fd188fbd46d2a69fed37ac0f773be3008a814b93c6d646ed8c6aa30e3ca`.

**Основной вывод:** каскад сократил обращения к облаку при сохранении измеряемого качества относительно tools+cloud. Локальная ступень добавила экономию вызовов, но увеличила задержку. Это ограниченный результат для данного корпуса и моделей, а не проверка готовых агрономических рекомендаций.

## Итоговая таблица

Quality — правильность завершения задачи, включая ASK_FOR_DATA. Latency — реконструкция выбранных стадий из реально измеренных HTTP вызовов и времени gate; отдельный live performance run каждой политики не выполнялся.

| Метод | Правильно | 95% group bootstrap CI | Cloud calls из 90 | Mean / p50 / p95, секунды | Известная cloud USD за 90 | Critical errors |
|---|---:|---:|---:|---:|---:|---:|
{table}

12 запросов выполнены численными инструментами, ещё 12 завершены проверкой входов и уточнением. Это 26.7 процентного пункта снятых облачных обращений. Cascade принял 12 локальных QA ответов, из них 10 правильны по strict exact match. **40% запросов обходятся без облака, но сама локальная модель обслуживает 13.3%**, остальные обслуживают инструменты и проверки.

Cascade в среднем медленнее cloud-only в 2.11 раза и tools+cloud в 2.90 раза. Гипотеза об ускорении на этом CPU не поддержана. Rule экономит больше cloud calls, но теряет 21.1 п.п. качества относительно cloud. Выбор метода зависит от допустимого качества, задержки и облачного бюджета.

![Качество, облачные вызовы и задержка](../results/{RUN}/quality_calls_latency.png)

Главная фигура сравнивает quality, cloud calls и latency для всех методов. Дополнительная `quality_cost_latency.png` исключает из cost scatter методы с неизвестной полной стоимостью: неполный bill не показан как точный. Условные cost ranges приведены ниже; это planning assumptions, не доверительные интервалы.

## Гипотезы и парное сравнение

Cascade − cloud: **+6.67 п.п.**, paired cluster bootstrap 95% CI **+1.11…+14.29 п.п.**, 6 wins / 0 losses. Tools+cloud имеет тот же correctness vector. McNemar exact p=.03125 описателен: синтетические варианты зависимы, multiple comparisons не скорректированы. Вывод основывается на групповой оценке и ограниченном scope.

Cascade − tools+cloud: quality difference 0, CI [0,0] на данной cached matrix. Дополнительное сокращение cloud calls **13.33 п.п.**, CI **6.67…22.23 п.п.**; это 12/66 ≈18.2% от обращений tools+cloud. Нулевая разность не означает гарантированную эквивалентность на новых данных.

Все frozen utility checks выполнены: lower quality CI ≥−.05, cloud reduction 40% ≥ pilot-derived target 16.7%, upper critical-error difference 0 ≤0. H1 об инструментах поддержана. H2 о дополнительном вкладе local reader поддержана **на этом test**, хотя в обоих пилотах такой вклад отсутствовал. H3 демонстрирует частичное обслуживание и отказ при offline, а не сохранение полного качества.

Gold-informed local/cloud oracle без tools: 73/90=81.1%. Он ниже tool-aware 76/90, поскольку доступные исполнители различаются. Это диагностическая граница для пары LLM, не executable router и не upper bound инструментальной системы.

## По категориям

| Категория | n | Local | Cloud | Rule | Cascade / tools+cloud | Offline |
|---|---:|---:|---:|---:|---:|---:|
| Extractive AgXQA | 30 | 10/30 | 17/30 | 14/30 | 17/30 | 10/30 |
| Numeric | 12 | 0/12 | 11/12 | 12/12 | 12/12 | 12/12 |
| Missing data / units | 12 | 8/12 | 7/12 | 12/12 | 12/12 | 12/12 |
| Tool selection | 12 | 0/12 | 12/12 | 0/12 | 12/12 | 0/12 |
| Supplied risk rule | 12 | 5/12 | 12/12 | 5/12 | 12/12 | 0/12 |
| Compound criterion | 12 | 8/12 | 11/12 | 8/12 | 11/12 | 0/12 |

QA token F1: local .4490, cloud/cascade/tools+cloud .8269, rule .6671, offline .3639. Это не factuality или hallucination rate. Offline ANSWER coverage 24/90=26.7%; 34 правильных завершения дополнительно включают 12 уточнений. Зафиксированы 54 ABSTAIN и 2 неправильных по EM ответа среди 24 ANSWER, selective error 8.33%.

RU 20 / EN 70: local 35.0% / 34.3%, cloud 85.0% / 75.7%, cascade 95.0% / 81.4%, offline 40.0% / 37.1%. **Это не языковой эффект:** все QA английские, controlled families и task mix различаются. Парные переводы не проводились.

## Наблюдаемые ошибки и ограничение QA метрики

- `controlled_numeric_10_2`: cloud ET₀=8.14 вместо gold 4.6900511234 mm/day. Единица правильна, число ошибочно. Executor считает правильно.
- `controlled_missing_data_9_0` и `controlled_missing_data_10_2`: cloud выдаёт ANSWER при неподдержанных единицах или пропущенном входе. Gate выдаёт ASK_FOR_DATA.
- Cloud: 3 structured parse failures и 1 HTTP 503. Local: 1 parse failure. У 503 нет usage, повтор не выполнялся. Все failures входят в quality denominator.
- `agxqa_336`: local «The IrrigateCost app», cloud «IrrigateCost app», reference «use of the IrrigateCost app». Strict EM штрафует оба, хотя содержание выглядит верным.
- `agxqa_564`: local «56 hertz» опускает исходные 60 hertz и расчёт из reference. Cloud возвращает «60 hertz». Ошибки EM различаются по смыслу.

Prompt просит shortest span, а некоторые gold spans включают дополнительные слова. Это дефект первого QA setup, раскрытый после test; критерий и gold **не исправлялись задним числом**. Следующая версия требует согласованной granularity и независимой предметной проверки. Два local answers прошли substring gate, но не EM; считать их доказанными галлюцинациями нельзя. Substring support не проверяет релевантность вопросу.

`failure_audit.json` содержит фактические случаи и MAE по каждому инструменту. Общий `numeric_mae_when_present` в primary analysis смешивает разные единицы, поэтому физического смысла не имеет и в выводах не используется. Просмотр примеров выполнил автор стенда; независимого agronomist review и inter-annotator agreement нет.

## Стоимость

[Цена Inception на 30.09.2026](https://docs.inceptionlabs.ai/get-started/models): Mercury 2.5 promotion $.04 input / $.15 output за 1M, regular $.20 / $.75. Cache discount не применён. Test usage: 52 736 input + 14 952 output известных tokens. Один HTTP 503 без usage; provider invoice не получен. Поэтому primary total cost per 1000 для cloud/cascade/tools+cloud = null.

| Метод | Known cost /1000 USD | Условный planning range /1000 USD |
|---|---:|---:|
| Cloud | .048358 | .048358–.050106 |
| Cascade | .027661 | .027661–.029409 |
| Tools+cloud | .032705 | .032705–.034452 |
| Rule | .007911 | .007911 |

Верхняя planning граница предполагает byte-based input allowance +256 framing и 512 output tokens для неизвестного вызова. Это не гарантированный bill bound. Один и тот же cached unknown-cost вызов выбран всеми тремя методами, поэтому абсолютная разность известна: cloud − cascade **$.00186275 за 90**, tools+cloud − cascade **$.00045392**. Экономия по известной usage части 42.8% /15.4%; проценты полного bill UNVERIFIED. Local CPU, энергия и амортизация не монетизированы.

Известная token-cost estimate фактически исполненных two pilots + final + live + browser RU query: **$.01272216**, плюс unknown 503. Нельзя суммировать виртуальные policy costs как реальные расходы: все replay методы используют одни cached responses.

## Пилоты и оборудование

| Run | Выборка / модели | Local / cloud / cascade / tools+cloud |
|---|---|---|
| 20260930T174937Z_6bd7b353 | dev36 v0.1, Qwen0.8B / Mercury2 | 11.1% /47.2% /75.0% /75.0% |
| 20260930T181919Z_b3271efb | dev36 v0.2, Qwen2B / Mercury2.5 | 27.8% /86.1% /94.4% /94.4% |

Pilot1 содержал tool-selection hint, его результаты не объединяются с v0.2. Pilot2 analysis использует rule900 до freeze; dev grid выбрала 400, test использует именно 400. Пары моделей менялись совместно: разность пилотов не изолирует эффект размера local model. Подробнее PILOT_CHANGELOG_RU.md.

Ноутбук: 7.73 GiB RAM, 8 logical CPU, 4 inference threads, Windows build26200, Python3.12.14, context4096, seed42, temperature0, max512, local reasoning off / cloud instant. GPU/VRAM UNKNOWN. GGUF 2B: 1 280 835 840 bytes, SHA `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`, upstream LFS verified; llama.cpp b11292. Cloud alias не фиксирует неизменяемые weights. Отдельный пользовательский PC RTX5060Ti16GB / RAM32GB / Ryzen7 8700 **NOT RUN**.

## Проверка MVP

Unit/failure tests: **24 passed**. Live smoke: **13/13**, `results/live_20260930T184104Z`, 10 queries и 3 invalid-payload checks. NASA Moscow Oblast GDD=9.52 °C·day; missing ET0 ASK; F units rejected; direct local Wheat; RU cascade Пшеница; offline ABSTAIN без cloud.

Браузерная форма проверена, console warnings/errors 0. Screenshot: docs/assets/mvp_cloud.jpg. Дополнительный RU запрос: local1809.7ms + cloud993.4ms, total2805.3ms, cloud estimate $.00003361. Это функциональный пример, не performance CI.

## Научные пределы

Test90 /45groups, из них15 controlled families; общие шаблоны и непроверенный document-level overlap. Local2B CPU слаб, Mercury instant не frontier comparison. Strict span metric, supplied context без retrieval, replay latency, prompt cache, promotion price и неизвестный bill одного вызова. Не измерены калибровка, урожайность, полив, поведение агрономов или безопасность реальных рекомендаций. Вывод относится к фиксированной матрице этого протокола. Для усиления нужны expert review, сильный local на PC, новый semantic/document holdout и live performance runs.
'''

outline = '''# Основа первой статьи

**Название:** «Инструментально-ориентированная маршрутизация локальных и облачных языковых моделей для агрометеорологических расчётов и сельскохозяйственных вопросов».

**English:** “Tool-Aware Routing of Local and Cloud Language Models for Agrometeorological Calculations and Agricultural Question Answering”.

Авторы: Антоний и Денис. Полные ФИО, affiliation, email, supervisor и УДК заполнить по подтверждённым данным. Анастасия не считается автоматически научным руководителем. Это outline, не submission-ready Word manuscript.

## Черновик аннотации

Исследовано влияние выбора языковой модели и детерминированного исполнителя на качество обработки текстовых сельскохозяйственных задач. Разработан воспроизводимый стенд с расчётами GDD, VPD, ET₀, дефицита осадков и проверками достаточности входов. На тестовой выборке 90 запросов сравнивались Qwen3.5-2B Q4_K_M, Mercury 2.5 и четыре политики. Каскад достиг 84.4% правильных завершений при 60% облачных вызовов, прямой облачный ответ — 77.8% при 100%. Инструменты с облаком обеспечили то же качество при 73.3% вызовов. Локальная ступень снизила число вызовов, но увеличила реконструированную среднюю задержку с 1.56 до 3.30 с. Выводы ограничены малой контролируемой выборкой, форматными ошибками и строгой метрикой извлечения ответа.

Ключевые слова: языковые модели; маршрутизация; агрометеорология; локальный инференс; облачный инференс; детерминированные инструменты; оценка качества; отказ от ответа.

## Структура 3–5 страниц

| Часть | Содержание | Объём |
|---|---|---|
| RU/EN front matter | Авторы, abstract, keywords | .7page |
| Введение | На каких данных сравнивать модели; зачем tools и clarification | .6page |
| Related work | RouteLLM/cascades, AgXQA/AgroTools; границы новизны | .4page |
| Методы | Corpus360/test90, grouped split, 6 категорий и методов, абляция | 1page |
| Результаты | Quality CI, calls, latency, incomplete cost, ошибки метрики | 1page |
| Выводы | Сокращение вызовов, отсутствие ускорения, следующий эксперимент | .3page |
| References | ≤10 первичных источников | .5page |

В таблице оставить local/cloud/cascade/tools+cloud/offline; rule вынести в supplementary artifacts. Уточнение и расчёты показать отдельно. Footnote о reconstructed latency и unknown cost обязателен. Проценты task-quality не означают безопасность рекомендаций.

Таблица1: correct/90, 95% group CI, cloud calls, mean/p95 latency, known cost +unknown. Рисунок1: архитектура либо quality/call-rate и latency, чтобы unknown bill не исчезал из cost scatter. JPG соответствует письму конференции; SVG/PNG сохранены для редактирования.

## Приоритетные ссылки

Это список источников для будущих ГОСТ записей; авторов, том, страницы и библиографические поля сверить с metadata перед подачей.

1. [RouteLLM, ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html).
2. [FrugalGPT](https://arxiv.org/abs/2305.05176).
3. [Cluster, Route, Escalate2026](https://arxiv.org/html/2606.27457v1).
4. [AgXQA, DOI10.1016/j.compag.2024.109349](https://doi.org/10.1016/j.compag.2024.109349).
5. [AgroTools2026](https://arxiv.org/abs/2605.22366).
6. [FAO-56, chapter4](https://www.fao.org/4/x0490e/x0490e08.htm).
7. [Qwen3.5-2B card](https://huggingface.co/Qwen/Qwen3.5-2B).
8. [NASA POWER API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).
9. [Inception models/prices](https://docs.inceptionlabs.ai/get-started/models).

Полный обзор не умещать в ≤10 refs. Соответствие ICLR формальному A*/A пункту конкурса сверить. Права на публикацию исходных paragraphs проверить до открытого data release.

## Усиление перед подачей

Текущий test сохранить как foundation. На PC выбрать модель по dev, согласовать scope/gold и granularity QA, создать новый независимый semantic/document holdout. Затем live latency trials и fixed frontier API при доступе. Новые результаты не объединять с текущими без контроля моделей, prompt, данных и оборудования. План по двум студентам и курсовым — ROADMAP_RU.md.
'''

onepager = '''# Предложение первой исследовательской статьи

**Антоний и Денис**, первый курс магистратуры РГАУ-МСХА имени К.А. Тимирязева. 30.09.2026. Научный руководитель пока не подтверждён.

**Название:** «Инструментально-ориентированная маршрутизация локальных и облачных языковых моделей для агрометеорологических расчётов и сельскохозяйственных вопросов».

**Проблема.** При ограниченной связи часть запросов нужно обслуживать на доступном компьютере. Для сравнения нужны конкретные данные и эталоны. Общий выигрыш гибрида может объясняться только численными инструментами, поэтому вклад local reader следует оценивать отдельно.

**Объект:** обработка текстовых сельскохозяйственных запросов. **Предмет:** влияние выбора исполнителя и проверки локального ответа на правильность, задержку, облачные вызовы и стоимость. **Цель:** определить границы полезности домашнего гибридного стенда на открытых данных.

**Гипотеза:** инструменты и локальная модель сокращают облачные вызовы при заранее заданном допуске task-quality. Вклад local LLM должен сохраняться относительно tools+cloud. Допуск пилотный; для подтверждающего исследования нужно предметное согласование.

**Задачи:** определить категории; подготовить grouped benchmark и numerical gold; реализовать baselines/gate/cascade; выполнить paired tests и offline; разложить эффект tools/local/cloud; подготовить статью.

**Данные:** 120 paragraphs AgXQA PartB и 240 controlled RU/EN scenarios, train/dev/test180/90/90. Шесть категорий: extractive QA, расчёты, missing inputs/units, tool selection, заданное risk rule, compound criterion. NASA POWER для Московской области — отдельное demo; crop thresholds не выдумываются.

**Стенд:** Qwen3.5-0.8B/2B Q4_K_M на CPU ноутбука, Mercury2/2.5 API. Local/cloud/rule/cascade/tools+cloud/offline; Python GDD/VPD/FAO-56 ET₀/rain deficit, web UI, raw cache, version hashes. Отдельный PC16GBVRAM пока не использован.

**Метрики:** exact/numeric correctness, QA F1, group bootstrap CI, paired differences, critical wrong-ANSWER proxy, cloud calls, mean/p50/p95 latency, token-based cost, coverage/abstention. Confidence calibration пока нет.

**Уже получено:** test90, Qwen2B/Mercury2.5: local 34.4%, cloud 77.8%, cascade 84.4%, tools+cloud 84.4%. Cloud calls 54/90 против 90/90 и 66/90. Local stage снимает ещё 12 вызовов, но mean reconstructed latency 3.30s против 1.56s cloud. Tests 24 passed; live 13/13. Known cloud cost test $.00435224; один 503 без usage. Offline 37.8% правильных завершений и 54 отказа.

**Вклад:** воспроизводимое разделение эффектов tools/local/cloud на узких задачах. Общая routing идея не объявляется новой. Ограничения: слабая CPU модель, synthetic templates, EN QA, неоднозначность reference granularity, replay latency. Независимого agronomist review нет.

**Для первой статьи:** согласовать предметные границы и QA acceptance, проверить сильную модель на PC, создать новый holdout; затем 3–5 страниц, таблица и рисунок. Возможность РГАУ: 18.12 конференция, 11.12 заявка, 29.12 статья; master eligibility нужно подтвердить.

**Для ВКР:** Антоний — resource/cost-aware routing и calibration; Денис — source-grounded Russian benchmark и экспертная оценка. Общий стенд, разные исследовательские вопросы. Темы и связь с GIS/ML/data coursework согласовать с руководителем.
'''

# The instructor's later requirements supersede the original short-collection outline.
outline = '''# Актуальная структура экспериментальной статьи

Обновлено 30.09.2026. Основной план: [RESEARCH_ARTICLE_PLAN_RU.md](RESEARCH_ARTICLE_PLAN_RU.md). Отдельный обзор: [REVIEW_ARTICLE_PLAN_RU.md](REVIEW_ARTICLE_PLAN_RU.md).

**Краткое название:** «Маршрутизация моделей и инструментов для аграрных задач».

**Формат преподавателя:** 6–8 страниц; УДК; аннотация200–300 знаков; проблема, методика и эксперимент; результаты и выводы; минимум15 научных источников. Для AI приоритет последних трёх лет. Wikipedia/GitHub не входят в научные ссылки; repositories и API/model docs остаются в техническом реестре.

**Аннотация — 246 знаков с пробелами:**

> На 90 аграрных запросах сравниваются локальная и облачная модели, каскад и расчётные инструменты. Каскад сократил облачные вызовы на 40% при правильности 84,4%, но увеличил задержку. Вклад локальной модели оценён отдельно от эффекта инструментов.

| Раздел | Страницы |
|---|---:|
| УДК, краткий title, аннотация, авторские сведения | .35 |
| Введение | .75 |
| Краткие связанные научные работы | .65 |
| Материалы и методы | 1.75 |
| Результаты | 1.25 |
| Обсуждение и ограничения | .8 |
| Выводы | .35 |
| Научная библиография, минимум15, цель18–22 | 1.5 |
| **Итого** | **7.4** |

Узкий вопрос: дополнительный вклад local reader относительно tools+cloud. Использовать одну основную пару моделей и protocol; pilots не объединять с test. Не обещать latency gain, calibrated router или готовые агрономические рекомендации. Точный УДК подобрать с библиографом; код из образца чужой аграрной статьи не копировать.

Обзор15–20 страниц с≥50 научными источниками имеет собственные цель, таксономию и выводы. Его длинный related work не переносить в экспериментальную статью.

Прежний outline3–5 страниц с≤10 refs соответствовал отдельному декабрьскому сборнику. Он не удовлетворяет новым требованиям преподавателя и больше не является основным планом. Правила сборника сохранены в RGAU_PUBLICATION_OPPORTUNITIES_2026_RU.md; короткую версию и возможность отдельной публикации согласовать без автоматической двойной отправки.
'''
onepager = onepager.replace('«Инструментально-ориентированная маршрутизация локальных и облачных языковых моделей для агрометеорологических расчётов и сельскохозяйственных вопросов»', '«Маршрутизация моделей и инструментов для аграрных задач»')
onepager = onepager.replace('затем 3–5 страниц, таблица и рисунок.', 'затем 6–8 страниц, УДК, аннотация 200–300 знаков и минимум 15 научных ссылок.')
onepager += '\n**Отдельная обзорная публикация:** 15–20 страниц, минимум 50 научных источников; таксономия и систематизация методов. GitHub используется только для ПО, Wikipedia/GitHub не входят в научную библиографию. Учебные форматы и короткий декабрьский сборник — разные требования; планы находятся в REVIEW_ARTICLE_PLAN_RU.md и RESEARCH_ARTICLE_PLAN_RU.md.\n'

for name, content in [('RESULTS_RU.md', results), ('PAPER_OUTLINE_RU.md', outline), ('SUPERVISOR_ONE_PAGER_RU.md', onepager)]:
    (ROOT/'docs'/name).write_text(content, encoding='utf-8')
print('Rendered three Russian research documents from '+RUN)

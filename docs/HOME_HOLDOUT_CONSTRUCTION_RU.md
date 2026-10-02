# Новый HOME holdout150: построение до финального прогона

**Статус на момент построения: READY, FINAL EXPERIMENT NOT RUN.** Настройки модели и маршрутизатора были окончательно выбраны родительским агентом до создания этого набора; объявленное время остановки тюнинга — 1 октября 2026, 20:11:00 UTC. Сборщик не вызывает модели, не использует ответы текущего/будущего финального прогона и не меняет исторические данные. Параметры протокола и его freeze-файл фиксирует основной агент отдельно.

Созданы `data/home_holdout_20261001.jsonl` и реестр `data/home_holdout_20261001_sources.json`. Всего 150 новых запросов, 75 EN и 75 RU; split=`home_final`, IDs=`home_final_20261001_0001`…`0150`. Генерация чисел воспроизводима: seed=20261001, фиксированная перестановка seed=20261002. Сборщик `scripts/build_home_holdout.py` использует exclusive-create и отказывается перезаписывать существующие итоговые файлы.

| Категория | Всего | EN | RU | Разметка |
|---|---:|---:|---:|---|
| Supplied-context agricultural QA | 40 | 20 | 20 | 20 фактов × EN/RU; короткий точный span |
| Numerical GDD/VPD/ET0/rain deficit | 30 | 15 | 15 | Независимые Decimal эталоны, явные единицы |
| Missing input / malformed units | 20 | 10 | 10 | ASK_FOR_DATA, 10 дефектов × два языка |
| Tool selection | 20 | 10 | 10 | По 5 gdd/vpd/et0/rain_deficit |
| Rule application | 20 | 10 | 10 | 10 RISK / 10 NO_RISK, включая равенство |
| Compound reasoning | 20 | 10 | 10 | 10 ALERT / 10 OK, включая равенство |
| **Всего** | **150** | **75** | **75** | |

QA — новые авторские вопросы и короткие перефразированные контексты по проверенным первичным фактам. Это не копия AgXQA и не реальные запросы фермеров. Все 110 остальных случаев явно помечены `provenance_kind=synthetic`; fictional water targets и правила не являются агрономическими рекомендациями. QA помечены `source_paraphrase`, переводы — AI-assisted, `human_validation=PENDING`. Экспертная/ручная проверка Антоном и Денисом ещё не состоялась; агентская самопроверка не считается независимой человеческой валидацией.

QA содержит **пять независимых документов**, семь официальных страниц. Три главы одного FAO-56 handbook образуют один document group, а не три независимые группы:

| Документ / первичный источник | Фактов | EN/RU строк | Проверенные разделы |
|---|---:|---:|---|
| [FAO-56: introduction](https://www.fao.org/4/x0490e/x0490e04.htm), [reference surface](https://www.fao.org/4/x0490e/x0490e06.htm), [meteorological data](https://www.fao.org/4/x0490e/x0490e07.htm) | 6 | 12 | Transpiration; reference grass; wind profile; saturation vapour pressure |
| [FAO Irrigation Water Management, Salty Soils](https://www.fao.org/4/r4082e/r4082e08.htm) | 4 | 8 | Salinization, leaching, subsurface drainage |
| [USDA NRCS Soil Health on Cropland](https://www.nrcs.usda.gov/conservation-basics/soil/soil-health/soil-health-on-cropland) | 4 | 8 | Soil cover, living roots, biodiversity, rhizosphere |
| [UMN Extension, cover-crop species, 2022](https://blog-crop-news.extension.umn.edu/2022/09/maximize-your-cover-crop-benefits-by.html) | 4 | 8 | Legumes, grass roots, oats and cereal rye in Minnesota |
| [UMN Extension, nitrogen credits, 2019](https://blog-nwcrops.extension.umn.edu/2019/04/cover-crops-and-nitrogen-credits.html) | 2 | 4 | Soybean residue C:N and legume residues |

Каждая из семи страниц дополнительно получена по HTTP 200. Реестр содержит дату получения, SHA256 исходного HTTP content, publisher, URL, раздел и права источника. Целые статьи не сохранялись и не публиковались. FAO и университетские права не объявлены CC0; у UMN species page зафиксирован опубликованный CC BY-SA4.0. Новые синтетические сценарии имеют собственную отметку CC0. Короткие перефразировки сохраняют атрибуцию первичного источника.

Числовые gold вычислены отдельными выражениями `Decimal` с точностью 45 знаков **до** проверки текущим executor. GDD — сумма положительной разности среднего Tmin/Tmax и заданной базы, без верхнего температурного clipping; это заданная benchmark convention, а не универсальная crop-specific GDD. Определение накопленного тепла проверено по [University of Maryland Extension](https://extension.umd.edu/resource/understanding-degree-days). VPD использует приближение по одной температуре и RH; суточное среднее VPD не реконструируется. ET0 следует FAO-56 Eq6, давлению насыщения Eq11 и наклону Eq13. Для синтетических ET0 `es` получено из среднего saturation(Tmin)/saturation(Tmax), `delta` из средней температуры, `gamma` из правдоподобного давления; дневные Rn/G, ветер на2м и давления переданы явно. Rain deficit — `max(0,target-sum(rain))` с fictional target.

После создания независимого gold все 30 числовых примеров сверены с неизменным `agro_route.tools.execute`; максимальная абсолютная разница ниже 1e-10, существенно меньше установленного допуска scorer. Все 20 malformed/missing случаев действительно отклоняются executor. Условия compound вычислены независимо; границы strict `>` и `<` включают отрицательные примеры при равенстве. Rule labels также получены явным сравнением, без языковой модели.

Неизменный scorer проверяет action, exact label, span EM/F1 либо numeric с 1% relative / 0.02 absolute tolerance и точной единицей. Это операционная корректность по заданному запросу. В частности, span EM чувствителен к русским словоформам, даже если свободный ответ семантически приемлем; human audit должен отдельно показывать такие случаи, без исправления gold после просмотра результатов.

Фактическая совместимость с публичным `hard_gate` проверена только по `public_request`: 30 DETERMINISTIC_TOOL, 20 ASK_FOR_DATA и 100 без hard gate. Gold, category, group и split отсутствуют в API request. Это не обещание итогового local/cloud маршрута: оставшиеся 100 решений определяет замороженная политика по выходам моделей. Tool-selection-only не превращается в выполнение расчёта.

Проверка новизны включает весь `data/benchmark.jsonl`, историческую версию `data/versions/benchmark_v0.1.jsonl`, двуязычный DEV probe и все исходные AgXQA annotations: 1302 строки с учётом повторений версий. Хеши проверенных файлов записаны в реестре. Exact overlap по нормализованным question+context+inputs равен 0; IDs также не повторяются. Max token-set Jaccard с историческими запросами: **0.5484** по объединённым полям и **0.5000** только по question. При заранее указанной границе 0.8 near-duplicate count равен 0 для обоих способов. Это лексическая проверка, не доказательство отсутствия семантического сходства или pretraining contamination.

Внутри нового набора 96 уникальных формулировок question; 72 строки относятся к 18 повторяющимся question-шаблонам. Полные question+context+inputs при этом не повторяются. Повторяются форматы controlled rule/missing/compound задач; новые значения не делают варианты независимыми. Всего **25 групп**: 5 source documents, 4 numerical families, 10 input-defect families, 4 tool-selection families, 1 strict-temperature-rule family и 1 heat/rain compound family. Эти group IDs должны использоваться в парном cluster bootstrap; Wilson/example-level bootstrap не устраняют зависимость. QA содержит 20 фактов и 5 документов, а не 40 независимых аграрных знаний.

Ограничения: набор спроектирован авторами под существующие задачи, 73.3% строк synthetic, QA-контексты короткие и предоставлены модели. Он проверяет контролируемые вычисления, отказ при плохих входах и чтение контекста; не доказывает качество на произвольных реальных фермерских запросах, российской агрономии или новых семействах задач. Новые тексты/значения независимы от DEV примеров и ответов финального прогона, но шаблоны остаются внутри уже известного распределения. Публикации могли входить в pretraining; это UNKNOWN.

SHA256 итогового JSONL:

```text
3a4d47451fec18794b084d08d5f45c80b1443d3f99afca4656f9b335b578ac03
```

SHA256 реестра источников после проверки семи HTTP страниц:

```text
cee18b0a44fbd93d50ae84072f6afef9e0ceb5516ae6caecaa96a66150866abd
```

Проверка существующего артефакта без записи и без inference:

```powershell
.\.venv\Scripts\python.exe scripts/build_home_holdout.py --verify-existing
.\.venv\Scripts\python.exe -m pytest tests/test_home_holdout.py -q
```

Три смысловые проверки нового набора прошли. После protocol freeze и первого final execution содержимое JSONL и его labels должны остаться неизменными. Замечания последующего human audit следует записывать отдельно; любое пересмотренное исследование требует нового protocol/dataset version, а не незаметной правки этого holdout.

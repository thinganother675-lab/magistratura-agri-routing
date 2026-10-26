# Независимая проверка локального screen ruTXTAgroBench — 03.10.2026

Статус аудита: **STAGE1 VERIFIED / SHORTLIST BOUNDARY VERIFIED / STAGE2 VERIFIED / FINAL ANALYSIS VERIFIED / DEV**. Основной независимый пересчёт завершён. Проверяющий не управлял LM Studio, не вызывал модели, не выполнял cloud inference, не запускал TEST, ничего не отправлял и не публиковал. Read-only обращения к публичным GGML/Hub metadata перечислены отдельно. Исторические файлы, исходные задания, эталоны и ответы моделей не изменялись.

Проверена серия `results/20261003_local_screen_571682f5`. Исходный файл публичного DEV находится только в игнорируемом `.runtime/mera`; проверка выводит и сохраняет исключительно хеши, идентификаторы, счётчики и числовые/булевы измерения. В этом документе нет текстов заданий, эталонов или ответов моделей.

## Подтверждённые свидетельства

| Проверка | Проверенный объём | Результат |
|---|---:|---|
| Исходный DEV, SHA256 и идентификаторы | 293 записи | SHA256 соответствует замороженному источнику; все ID уникальны и совпадают с протоколом |
| Строгая разбираемость исходных эталонов | 293 записи | 289 разбираются; 4 сохранены как нерешённые ошибки формата |
| Исторический DEV60 | 60 ID | По 6 заданий в каждой из 10 исходных дисциплин; 59 разбираемых эталонов |
| Полный Stage1: независимый пересчёт EM/F1 | 10 терминальных манифестов, 481 попытка, 480 завершённых ответов | Расхождений по каждому заданию и агрегатам нет |
| Запросы полного Stage1 | 481 попытка и синтетические прогревы | Совпадают параметры, system, reasoning policy, идентификатор модели и исходные промпты; превышений бюджета контекста не найдено |
| Сохранённые время, токены и lexical confidence | 15 терминальных манифестов, 1946 попыток | Расхождений с raw, квантилями, суммами, load/warmup accounting и coverage нет |
| Точная raw JSON schema и SSE identity Stage1 | 480 завершённых ответов | Все удовлетворяют исходной raw schema; choice index и идентификаторы моделей совпадают |
| Исходная облачная диагностика из сохранённых ответов | 20 попыток | Исправленные EM/F1, расчётные цены, параметры и хеши совпадают; 15 ответов завершены успешно |
| Новая облачная серия Mercury512, общий DEV60 | 60 попыток | 56 успешных ответов и 4 `length`; все EM/F1, параметры, цены, хеши и identity совпадают |
| Граница shortlist до Stage2 | 19 проверок | Все выполнены; пять завершённых кандидатов принадлежат независимо пересчитанному Pareto; файлов Stage2 на момент проверки не было |
| Снимки исходников | Первоначальные и amendment01–03 | Каждый снимок соответствует хешу своей версии; первоначальные снимки сохранены отдельно |
| Завершённые полные DEV293 | Все пять замороженных кандидатов; 1465 попыток | По 293 успешных ответа и 289 исходных разбираемых эталонов; расхождений метрик, запросов и хешей нет |
| Raw JSON schema / SSE identity всего локального исследования | 1945 успешно завершённых ответов | Все удовлетворяют заданной raw schema; returned model identity и choice index совпадают |
| Повторённые DEV60 в полных прогонах | Все пять моделей; 60 ID каждая | Запросы одинаковы; обе Gemma, Qwen9 и Qwen27 повторили 60/60 valid sets, Qwen4 — 59/60 и тот же один invalid; переключений strict correctness нет |
| Облачный итог и claim provenance | 80 попыток и 62 утверждения | Все hashes/JSON pointers/values совпадают; 71 успешный ответ, известная оценка стоимости $0.00837025 плюс один UNKNOWN timeout |
| Дополнительные inventory/upstream claims | 79 + 44 утверждения | Все hashes/pointers/values/status и записанные code bindings совпадают; 8 current + 2 historical byte identities сохранены |
| Финальный локальный analysis / claims | 759 утверждений, 72 cascade grid points | Все значения, группы, AUC, Wilson, paired counts, выборы и источники независимо воспроизведены |
| CSV delivery | 10 Stage1, 5 Stage2, 50 domain rows | Каждая ячейка соответствует замороженному analysis; строки и группы полны и уникальны |
| Software validation / claims | 633 JUnit cases и 7 утверждений | XML counts/hash и DEV/software code bindings совпадают; 0 failures/errors/skipped |
| TEST draft/readiness | 9 blockers | Hash/evidence/code bindings и причины совпадают; readiness/inference/submission остаются false |
| Последний controller host receipt | Все пять манифестов и завершённый controller | Счётчики, source hashes и даты согласованы; receipt сообщает unload 0/0 и сохранение 24 inventory entries |

Закреплённая revision данных: `b00011342a8f5f1e7968edaa2f6d50545a1e8f79`. SHA256 исходного DEV: `be1c6da85e9c19a819656733fcb30318b79735e05068d5699a3f4142df50d150`. Хеш проверен до и после чтения. Исходный протокол и цепочка трёх поправок проверены по хешам; даты поправок предшествуют началу всех проверенных моделей. Исполнявшиеся runner и scorer соответствуют effective amendment03; их canonical archived source commit — `3bbe24410cdc42d74edd2791cd7b5862e2848987`, который также записан во всех Stage1 манифестах.

Stage2 манифесты сохраняют фактический working-tree HEAD на начало каждой модели: Gemma12 — `39f18b3`, Gemma26 — `92cf970`, Qwen4 — `8c7208b`, Qwen9 — `52c9e572`, Qwen27 — `888b470` (полные SHA в receipt). Это разные HEAD, при одинаковых неизменённых runner/scorer bytes и effective protocol; они не заменяются одним предполагаемым execution commit. Финальный анализ привязан к собственному `65e6f8491cf51346a97665ed870871d3a69fdcbf` и отдельным source hashes.

Первоначальная узкая проверка только каталога `source_snapshots` предположила отсутствие effective snapshots. Проверка соседних каталогов `source_snapshots_amendment_01`, `_02`, `_03` показала, что они уже сохранены. Эта гипотеза снята; проблемы с хешами снимков не обнаружено.

## Проверенный полный DEV293

| Конфигурация | Strict EM, correct/289 | Strict F1 | Request p50 / p95, с | Invalid / errors |
|---|---:|---:|---:|---:|
| Qwen 27B | 150/289 = 51.9031% | 0.646779 | 1.374 / 1.753 | 0 / 0 |
| Gemma 26B A4B | 147/289 = 50.8651% | 0.667112 | 0.807 / 0.948 | 0 / 0 |
| Qwen 9B | 141/289 = 48.7889% | 0.628621 | 0.295 / 0.402 | 0 / 0 |
| Gemma 12B | 132/289 = 45.6747% | 0.635475 | 0.499 / 0.611 | 0 / 0 |
| Qwen 4B | 97/289 = 33.5640% | 0.563973 | 0.225 / 0.273 | 1 / 0 |

Финальный selector верно рекомендует Qwen27 как primary local **по strict EM среди этих пяти конфигураций на DEV**. При заявленном exploratory допуске 10 п.п. по EM правило минимальной p95 верно выбирает Qwen9 как latency-quality candidate. Это правило не является подтверждённым критерием агрономической допустимости. Gemma26 имеет более высокий F1, чем Qwen27, поэтому лидерство по EM не означает лидерство по всем метрикам.

Парные исходные 289 задания Qwen27/Qwen9 дают 113 both correct, 37 only Qwen27, 28 only Qwen9 и 111 both incorrect. Разность strict EM — 9/289 = 0.031141868512. Подтверждающий p-value не вычисляется. Wilson95 intervals правильно рассчитаны, но имеют только описательную роль при условных binomial предположениях; фиксированная выборка, question dependence и post-selection не устраняются этими интервалами.

Весь raw/safe подсчёт охватывает 1946 локальных benchmark attempts: 481 на Stage1 и 1465 на Stage2. Из них 1945 успешно завершены; единственный неуспешный benchmark completion — Stage1 GPT-OSS `length`. Qwen35 остался FAILED_LOAD с нулём benchmark attempts. Failed/partial profiles не допущены к primary ranking.

Независимый пересчёт выполнен отдельным локальным кодом без вызова production-функций `choice_set`, `set_score` и `summarize`. Из закреплённого DEV восстановлены только допустимые варианты и исходный промпт; затем ответы из сохранённых raw разобраны как множества латинских букв. EM рассчитан как равенство множеств, F1 — как `2 × |пересечение| / (|эталон| + |предсказание|)` по каждому заданию. Незавершённый ответ или ошибка исполнения получают нулевой вклад; исходный неразбираемый эталон остаётся нерешённым. Ни кириллическая транслитерация, ни извлечение ответа из пояснений, ни смысловое исправление не применялись.

Для каждого проверенного терминального манифеста raw и safe JSONL совпадают по порядку ID, сохранённым SHA256 и хешам при повторном чтении. Проверены исходные промпты, их хеши, system, общие параметры и запрошенный reasoning. Из сохранённых SSE независимо пересчитаны вероятности непосредственно выданных токенов вариантов; они совпадают с сохранёнными numeric measurements. Наличие одинакового запроса seed не является отдельным доказательством детерминированного backend.

Полный Stage1 закрыт в 10 явных терминальных манифестах. Восемь моделей имеют `COMPLETE`, по 60 завершённых ответов; Qwen35 имеет `FAILED_LOAD` и 0 benchmark calls после ошибки измерения при загрузке; GPT-OSS имеет `PARTIAL`, одну попытку и 0 завершённых ответов после `length` на бюджете 512 токенов. Последнему ответу правильно присвоен нулевой вклад. Для всех `COMPLETE` подтверждены шесть reload offsets `0,10,20,30,40,50`; partial не подменяют полное покрытие. На момент проверки `08:36:07 UTC` shortlist ещё отсутствовал и Stage2 не начинался.

В `08:44:56 UTC` independently проверены amendment выбора и замороженный shortlist: Qwen27, Qwen9, Qwen4, Gemma26, Gemma12. SHA256 shortlist — `1ff0f4d3df063efff07956f96d10ee6c935e605e251df8707b3bc91d128cc179`; amendment — `72173cc1753b211452797fee1c69e786cabb6102763f34207ea504dcbb718499`. Все 19 проверок прошли: Stage1 завершён до amendment; amendment предшествует shortlist; hashes Stage1, протокола, reviewer receipt, effective snapshots и анализатора совпадают; все пять моделей завершены и относятся к независимо пересчитанному Pareto; каталогов с файлами Stage2 ещё нет. Контроллер начал DEV293 после этой проверки.

Практический shortlist оформлен как явный агентный выбор **после просмотра DEV60 и до DEV293**. Исходный автоматический shortlist с MiniCPM сохранён отдельно; заменять его без раскрытия истории нельзя. Amendment прямо указывает `human_review=false`: независимый агентный аудит не подменяет человеческую научную проверку.

В исходной диагностике Mercury найдено 20 попыток: 8 для одного профиля и 12 для другого. Завершены 5 и 10 ответов соответственно; четыре ответа закончились `length`, одна попытка завершилась ошибкой. Оба исправленных operational gate этой серии закрыты.

Позднее выполнена отдельная серия `20261003_cloud_budget_only_c1184a27`: единственное изменение Mercury2.5 instant — бюджет ответа с 256 до 512. Успешный operational probe12 предшествует выбору профиля, профиль заморожен до extension48, ID не повторялись между частями. Независимо проверены все 60 попыток: 56 закончились `stop`, четыре `length` получили нулевой вклад. Набор ID точно совпал с DEV60; EM `31/59`, F1 `0.6576271186440678`, известная token-cost estimate `$0.0020922` воспроизведены. Все usage известны, снимки и request parameters совпали с отдельным plan.

Исходный extension manifest использует `status=COMPLETE` для всех 48 выполненных попыток, хотя только 44 ответа успешно завершены; его summary правильно показывает `complete_coverage=false`. Манифест сохранён без изменения. Дополнительный `manifest_status_correction.json` явно фиксирует `ATTEMPT_COVERAGE_COMPLETE_WITH_FAILURES`, 44/48 и 56/60 успешных ответов. Независимо сверены hash родительского manifest, счётчики и неизменность combined bytes: исправление не меняет метрики. Сохранённые расчётные цены являются оценками по известным usage и закреплённым тарифам, а не свидетельством списанной суммы.

## Научные и технические границы

DEV60 — фиксированная стратифицированная выборка по шесть заданий каждой дисциплины. Её общий процент отражает этот screen. Полный DEV293 имеет другое распределение дисциплин и включает задания screen; последующий выбор моделей по нему остаётся **DEV**, с зависимостью от этапа выбора. Это не независимая подтверждающая проверка и не официальная серверная оценка MERA.

Независимо вычислены нетюнингованные analytical baselines. Выбор всех доступных вариантов даёт EM 0 и F1 0.467810061878 на DEV60/59; на DEV293/289 — EM 0 и F1 0.472862086011. Для равномерного распределения по всем **непустым** subsets доступных вариантов exact analytical expectation составляет EM/F1 0.056530153523/0.365807986196 и 0.059472655772/0.369776665097 соответственно. Это не случайные прогоны модели. MiniCPM F1 ниже all-options baseline при EM 0; этот факт демонстрирует необходимость совместно показывать exact match и partial-match F1, но не устанавливает причину конкретных ошибок модели.

Совпадение исходного промпта с явным whitelist подтверждает отсутствие программного добавления поля эталона в проверенные запросы. Оно не доказывает предметную правильность исходных эталонов или отсутствие ruTXTAgroBench в обучающих данных готовых моделей; эти вопросы данным аудитом не разрешены.

Неразбираемые эталоны нельзя незаметно исправлять или удалять из описания. Основные показатели используют только исходные разбираемые эталоны: 59/60 и 289/293. Companion `conservative_all_n_em` показывает нижнюю границу при нулевом вкладе нерешённых случаев; он не утверждает, что ответы в этих случаях действительно неверны.

Partial и FAILED_LOAD должны иметь явные терминальные статусы. Их проценты описывают только выполненные попытки и не допускаются к общему ranking. У Qwen35 без успешной загрузки native identity отсутствует: это **NOT_APPLICABLE**, а не найденное расхождение идентичности. На момент дополнительной проверки native key всех загруженных моделей совпал с запрошенным ключом.

Resource peaks относятся ко всей GPU и всей системной RAM на обычном хосте; другие процессы не изолированы. Проверенные load headroom не нарушают закреплённые пороги, однако они не доказывают непрерывный минимум ресурсов за весь запуск. GPU ratio — запрошенное значение; фактическое число GPU layers не раскрыто. Request latency измеряется отдельно от reload и warmup; суммы последних проверены отдельно. Lexical confidence не является калиброванной вероятностью правильности.

Точное execution archive содержит 11 source/helper файлов; финальный downstream archive — ещё 16 индексированных source files на `65e6f849`. Независимо сверены все архивные хеши, длины и byte equality с текущими файлами. Принадлежность байтов Git commits проверена владельцем в отдельных receipt; этот аудитор Git-команды не выполнял. Исходный 11-file index сохранён без изменения; analysis/auxiliary source bytes и claims привязаны отдельно от генерации.

Финальный JUnit XML независимо разобран: 633 testcase, 0 failures, 0 errors, 0 skipped; SHA совпал с software validation receipt. Разница относительно зафиксированного владельцем исходного наблюдения 521 составляет 112 новых cases. Аудитор не перезапускал initial baseline и не воспроизводит исторический runtime по текущему Git. Эти software tests проверяют программные свойства и не подтверждают агрономическую достоверность или качество на TEST.

Дополнительно проверен GGUF header GPT-OSS без чтения tensor payload. Из [закреплённого официального `ggml.h`](https://raw.githubusercontent.com/ggml-org/ggml/353b63b439f27ab2cc19dac97ab1681ba6d2d084/include/ggml.h) получены данные type enum; SHA256 совпал с receipt, `39=MXFP4` и `8=Q8_0`. Отдельный parser прочитал 13 008 824 байта metadata/descriptors и воспроизвёл всю гистограмму. Доли **по числу хранимых tensor elements**: 91.3723139689% MXFP4, 8.5837802668% Q8_0, 0.0439057643% F32. Это не byte fractions и не доли активных MoE parameters. Единственный backend label `Q8_0` поэтому сохраняется как backend-reported, рядом с фактической mixed гистограммой; полный weight hash во время inference повторно не читался.

Текущие public Hub files двух Gemma не совпали с локальной receipt, поэтому проверены прежние metadata без скачивания весов. Точное историческое соответствие SHA256 **и** размера найдено для [Gemma12 на revision `faacc07cd184152e87f520a91e1112947b0751da`](https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/blob/faacc07cd184152e87f520a91e1112947b0751da/gemma-4-12b-it-Q4_K_S.gguf) и [Gemma26 на revision `b68961b3c96e42475123a39fe3f8aa149163cf8b`](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/blob/b68961b3c96e42475123a39fe3f8aa149163cf8b/gemma-4-26B-A4B-it-UD-IQ4_NL_XL.gguf). Проверены три relevant revision snapshots для Gemma12 и один для Gemma26; history использована только для ограниченного поиска этих границ. Public commit metadata фиксирует последующее удаление имени Gemma26. Это подтверждает историческую byte identity, но не восстанавливает installation-time repo commit и не устанавливает точную семантическую причину изменения байтов. Старые receipt и установленные файлы сохранены.

Повторённые DEV60 — диагностическая проверка согласованности сохранённых прогонов. Одинаковые seed и temperature сами по себе не гарантируют идентичный ответ. Доли совпадения относятся к presentation-normalized valid choice sets; буквы и исходные ответы не публикуются. Invalid сохраняется отдельным счётчиком и не считается valid agreement. Переключения правильности оцениваются только на 59 неизменённых исходных разбираемых эталонах. Повторные задания не являются независимым holdout.

Wall deadline проверяется при получении каждой SSE-строки, дополнительно действует HTTP read-inactivity timeout 60 секунд. Это кооперативный механизм: он не гарантирует жёсткий общий предел 60 секунд при остановке потока перед очередным чтением. Аналогично resource trip наблюдается генератором при следующей строке либо ошибке чтения. Эти границы оформлены в amendment03; runner в ходе inference не изменялся.

В анализаторе выявлена необходимость проверять хеши и provenance конкретных манифестов относительно effective protocol, а не только присваивать всем профилям общие fingerprints из протокола. Замечание устранено до shortlist: сверяются source/protocol/runner hashes, private/DEV classification, actual load config, reload offsets и наличие warmup; первый orphan amendment отклоняется. Исправленный исходник просмотрен независимо, владелец сообщил о прохождении семи профильных тестов. Эти guard исправления не изменяют frozen runner или scorer. Снимки импортируемых helper-модулей и финального анализатора теперь входят в проверенные индексы воспроизводимости.

Каскад можно пересчитать по 60 сохранённым попыткам обоих плеч с нулевым вкладом failures и статусом **SIMULATED**. Шесть завершённых локальных моделей Stage1 имеют пригодные наборы по всем 60 заданиям, включая Qwen27, Qwen9 и Gemma26; у Qwen4 и Phi по одному invalid set, который вызывает форматный fallback. Соответствие общей raw JSON schema не гарантирует принадлежность букв вариантам конкретного задания. Для конфигураций без invalid наборов форматное правило назначает ноль облачных вызовов, сохраняя целиком локальное качество, включая неверные ответы. Поэтому потенциальное сокращение вызовов на 100% по этому правилу не доказывает сохранение качества относительно cloud. Фактически сэкономленные запросы от offline replay — 0; live cascade latency/cost savings и fullDEV293 cascade не измерены.

Все 72 grid points восьми завершённых Stage1 моделей независимо пересчитаны из проверенных saved rows, включая failed cloud ответы с нулевым вкладом. Сетка и objective объявлены после наблюдения screen DEV, до offline grid evaluation. Выбор минимальной cloud fraction с EM ≥ cloud EM − 5 п.п., затем higher F1 / lower threshold воспроизведён точно. Значение 5 п.п. остаётся exploratory design margin; оно не является подтверждённым неухудшением. `confidence_benefit_established=false` корректно сохранён даже там, где наблюдается увеличение EM на том же DEV. Для primary Qwen27 выбран None / 0 cloud calls: это local-only результат. Исследовательские thresholds других моделей не заморожены как deployment rule.

Private TEST draft и readiness receipt отдельно проверены без чтения TEST inputs или обращения к моделям. Девять blocker names совпадают с независимым инспекционным расчётом; evidence hashes, guard/preparation source и primary DEV recommendation согласованы. `MERA_PRIVATE_TEST_READY=false`, `inference_permitted=false`, `submission_permitted=false`; программная проверка не устанавливает личность или полномочия людей.

Финальный host receipt владельца controller сообщает native loaded instances 0, `lms ps` 0, неизменные 24 inventory entries, RAM available 22.902359 GiB и actual GPU free 15289 MiB. Проверена его согласованность с пятью финальными манифестами, source/shortlist hashes и датами; capture выполнен после всех завершений. Этот аудитор не делает отдельного утверждения о live host state и не обращался к LM/GPU endpoints.

Сохранённое заключение о опубликованной метрике MERA отделено от серверных утверждений: локальный public scorer повреждает вариант A, `SERVER_METRIC_CERTAINTY = UNKNOWN`. Этот аудит не обращался к серверу. Права остаются `USE_WITH_RESTRICTIONS / DO_NOT_REDISTRIBUTE`; собственная лицензия кода не разрешает публикацию benchmark text. Приёмка official submission и ответы сопровождающих не проверены. `MERA_PRIVATE_TEST_READY = NO` сохраняется; программная readiness inspection не предоставляет разрешение на inference или отправку.

## Машиночитаемые файлы аудита

- `results/20261003_local_screen_session/independent_qa_20261003T082242.json` — исходный DEV, протокол, все снимки, независимые EM/F1 и запросы первых четырёх моделей.
- `results/20261003_local_screen_session/independent_qa_cloud_20261003T082504.json` — независимый пересчёт исправленной облачной диагностики из сохранённых raw.
- `results/20261003_local_screen_session/independent_qa_timing_20261003T082812.json` — время, токены, confidence, агрегаты и load headroom восьми терминальных манифестов.
- `results/20261003_local_screen_session/independent_qa_20261003T083607.json` — полный Stage1: все 10 манифестов и 481 попытка, независимые EM/F1, completion accounting, исходные промпты, модельные идентификаторы, параметры и хеши.
- `results/20261003_local_screen_session/independent_qa_schema_20261003T084309.json` — raw JSON schema, choice index и SSE model identity всех 480 успешно завершённых ответов Stage1.
- `results/20261003_local_screen_session/independent_qa_boundary_20261003T084456.json` — 19 проверок перед первым вызовом DEV293, независимый Pareto и hash chain.
- `results/20261003_local_screen_session/independent_qa_cloud512_20261003T084931.json` — новый общий облачный DEV60: 60 попыток, 56 успешных ответов, cost estimate и независимые EM/F1.
- `results/20261003_local_screen_session/independent_qa_20261003T085414.json` — первый полный локальный DEV293 (Gemma12) вместе с неизменным Stage1 и проверкой shortlist timing.
- `results/20261003_local_screen_session/independent_qa_archive_20261003T085559.json` — 11 execution archive файлов и append-only correction облачного статуса.
- `results/20261003_local_screen_session/independent_qa_gguf_20261003T085946.json` — независимые official enum hash и header-only mixed tensor histogram GPT-OSS.
- `results/20261003_local_screen_session/independent_qa_cloudclaims_20261003T090313.json` — 62 облачных утверждения, итоговые счётчики и статус provisional DEV.
- `results/20261003_local_screen_session/independent_qa_20261003T091031.json` — три завершённых полных DEV293 и неизменный Stage1.
- `results/20261003_local_screen_session/independent_qa_timing_20261003T091023.json` — независимые время, tokens, lexical confidence, load/warmup accounting и recorded headroom всех 13 терминальных манифестов.
- `results/20261003_local_screen_session/independent_qa_overlap_20261003T091032.json` — совпадение наборов и correctness switches повторённых DEV60 у первых трёх завершённых моделей.
- `results/20261003_local_screen_session/independent_qa_weight_history_20261003T091343.json` и `independent_qa_weight_history_followup_20261003T091548.json` — append-only chain исторической byte identity обеих Gemma; первое промежуточное UNKNOWN для Gemma12 разрешено followup.
- `results/20261003_local_screen_session/independent_qa_20261003T092009.json`, `independent_qa_timing_20261003T092010.json`, `independent_qa_overlap_20261003T092011.json` — четыре завершённых полных DEV293, 14 terminal manifests и повторённые DEV60.
- `results/20261003_local_screen_session/independent_qa_auxiliary_claims_20261003T092326.json` — 123 дополнительных claims и source/code bindings; Git byte equality остаётся отдельно аттестованной владельцем.
- `results/20261003_local_screen_session/independent_qa_baselines_20261003T092446.json` — независимые нетюнингованные analytical baseline aggregates по исходным refs и дисциплинам.
- `results/20261003_local_screen_session/independent_qa_runtime_packages_20261003T092616.json` — current auditor `.venv` Python/package metadata; не process-level attestation controller и не wheel hash verification.
- `results/20261003_local_screen_session/independent_qa_baseline_claims_20261003T093143.json` — все три analytical baselines, включая uniform single-option, и 12 соответствующих claims.
- `results/20261003_local_screen_session/independent_qa_20261003T093340.json` — итоговые все пять DEV293 и полный Stage1; 1946 attempts, ноль core mismatches.
- `results/20261003_local_screen_session/independent_qa_timing_20261003T093340.json` и `independent_qa_schema_20261003T093329.json` — финальные timing/token/confidence/load проверки и raw JSON/SSE identity.
- `results/20261003_local_screen_session/independent_qa_overlap_20261003T093341.json` — все пять DEV60-overlap diagnostics; выборы и эталоны представлены только числовыми счётчиками.
- `results/20261003_local_screen_session/independent_qa_final_20261003T093559.json` — 759 локальных claims, 72 cascade grid points, breakdowns, AUC, Wilson, paired discordance и primary/latency-quality selection.
- `results/20261003_local_screen_session/independent_qa_delivery_20261003T093842.json` — все CSV ячейки и отдельный TEST draft/readiness с девятью blockers.
- `results/20261003_local_screen_session/independent_qa_host_20261003T094058.json` — consistency финального controller host receipt и реальные per-model recorded HEADs.
- `results/20261003_local_screen_session/independent_qa_final_archive_20261003T094554.json` — 16 downstream source files и независимый разбор 633-case JUnit XML.
- `results/20261003_local_screen_session/independent_qa_software_claims_20261003T094908.json` — семь software claims и повторная проверка неизменного 11-file execution archive.

Итог: **PASS для целостности и воспроизводимости проверенного development evidence**. Все 963 новых локальных/облачных/inventory/upstream/baseline/software claims проверены по своим hashes, JSON pointers, значениям и разрешённым DEV/SIMULATED ролям. Нерешённые научные границы сохранены: четыре исходных неразбираемых refs, отсутствие независимого TEST, server scorer UNKNOWN, права USE_WITH_RESTRICTIONS, некалиброванный confidence и отсутствие live cascade savings. Это завершённый аудит данной DEV серии; он не разрешает private inference, official submission или публикацию benchmark content.

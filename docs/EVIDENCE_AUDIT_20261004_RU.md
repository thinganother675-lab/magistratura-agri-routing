# Аудит доказательной базы 4 октября 2026 года

Аудит выполнен на сохранённых данных без новых inference/API-вызовов, чтения
приватного TEST, GPU-загрузок и изменения исторических результатов. Фактические
UTC начала/окончания записаны в [новом analysis.json](../results/20261004_evidence_audit/analysis.json).
Воспроизведение: `.venv/Scripts/python.exe scripts/audit_evidence_20261004.py`.
Скрипт отказывается перезаписывать уже существующие результаты. Questions,
gold и строки ответов остаются в игнорируемой `.runtime/mera`; новые таблицы
содержат агрегаты, ID и проверяемое происхождение.

## Центральные исторические показатели подтверждены

Из retained raw повторно рассчитан каждый ответ обеих конфигураций. Результат
побитово согласован с сохранёнными безопасными per-item метриками; SHA-256 raw
и источника проверены по manifests. В каждой raw-серии 293 benchmark-записи и
30 отдельных `synthetic_warmup`, которые не попадают в показатели качества.

| Конфигурация | Strict set EM | Средний set F1 | Консервативный EM на всех 293 |
|---|---:|---:|---:|
| Qwen3.5-9B Q8_0 | 141/289 = 48,7889% | 0,628620860109 | 141/293 = 48,1229% |
| Qwen3.8-27B UD-Q4_K_M | 150/289 = 51,9031% | 0,646778711485 | 150/293 = 51,1945% |

Исходные references ID **222, 300, 317, 374** не разбираются строгим parser.
Они не исправлены транслитерацией или догадками. Основной знаменатель 289;
консервативный показатель на 293 трактует нерешённые references как нулевые,
а не устанавливает их истинную правильность. Set EM проверяет равенство всего
набора выбранных вариантов; set F1 вычисляется по пересечению наборов и затем
усредняется по заданиям. Ни одна метрика не названа production score MERA.

Парные исходы: обе верны **113**, только Qwen9 **28**, только Qwen27 **37**,
обе неверны **111**. Разность EM9−EM27 **−3,1142 п.п.**; F1 **−0,018157851376**.
Повтор domain-stratified paired bootstrap, 10 000 resamples, seed20261003,
в точности воспроизвёл сохранённые интервалы: EM **[−8,3045; +2,4221] п.п.**,
F1 **[−0,061477179107; +0,025523562366]**. Это описательная чувствительность DEV,
а не доказательство эквивалентности или неухудшения. Отношение 141/150=**94%**
означает долю наблюдаемого EM Qwen27; оно не равно accuracy94%.

DEV60 входит в DEV293: все **60/60** ID повторно присутствуют. Screening,
shortlist, подбор профилей и последующая полная оценка не образуют независимые
наборы данных. TELEMETRY40 также взята из DEV293, её пересечение с DEV60 —
**20 ID**. Это три повторно использованных представления public DEV.

## Новое: качество сохранённых TELEMETRY40 ответов

Ответы native-серии впервые в этом аудите оценены тем же `choice_set/set_score`
без изменений parser и references. Для обоих моделей присутствуют ровно 40
заданных protocol ID, из них 39 разбираемых references: ID374 остаётся unresolved.

| Модель и профиль | EM на тех же 39 | Set F1 | Ошибки транспорта | Нарушения JSON contract |
|---|---:|---:|---:|---:|
| Qwen9, исторические DEV293 ответы на тех же40 | 23/39 = 58,9744% | 0,728205128205 | 0 | 0 |
| Qwen9, native TELEMETRY40 | **22/39 = 56,4103%** | **0,719658119658** | 0 | 2 |
| Qwen27, исторические DEV293 ответы на тех же40 | 23/39 = 58,9744% | 0,737362637363 | 0 | 0 |
| Qwen27, native TELEMETRY40 | **24/39 = 61,5385%** | **0,780097680098** | 0 | 0 |

Все 80 пары совпадают по фактическим UTF-8 bytes user/system input и task ID.
Сохранённые weight receipts обеих серий совпадают по пути, exact bytes и
SHA-256; веса на диске в этом офлайн-аудите заново не хешировались. Файл Qwen9
имеет 9 527 502 048 bytes; Qwen27 — 16 464 440 224 bytes.

При одинаковых input bytes набор выбранных вариантов изменился у **1/40**
ответов Qwen9 и **2/40** Qwen27. Полностью одинаковые response bytes — **38/40**
у каждой модели. У Qwen9 два ответа нарушают JSON contract, но допускаются
существующим parser как латинские наборы; invalid predictions — 0. Поэтому
JSON-validity и корректность ответа различаются. Qwen9 потерял один EM,
Qwen27 приобрёл один. Парность native моделей: **19 обе верны; 3 только9;
5 только27; 12 обе неверны**. Это не независимая проверка DEV293.

| Свойство | Исторический DEV293 | Native TELEMETRY40 |
|---|---|---|
| Transport | OpenAI-compatible `/v1/chat/completions` | native `/api/v1/chat` |
| Temperature/top_p/context/token budget | 0/1/2048/512 | 0/1/2048/512 |
| Reasoning | `none`, `enable_thinking=False` | `off`; recorded reasoning отсутствует |
| Seed | 42 | не задан |
| Schema enforcement | strict JSON schema | не задано; лишь та же текстовая инструкция |
| Context checkpoints | 32 | 0 |
| Requested GPU | Qwen9 `max`; Qwen27 `0.75` | automatic; placement неизвестно |
| Actual layers | неизвестны | неизвестны |
| Loads/warmups | 30/30, reload каждые10 | 2/2 на модель; ABBA блоки по20 |

Warmup и load не включены в request latency. Нельзя называть reload гарантированно
cold: OS/runtime caches не полностью наблюдаемы. Native stream completion не
доказывает EOS: точный stop/length reason не раскрыт этим API.

| Native TELEMETRY40 | Qwen9 | Qwen27 |
|---|---:|---:|
| Request latency p50/p95, с | 0,268663 / 0,343981 | 1,434159 / 1,829149 |
| Client answer TTFT p50, с | 0,122284 | 0,690953 |
| Backend TTFT p50, с | 0,090318 | 0,639350 |
| Backend reported token/s p50 | 40,333738 | 7,562348 |
| Whole-device GPU sampled request peak, MiB | 11 471 | 13 287 |
| Whole-system RAM sampled request peak, GiB | 20,858128 | 28,470402 |
| Allowlisted LM Studio process-group RSS peak, MiB | 11 198,957 | 18 742,336 |

Для этой маленькой подвыборки допустимо совместно описывать **её собственное**
retrospectively scored качество и contemporaneous native timing: 22/39 против
24/39 при приведённых p50/p95. Для всего DEV293 остаётся отдельный исторический
результат. При изменившемся поведении запрещено представлять historical141/289
и native p50 как одновременный эксперимент с идентичными настройками.
Новый matched DEV rerun не нужен, если рукопись ясно сохраняет это разделение.
Обобщение коротких JSON/буквенных ответов на long-form generation не обосновано.
Peak GPU/RAM относится к устройству/системе, RSS — к сумме процессов по basename,
не к приватному физическому allocation модели; энергию не измеряли.

## Study C: сохранённые численные результаты и пределы

Использована исправленная историческая сводка; первичные записи не изменены.

| Показатель | Qwen9 V1 | Qwen27 V2 | Детерминированный executor |
|---|---:|---:|---:|
| Полный правильный ответ /27 | 7 | 15 | 27 |
| Numeric+unit /16 | 1 | 6 | 16 |
| Action /27 | 19 | 26 | 27 |
| Применимая декларация tool /26 | 17 | 25 | 26 |
| Missing/invalid inputs и units /10 | 5 | 8 | 10 |
| Явное преобразование units /3 | 0 | 1 | 3 |
| Saved tool-choice replay /26 | 17 | 25 | 26 |

Tool-name declaration и replay не являются live tool calls. Исторические
live tool calls — **0**; новые текущие эксперименты должны иметь отдельные
protocol/results и не подменять эту таблицу. Typed task и формулы были явно
даны всем arms. Replay передаёт исходные inputs executor; он не проверяет
правильность модельных аргументов. Qwen9V1/Qwen27V2 различаются runtime, поэтому
историческую Study C latency нельзя трактовать как чистый model-size эффект.
High-precision scorer и отдельная rounding1e-4 диагностика дали одинаковые
numeric counts1/16 и6/16; строгие scores сохранены. Реализация FAO-56/GDD —
технический reference для указанной формулы; 27/27 не доказывает безопасность
агрономических рекомендаций и не является 27 независимыми agronomic facts.

## Покрытие, сбои и supplementary cloud

Полная компактная таблица: [model_coverage.csv](../results/20261004_evidence_audit/model_coverage.csv).
Она разделяет model/checkpoint, access, dataset/split, N, config, status,
metric, live/replay, role и primary evidence.

OpenRouter HOME DEV9: Ling3.0FlashSante **4/9**, hosted Qwen3.8-27B **5/9**,
Dots3NotePreview **4/9**, по9 успешных генераций каждого. `shared_dev.status=NOT_RUN`
в старой сводке противоречит её же `test_status=TESTED`, 9 attempts и retained
outcomes. Новый coverage использует actual outcomes; старый файл сохранён.
Это HOME, не MERA. Hosted display name не удостоверяет совпадение локальных
weights/quantization/serving config.

Mercury2.5 MERA DEV60, instant512/temperature0.5: **31/59 EM; F1 0,657627118644**.
Combined60 состоит из reused12 и new48 historical attempts. В extension48
получены 48 responses, из них44 completed по declared success policy;
combined60 — 60 responses,56 completed,4 length errors. Ошибки включены в
scored denominator, unresolved reference отдельно. Это реальные сохранённые
API-запросы; последующее confidence routing — **replay**, его cost/latency
не являются live cascade measurement. На DEV60 local-only37/59; ни один
ненулевой сохранённый fixed threshold не улучшил EM, поэтому cloud escalation
benefit не установлен. Новых Mercury calls/paid spending нет.

Codex CLI gpt-6-luna medium:60/60 completed, **36/59 EM; F1 0,735108958838**,
46 JSON-contract violations при0 parser-invalid; backend weight revision
не раскрыта. Latency включает запуск CLI/system overhead. Subscription cost
не равен нулю. Claude Code:2 synthetic403,0 DEV attempts; качество не измерено.
Jev/Laya: отдельная HOME DEV36×6,216 live outcomes; Jev30/36, rule31/36,
Laya23/36. Router/provider timeouts, all external requests и changed guards
сохраняют ограничения сравнения. Эти блоки нельзя смешивать с MERA DEV293
или с Study C в общий accuracy score.

## Ответы на вопросы о справедливости сравнения

1. Это **исследование практических конфигураций**, меняются generation,
   parameter count, quantization и offload; causal size study не выполнена.
2. Исторические Qwen9/27 получают одинаковые format prompts/schema; native
   обе получают одинаковую инструкцию без schema. Разницу между transport
   profiles нельзя скрывать, а JSON contract нужно отделять от parsed EM/F1.
3. Budget512 и off reasoning задают конкретный эксплуатационный сценарий,
   не универсально нейтральную оценку reasoning models. У частичных screen
   моделей сохраняются timeout/length failures; исключать их из общего рейтинга
   как будто запусков не было нельзя. У завершённых historical293 обоих Qwen
   transport errors0; native finish reason остаётся UNKNOWN.
4. Runtime changes и model changes представлены раздельно, actual GPU layers
   не приравнены к requested ratio. Новое same40 scoring показывает небольшое,
   но фактическое изменение ответов.
5. EM — exact set accuracy; F1 — partial overlap. Ratio94%, пересечение bootstrap
   interval с0 и похожие point estimates не доказывают equivalence. Численная
   non-inferiority margin не задана и post-hoc не подбирается.
6. DEV60 selection, DEV293 reuse и TELEMETRY40 subset раскрыты. Повторные тесты
   не образуют независимую выборку; bootstrap остаётся descriptive.
7. Real saved API и simulated routing различаются. Cloud улучшение в этой MERA
   replay серии не подтверждено; оно не является условием завершения статьи.
8. Memory scopes раскрыты; process RSS и whole-device GPU не являются приватной
   памятью модели. Short answer timing не является universal generation speed.
9. Исторические tools получают исходные public inputs и typed task; gold не
   заполняет недостающие arguments. Однако replay обходит модельную передачу
   arguments, поэтому живой tool pipeline требует отдельной проверки.
10. Published scorer diagnostic, strict set scoring, unresolved labels и неизвестный
    production server scorer разделены. Software Apache-2.0 не распространяет
    права на dataset/raw logs. Private TEST и MERA submission не выполнялись.

Фактическая граница выводов: на одном consumer PC Qwen9 Q8_0 даёт меньшую
измеренную задержку и потребление общих ресурсов с меньшим observed EM,
чем Qwen27 UD-Q4_K_M. Стабильность результата на независимых заданиях,
эквивалентность, universal superiority и farm deployment safety не доказаны.

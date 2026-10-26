# Jev/Laya до генерации: живое exploratory сравнение 02.10.2026

**DONE:** 216 уникальных измерений, 36 development задач × 6 методов, без повторного запуска ответов. Начало 18:01:19 UTC, завершение 18:14:00 UTC. Это ранее доступный DEV, не новый независимый тест. 21 EN / 15 RU; 6 категорий по 6 задач; 21 объявленная группа. Human review FALSE. Переводы и шаблоны могут зависеть друг от друга и выше уровня этих групп.

Исторические 90/150 результаты, scoring и каскад не переписаны. Общие генераторы: Gemma 4 26B-A4B IQ4_NL_XL / context4096 / parallel1 / GPU request0.70 и Mercury2.5. Laya-multilingual работает на CPU float32, 4 threads, input1024/head256; Jev — hosted jev-1.13.0, один пакет двух typed questions. Gold/category/expected route не поступают selector. Методики и hash фиксируются в [protocol](../results/20261002_180119Z_76283d02_prerouting_dev/protocol.json) и [architecture](PREROUTING_ARCHITECTURE_20261002_RU.md).

| Схема | Правильно /36 | Генеративные cloud | Hosted router | Все внешние | Mean, s | p50, s | p95, s | Известная оценка $, не счёт | Неизвестных списаний |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TOOLS+CLOUD | 31 | 24 | 0 | 24 | 4.314 | 1.333 | 17.156 | 0.00118831 | 2 |
| Старый TOOLS→LOCAL→CLOUD | 32 | 18 | 0 | 18 | 4.349 | 1.386 | 17.232 | 0.00081088 | 2 |
| Rule-first | 31 | 23 | 0 | 23 | 6.244 | 1.316 | 60.543 | 0.00098890 | 3 |
| Jev-first | 30 | 20 | 36 | 56 | 1.614 | 1.782 | 2.953 | 0.002297568 | 0 |
| Laya-first | 23 | 13 | 0 | 13 | 2.981 | 0.893 | 2.823 | 0.00045803 | 1 |
| Offline Laya/rules/tools/local | 12 | 0 | 0 | 0 | 0.793 | 0.721 | 1.016 | 0 | 0 |

Operational latency включает router, guards, генерацию и неуспешные попытки. Provider timeouts остаются в знаменателе и влияют на mean/p95. Отдельная technical-success latency сохранена в JSON; исключение ошибок не используется для основной таблицы. Нельзя приписать меньшую mean Jev только архитектуре: Mercury дал восемь ReadTimeout неравномерно между arms. Ещё два ответа завершились `length`. Router transport/schema failures: Jev 0/36, Laya 0/72. Retries/verification HTTP: 0. Server prompt/KV cache policy UNKNOWN; отсутствие replay не доказывает cold-cache latency.

**Primary Jev-first − rule-first:** −2.78 процентного пункта; paired whole-group bootstrap 95% CI [−20.69; +12.12] pp, 5000 resamples, seed20261002. Преимущество не установлено. Генеративных вызовов 23→20 (−13.0%), но всех внешних запросов 23→56 (+143.5%). Известная тарифная оценка выросла на 132.3%; точная разница полной стоимости UNKNOWN из-за трёх неизвестных списаний у rule-first и отсутствия invoice. Jev использовал 29274 input / 2806 output tokens; router fee estimate $0.001229508 уже включена в таблицу. Jev→LOCAL остаётся внешней обработкой.

**Laya-first − rule-first:** −22.22 pp; exploratory CI [−43.24; −2.56] pp. Это не confirmatory интервал после выбора среди нескольких методов. У Laya в обеих arms фактическое truncation 0/36, dropped state tokens0, truncated question0; ухудшение нельзя объяснить наблюдаемым обрезанием. Confidence не калибрована как вероятность правильного аграрного ответа.

Новый lexical ambiguity guard общий для rule/Jev/Laya, но отсутствует в историческом каскаде. Поэтому сравнение pre-routing с каскадом содержит дополнительный фактор; primary Jev-versus-rule применяет одинаковые guards. Hard numerical gate отдельно переопределил 12 решений каждой pre-routing arm. Jev ambiguity overrides14, Laya13. Успех numerical/missing-input tasks нельзя приписывать learned router.

| Категория, n=6 | Tools+cloud | Cascade | Rule | Jev | Laya | Offline |
|---|---:|---:|---:|---:|---:|---:|
| Compound reasoning | 5 | 5 | 5 | 6 | 0 | 0 |
| Context QA | 4 | 4 | 3 | 3 | 4 | 0 |
| Missing data | 6 | 6 | 6 | 6 | 6 | 6 |
| Numerical | 6 | 6 | 6 | 6 | 6 | 6 |
| Rule interpretation | 5 | 5 | 5 | 6 | 5 | 0 |
| Tool selection | 5 | 6 | 6 | 3 | 2 | 0 |

EN correct/21: 17,19,17,18,15,6; RU correct/15: 14,13,14,12,8,6 соответственно. DEV context QA только английская, состав категорий RU/EN отличается. Эти доли не измеряют отдельный причинный language gap. Strict extractive scoring может отклонять эквивалентные формулировки; literal-grounding verifier исторического каскада сохраняет известную слабость compound cases.

True offline проверен запретом внешних socket/HTTP inference и реально сделал 0 hosted/0 cloud requests. Offline correct12/36 относятся только к numerical и missing data: ASK19, ABSTAIN10, tool6, local1. Это низкая coverage, не преимущество по graceful degradation. Gold ABSTAIN в этом DEV нет; correct abstention **NOT IDENTIFIABLE**. Wrong scored answer proxy не называется human-audited hallucination или безопасностью агрономического решения.

Laya load16.602s / нейтральный warmup0.428s исключены из per-request latency, resident CPU worker одинаков во всех arms. Peak process RSS1.668GiB; whole-device GPU peak13843MiB, whole-system RAM peak26.067GiB, 1368 samples, 0 poll errors. Эти GPU/RAM значения не являются размером весов или per-model allocation. Actual offloaded layers/ratio UNKNOWN; сохранён CLI request0.70. Main GGUF SHA заново проверен перед timing и совпал с историческим.

Известная оценка всего нового comparison $0.005743688; неизвестные восемь попыток сохраняют верхний резерв $0.00144472 в общем ledger. Сумма оценки и резерва $0.007188408 ниже cap$0.01. Mercury usage известна90/98; локальная10/10; Jev36/36. Для всех 90 возвращённых Mercury completions raw warning фиксирует изменение requested temperature0 на1. Promotional quota, фактический invoice и принадлежность billing account UNKNOWN. [Официальная Mercury pricing](https://www.inceptionlabs.ai/models) и [Jev pricing/model metadata](https://docs.typesafe.ai/models) проверены 02.10.2026; дополнительный pricing annotation не меняет выполненный протокол.

Evidence: [raw216](../results/20261002_180119Z_76283d02_prerouting_dev/raw_decisions.jsonl), [attempt journal](../results/20261002_180119Z_76283d02_prerouting_dev/attempts.jsonl), [versioned analysis](../results/20261002_180119Z_76283d02_prerouting_dev/analysis_20261002_181438Z_c3905087/summary.json), [budget](../results/20261002_180119Z_76283d02_prerouting_dev/budget_snapshot.json). Начальный отдельный запуск 17:59:19 завершился до первой provider attempt:0 rows/0 calls/0 spend; исходные файлы и zero-call diagnostic сохранены, после исправления импорта начат новый run.

Научный вывод: новая архитектура реализована и измерена end-to-end; данные не показывают пользу Jev сверх простой rule baseline после полного учёта hosted overhead. Негативный empirical/reproducibility case study оправдан, новый алгоритм и общая агрономическая применимость не заявляются. Независимый external group-split holdout и human gold/translation/compound audit остаются NOT RUN/PENDING.

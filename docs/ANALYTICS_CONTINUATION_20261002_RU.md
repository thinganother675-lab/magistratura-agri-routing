# Аналитическая таблица продолжения 2 октября

Статус: **DONE — новый XLSX создан, проверен визуально и повторно импортирован**. Итог: [magistratura_continuation_20261002.xlsx](../outputs/continuation_20261002_analytics_76e0c1f2/magistratura_continuation_20261002.xlsx). SHA256: `4275c85fc18a6a633bf852d5cfc6ed58d99da964751cb76a2babc8ce31c05090`.

Пять листов содержат 6 методов маршрутизации на 36 DEV случаях, 4 отдельные конфигурации новых локальных baseline, 21 имя OpenRouter, все 45 исторических серий и 31 запись методики/источников. CLI, API, reasoning profiles, разные DEV selections и диагностические HTTP ошибки не образуют общий рейтинг. Старый final150 уже наблюдался; новый независимый confirmatory holdout **NOT RUN**. Человеческая проверка **FALSE**.

Прежний workbook `outputs/home_pc_final_20261002_analytics7b4c/home_pc_models_final150_20261002.xlsx` не изменён. SHA256 до/после сборки: `002619615be4d8a7a0f58409c15e8c15d1e10a02490830ff78ee27b84f79a04c`. Сохранены controls 45 серий: API 242 requests / input 113332 / output 17259; CLI 339 requests / известные input 135133 / output 39087. Частичная usage coverage остаётся видимой.

| Конфигурация | N / верно | Input / output | p50 / p95, с | Client TTFT p50, с | Native tok/s | Весь GPU, MiB |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-4B Q8_0, LM Studio | 12 / 3 | 5588 / 390 | 0.510 / 0.870 | 0.088 | 70.02 | 6995 |
| Phi-4-mini-instruct Q8_0, LM Studio | 12 / 3 | 5052 / 364 | 0.429 / 0.499 | 0.034 | 77.35 | 5396 |
| BitNet native I2_S, legacy GGUF config | 12 / 0 | 5852 / 415 | 1.640 / 2.605 | 0.461 | 25.8158 | 841, фон |
| BitNet native I2_S, official-config alternative | 12 / 0 | 5151 / 362 | 1.180 / 1.954 | 0.281 | 32.2277 | 841, фон |

Все четыре screen остановлены по заранее заданному DEV12 gate; оставшиеся 24 случая каждого варианта **NOT RUN**. Input/output coverage — 12/12. Qwen/Phi сообщили reasoning 0 при coverage 12/12; оба BitNet не сообщили reasoning, coverage 0, numeric cell оставлена пустой. Reasoning является частью output, если так сообщил backend, и не прибавляется повторно. Client approximate tok/s хранится отдельно от native decode tok/s.

Qwen и Phi имеют отдельные manifests и SHA. Native TPS берётся из `qwen_backend_log_auxiliary.json` и `phi_backend_log_auxiliary.json` с проверкой SHA manifest/raw и alignment 12/12. RSS Qwen 5208166400 B и Phi 4586582016 B связан с единственным новым backend process с пометкой **INFERRED_UNIQUE_NEW_BACKEND**; native API не предоставил PID модели. Запрошен offload `max`; actual GPU layers остаются **UNKNOWN**.

Оба native BitNet запуска использовали CPU binary `GGML_CUDA=OFF`, `-ngl0`, четыре потока. Actual GPU layers равны 0. RSS измерен для собственного server PID: legacy 1632518144 B, official-config 1608794112 B. VRAM 841 MiB относится ко всему GPU и фоновой нагрузке, а не к памяти BitNet; system RAM и own-process RSS — отдельные показатели.

Legacy BitNet имеет **COMPATIBILITY_LIMITED**: исходная GGUF-конфигурация использует Human/BITNETAssistant template, игнорирует system turn и выдаёт missing pre-tokenizer/degraded generation warning. Official-config alternative применён один раз после token/template parity с pinned official HF metadata; warning отсутствует. Обе строки и исходные 12 ответов сохранены отдельно: результаты 12+12 не объединены, конфигурация является дополнительным фактором. Legacy 0/12 не доказывает внутреннюю способность модели.

Native trace содержит prefix/KV cache reuse (`cache_n384`); LM Studio log prefill тоже может отражать только uncached часть input. Отсутствие скрытого warm-up не означает cold request. Prefix reuse отличается от replay сохранённого ответа; полные input totals взяты из usage, а не из prefill token count.

OpenRouter итоговая matrix сохраняет **111 внешних операций: 107 metadata GET + 1 credential setup POST + 3 неуспешных completion POST**. Ling: HTTP 401 и 403; LFM: HTTP 404 с подтверждённым account privacy/ZDR ограничением. Успешных генераций 0, full DEV models 0, token/cost coverage 0/3. Поэтому accuracy, generation latency и tok/s остаются пустыми. Прочие 16 text candidates — NOT_RUN; два Lyria исключены как paid music, Safety — specialized classifier. Paid cap $0 и aggregate account usage 0 не заменяют индивидуальное billing evidence. Preferences и лимиты не менялись; quota 50/50 remaining — snapshot для всего account.

Для маршрутов operational mean/p50/p95 вычислены по всем журналированным решениям, включая failed/blocked. Technical-success latency вынесена отдельно и не означает correct-answer latency. Generative cloud calls и total external requests разделены; hosted Jev считается внешней обработкой даже при выбранном local генераторе. Табличный VRAM/RAM peak маршрутов относится ко всему run, а не к отдельной политике. Разбивка по языкам и категориям сохраняет правильные числители и знаменатели.

QA: formula-error scan — 0 совпадений; все 5 листов просмотрены через 13 PNG диапазонов. Export/reimport сверил **2787 typed non-formula cells и все 45 quality formulas**, PASS. UNKNOWN остаётся пустым numeric cell, реальный 0 сохранён. Evidence: `formula_error_scan.ndjson`, `reimport_checks.json`, `source_validation.json`, `artifact_validation.json` в новом каталоге. Visual review выполнял агент, human validation по-прежнему FALSE.

Collector: `scripts/build_continuation_workbook_20261002.py`. Python читает сохранённые JSON и XML внутри старого XLSX; workbook создан `@oai/artifact-tool` через bundled Node. API, inference, секреты, download, build модели и Git в этой workstream не вызывались. Authoring/render/reimport выполнены после terminal model states в предоставленном root свободном окне.

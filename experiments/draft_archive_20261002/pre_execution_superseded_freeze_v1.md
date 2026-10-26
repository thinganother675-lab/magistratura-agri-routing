# Независимый HOME-PC эксперимент: замороженный протокол

**FROZEN. Фактическая фиксация UTC: 2026-10-02T04:33:57.023565+00:00. Финальная inference ещё NOT RUN на момент фиксации.**
Имя файла с 01.10 обозначает начало HOME-этапа; протокол заморожен 02.10.2026, без заднего датирования. Предыдущие draft-файлы сохранены побайтово в `experiments/draft_archive_20261002/`. Это локальная предварительная фиксация, не внешняя preregistration.

Машинный источник всех параметров: `experiments/HOME_PROTOCOL_2026-10-01.json` (SHA256 `99e7b2a3946c3765e9c81dcc55753eb9c26f7534c0f0f696b2b5ea6d4e478f45`). Точный prompt: `experiments/HOME_SYSTEM_PROMPT_2026-10-01.txt`. Исторические test90 и `data/protocol_frozen.json` остаются неизменными. Драйвер отклоняет несовпадение hashes; однократный durable claim запрещает автоматический повтор или resume.

## Выбор до создания holdout

Настройка прекращена 01.10.2026 в 20:11 UTC; holdout создан в 20:20:43 UTC. Выбрана `gemma-4-26b-a4b-it`, IQ4_NL_XL, как практический reader после инструментов: controlled DEV36 22/36, p50 1.532 s, p95 2.440 s; paired bilingual probe EN4/6 RU5/6 как Qwen27 при меньшей задержке. Qwen27 выше по общему DEV25/36, но медленнее. Новая выборка и её gold не использовались для последующей настройки; модель/thresholds больше не меняются.

Local: endpoint127.0.0.1:1234, context4096, parallel1, requested GPU ratio0.70, temperature0, top_p1, seed42, max_tokens512, reasoning_effort none, строгая schema пяти полей action/answer/numeric/unit/tool. Main GGUF14556687680bytes SHA`c1ac61e3af04b40c7688dfe0686c54d68ff5ed26178a56f0b18c8a0e2b94db83`; catalog16847892149bytes включает mmproj/config. Actual GPU layers UNKNOWN; нулевое reasoning проверяется по измеряемым channels.

Cloud: Mercury2.5, Inception API, исходный SYSTEM_PROMPT и parse_output, temperature0, max_tokens512, reasoning_effort instant, json_object, timeout60s. Незавершённый finish_reason считается ошибкой. Цена $0.04/M input и $0.15/M output проверена 01.10 и повторно 02.10 на официальной странице; cached discount не применяется. OpenRouter SKIPPED по указанию пользователя; Jev — отдельный typed DEV baseline и не подменяет основной cloud.

## Выборка и scoring

150IDs и их порядок находятся в JSON. Dataset SHA`3a4d47451fec18794b084d08d5f45c80b1443d3f99afca4656f9b335b578ac03`, source registry SHA`cee18b0a44fbd93d50ae84072f6afef9e0ceb5516ae6caecaa96a66150866abd`. 75EN/75RU; QA40, numerical30, missing20, tool selection20, rule20, compound20. 110 synthetic controlled cases; QA20fact pairs из5documents. Всего25source/family groups. Exact overlap с историческими данными0; lexical Jaccard threshold0.8 не доказывает semantic OOD. Независимые Decimal reference formulas и source registry сохранены. Переводы AI-assisted, human validation PENDING. Labels не исправляются по результатам inference.

Scoring неизменён: action; QA strict span EM и вторично token F1; numerical1%relative или0.02absolute плюс unit; exact controlled labels/tool. Ошибки входят в denominator; NOT_RUN отдельно, не imputed correct/zero. Critical error — неверный numeric/missing/rule/compound ответ согласно исходному scorer; это controlled proxy, не оценка полевого вреда.

## Пять живых политик

- LOCAL ONLY: один local вызов на каждый запрос.
- CLOUD ONLY: один cloud вызов на каждый запрос.
- TOOLS+CLOUD: исходный hard gate, затем cloud.
- TOOLS→LOCAL→CLOUD: hard gate; при supplied context local и исходный grounded substring validator; при отсутствии принятой опоры cloud. Без context сразу cloud.
- OFFLINE: та же tools/local логика, CLOUD_AVAILABLE=false; при отсутствии опоры ABSTAIN.

Hard gate ожидается для30numerical и20missing, но ожидаемый route/gold не передаются provider. Все750policy decisions исполняются живьём в deterministic shuffled порядке seed20261001; responses между политиками не переиспользуются. Никаких warmups, response cache replay или paid retries. Grounded substring подтверждает буквальную опору, не семантическую правильность.

## Критерии и статистика до результата

Основной contrast hybrid−tools+cloud. Успех требует одновременно: нижняя paired95%CI качества ≥−5п.п.; сокращение cloud calls ≥10п.п. от всех150запросов; верхняя95%CI прироста critical errors ≤0; hybrid p95≤10s. Каждый критерий сообщается отдельно. Невыполнение noninferiority criterion не объявляется доказанной inferior quality. Эти границы — исследовательский выбор.

Whole-group paired percentile bootstrap5000, seed20261001, unit sample.group; per-row weighted estimand. Wilson и McNemar описательные из-за коррелированных вариантов. Показываются category/language results, quality CI/effects, routes, coverage, ASK/ABSTAIN, ошибки, mean/p50/p95 end-to-end wall time, first delta/answer TTFT и approximate client tok/s с явным coverage, tokens и whole-device/system resources. Reasoning tokens входят в output, не прибавляются второй раз. Нет gold ABSTAIN: правильность abstention UNKNOWN. Offline goal — измеренное graceful degradation.

## Бюджет, безопасность записи и воспроизводимость

До450cloud calls по6000input+512output: консервативная planning estimate $0.14256; cap $0.25. Timeout usage/charge UNKNOWN сохраняется с резервом; invoice не получен. HTTP401/402/403/429/5xx прекращают последующие cloud calls, независимая local/offline работа продолжается. Memory guards baseline≥3GiB RAM/1024MiB GPU free, live≥2GiB/512MiB; при local stop облачный hybrid может деградировать, offline ABSTAIN фиксируется. Только собственный LM Studio instance выгружается.

До запуска213tests PASS, holdout validation PASS, hashes/statistics старого эксперимента PASS. Hashes scientific code/prompt/data/weights, schedule, hardware, config, raw responses, usage, latency, error logs и resource samples сохраняются в новом каталоге с фактической датой 02.10.2026. Секреты не публикуются. После freeze settings не меняются; bugs/partial run раскрываются, повтор не запускается автоматически. Ручная таблица30examples и bootstrap/plots создаются после единственного run без повторных provider вызовов.

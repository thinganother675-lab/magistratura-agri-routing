# Протокол нового независимого эксперимента

01.10.2026. **DRAFT / NOT FROZEN / FINAL NOT RUN.** Это проект протокола. Исторический `data/protocol_frozen.json` и старые результаты test90 остаются неизменными. Локальные прогоны HOME PC относятся к development.

## Выбор моделей и настройки

Окончательная локальная модель **не выбрана**. GPT-OSS 20B Q8_0 получил 28/36 на первом расширенном DEV, однако повторная парная QA-проверка дала EN 4/6 и RU 2/6. Это показывает необходимость контролируемого повторного DEV, проверки перевода и устранения ошибок CLI. Qwen3.8 27B остаётся кандидатом с 25/36 и нулём ошибок транспорта/формата на этом срезе. Расширенный smoke всех 15 установленных текстовых LLM документируется отдельно.

После расширенного сравнения предварительный bilingual context reader — Gemma4 26B-A4B IQ4_NL_XL: paired EN4/6, RU5/6, как Qwen27, при p501.810 против3.268 s. Общий DEV36 Gemma21/36 ниже GPT28/36; это выбор под роль после tools, а не универсального победителя. Окончательный выбор зависит от controlled DEV и ручной проверки gold.

Для облачного сравнения планируется один `mercury-2.5` через Inception. Новый доступ и billing credential пока не проверены. Исторические облачные прогоны не повторяются ради leaderboard. Цены, проверенные 01.10.2026: $0.04/M input, $0.15/M output; cached discount в планировании не применяется. [Официальные модели и цены](https://docs.inceptionlabs.ai/get-started/models).

Предложенные настройки HTTP DEV: исходный `SYSTEM_PROMPT` из неизменённого `models.py`, temperature 0, seed 42 local, context 4096, parallel 1, max_tokens 512. Окончательные лимиты ответа и reasoning необходимо выбрать на DEV. Реальное отключение reasoning у GPT-OSS не подтверждено. `json_object` и, если доступна, фиксированная JSON schema проверяются до freeze. Native tool calling и самозаявленная confidence не заменяют валидатор.

В CLI temperature и max_tokens неизвестны. Поэтому CLI-результаты нельзя считать исполнением этих HTTP settings. Установленный сервер требует отдельного LM Studio token; HTTP inference с ним **NOT RUN**.

## Маршрутизация и детерминированные инструменты

Новая development policy v2 находится отдельно в `home_policy.py`; исторический router не изменён. Сначала выполняется исходный deterministic hard gate. При наличии context вызывается локальный reader и проверяется опора ответа на supplied context. Без context запрос сразу планируется к облаку: прежний verifier не умеет принять такой локальный ответ. Offline при отсутствии support возвращается ABSTAIN.

Проверка substring подтверждает только буквальную опору, а не factual correctness или calibrated confidence. Формулы GDD/VPD/ET₀/rain deficit остаются детерминированными. Открытый аналог Jev исследуется как отдельный typed decision baseline; его классификацию нельзя смешивать с generative QA correctness.

## Новая выборка

**Selected IDs: NOT ASSIGNED; selected n = 0; target n = 150.** Окончательная выборка не создаётся до готовности модели, prompts, scoring и routing. Предложенный состав: 40 QA, 30 numeric, 20 missing input, 20 tool selection, 20 rule, 20 compound. Из QA возможны 20 EN/RU source pairs; переводы одного источника считаются одной статистической группой. Это план, а не выполненный dataset.

В AgXQA осталось 35 неиспользованных paragraph groups. Отсутствие document identity не позволяет доказать независимость на уровне документа. Предпочтительны новые источники и независимо проверяемые примеры. Для synthetic cases сохраняются source, seed, генератор и явная synthetic label. Новые значения старых templates не означают semantic OOD. RU translation требует метода и статуса независимой проверки.

Перед freeze исключаются exact/near duplicates всех исторических splits и новых DEV probes. Ответы holdout не используются для настройки. До запуска сохраняются окончательные IDs и hashes.

## Сравнение и статистика

Основные политики: LOCAL ONLY, CLOUD ONLY, TOOLS + CLOUD, TOOLS → LOCAL → CLOUD. Offline оценивается отдельно. Если политики реконструируются из одной сохранённой пары local/cloud outputs, latency обязательно называется reconstructed. Выводы о live performance требуют реального последовательного исполнения политик по заранее выбранному порядку. Облако повторно не вызывается ради пересчёта статистики.

Сохраняются raw responses, ошибки, model ID/quantization, runtime, prompts, generation settings, request hashes, usage, latency, TTFT, tok/s, VRAM/RAM. Неизвестные значения остаются null. Ошибки входят в denominator.

Исходный scoring: action, strict span EM/token F1, exact labels, numeric tolerance 1% relative / 0.02 absolute и unit. Его ограничения раскрыты в `TOOL_VALIDATION_HOME_PC_RU.md`. Изменение scoring возможно только как новая версия до final. Таблица 20–40 final examples требует независимого ручного аудита; DEV-таблица не заменяет его.

Основной contrast — hybrid минус tools+cloud. Планируется paired group bootstrap, 5000 повторов, seed 20261001; группы отражают source paragraph, translated pair или controlled family. Wilson и McNemar при зависимых вариантах используются описательно. Отсутствие значимости не доказывает equivalence. Основные результаты: effect size и CI, category correctness, coverage, escalation/abstention, mean/p50/p95, reliability и cost.

**Предложенные критерии, ещё не frozen:** lower paired 95% CI качества ≥ −5 п.п.; сокращение cloud calls ≥ 10 п.п. от всех запросов относительно tools+cloud; upper CI прироста critical errors ≤ 0; p95 end-to-end ≤ 10 s. Это исследовательские planning choices, а не агрономические стандарты. N=150 может оказаться недостаточным для точной noninferiority оценки; неопределённость должна быть показана.

## Стоимость и порядок запуска

Для 150 cloud requests по 6000 input + 512 output tokens плановая оценка — **$0.04752**; DEV 36 при том же допущении — **$0.0114048**. Это расчёт по указанным лимитам и ценам, не счёт. При других settings estimate пересчитывается. Предлагается guard $1/run и отсутствие автоматических оплачиваемых retries. Электричество и амортизация GPU не измерены и не объявляются бесплатными.

Порядок: controlled HTTP smoke; небольшой paired cloud DEV pilot; окончательный выбор модели и настроек; проверка источников и scoring; создание независимой выборки; запись IDs/hashes; реальный freeze с timestamp **до** выполнения; один final run без последующей настройки по его ответам.

`experiments/PROTOCOL_FREEZE_2026-10-01.md` сейчас содержит только статус NOT FROZEN. Имя файла не делает протокол зарегистрированным или выполненным.

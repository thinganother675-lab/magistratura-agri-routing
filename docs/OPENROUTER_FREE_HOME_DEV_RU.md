# OpenRouter free: HOME DEV, 1 октября 2026

**Inference NOT RUN: ошибка авторизации HTTP 401.** Публичный каталог доступен (HTTP 200): snapshot содержит 464 модели, из них 17 явных идентификаторов `:free` с нулевыми ценами prompt и completion. Наличие значения в `.env` не доказывает действительность API-ключа.

Реальный предпрогон `results/20261001_200747Z_615768b8_openrouter_free/`: проверка `GET /api/v1/key` вернула 401, первый `POST /api/v1/chat/completions` для `nvidia/nemotron-3-super-120b-a12b:free` также вернул 401. После этого выполнение остановилось. Успешных генераций 0, токены провайдером не сообщены, качество **N/A**, TTFT и tok/s **UNKNOWN**, задержка ошибочного HTTP-запроса 206.08 мс не является задержкой инференции. Не было повторов, платного fallback, смены ключа или динамического маршрутизатора.

| Предварительно выбранный точный ID из каталога | Научная роль | Цена prompt / completion | Статус |
|---|---|---:|---|
| `nvidia/nemotron-3-super-120b-a12b:free` | Более крупный общий облачный ориентир, JSON schema | $0 / $0 | POST 401; генерация NOT RUN |
| `google/gemma-4-26b-a4b-it:free` | Проверка практического локального кандидата у удалённого провайдера | $0 / $0 | NOT RUN |
| `qwen/qwen3.8-27b:free` | Второй локальный checkpoint как облачный ориентир | $0 / $0 | NOT RUN |

Размеры/квантизация серверных весов, серверные RAM/VRAM и GPU offload **UNKNOWN / N/A**. Совпадение названия checkpoint с локальным не означает совпадение квантизации, шаблона или производительности. Не использовались coder-модели, image-generation, TTS и uncensored варианты; все payload содержат только текст аграрного DEV-набора.

После исправления авторизации предусмотрен сначала пилот из трёх уже выбранных DEV12 случаев (EN extractive QA, RU missing-data, EN numerical); при отсутствии API/JSON ошибок — оставшиеся девять без повторения пилота. Набор `choose_samples(12)` тот же, что у HOME benchmark: шесть категорий по два случая, пять RU и семь EN. Все QA здесь EN; это не сбалансированный двуязычный QA-тест. Используются неизменные `SYSTEM_PROMPT`, `public_request`, parser и scoring проекта. Ответы и метки сохраняются локально, но не передаются в API. Это development-only диагностика, не новый независимый holdout.

В каждом запросе закреплены один точный catalog ID, temperature=0, max_tokens=512, stream=false, provider.allow_fallbacks=false, require_parameters=true и max_price={prompt:0,completion:0,request:0}. Нет массива fallback models, plugins, web-search, tools/MCP или paid retry. Если каталог сообщает `response_format` и `structured_outputs`, запрашивается strict JSON schema; иначе JSON обеспечивается только prompt и в результатах помечается grammar NONE. Seed=0 передаётся лишь при заявленной поддержке; reasoning.enabled=false — при поддержке reasoning. Эти возможности проверены по [официальным structured-output docs](https://openrouter.ai/docs/guides/features/structured-outputs) и [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection). Поддержка в каталоге сама по себе не подтверждает успешный ответ: сейчас авторизация не позволила проверить параметры.

Согласно [официальным правилам `:free`](https://openrouter.ai/docs/guides/routing/model-variants/free), вариант должен реально присутствовать в каталоге; суффикс нельзя добавлять к произвольной платной модели. [Документация лимитов](https://openrouter.ai/docs/api_reference/limits) рекомендует проверять daily free request counter через `/api/v1/key`. Здесь он **UNKNOWN** из-за 401. Между стартами запросов предусмотрено минимум 3.1 с, но численный RPM лимит на этом аккаунте пока не измерен. На 401/403/429 и любые другие HTTP-ошибки runner останавливается. Новая версия runner после этого пилота останавливается уже на отклонённой проверке авторизации, до POST.

Расчётная token-price стоимость бесплатного варианта — $0 по явным ценам каталога; **фактическое списание UNKNOWN**, invoice и response usage.cost отсутствуют. Runner сохраняет actual cost=0 только если провайдер явно вернул ноль. Любое ненулевое reported cost вызывает остановку. Ключ получен через allowlist `project_env:openrouter_api_key`, используется только внутри Authorization и не выводится/не хешируется/не сохраняется. В артефактах нет заголовков авторизации; response strings дополнительно проходят exact-value redaction.

Политики отдельных провайдеров могут различаться; [официальная страница privacy](https://openrouter.ai/docs/guides/privacy/provider-logging) описывает отдельные правила обучения на данных, логирования и хранения для free endpoints. Настройки аккаунта не изменялись. Планируемые payload содержат уже публичные benchmark тексты, а не личные документы или секреты.

Для продолжения требуется действующий OpenRouter API-ключ, сохранённый локально под `OPENROUTER_API_KEY` или `openrouter_api_key` в игнорируемой `.env`, либо восстановленная авторизация/доступ аккаунта. Значение ключа в чат передавать не требуется. Проверка `/api/v1/key` должна вернуть HTTP 200. Команда ниже создаёт новый каталог и при успешной проверке делает до 12 бесплатных запросов:

```powershell
.\.venv\Scripts\python.exe scripts/home_openrouter_benchmark.py --models nvidia/nemotron-3-super-120b-a12b:free
```

Новый runner: `scripts/home_openrouter_benchmark.py`; mock-проверки: `tests/test_home_openrouter_benchmark.py`. Измеренных сравнений OpenRouter с локальными моделями пока нет. Исторический Mercury-эксперимент, frozen core и final holdout не менялись.

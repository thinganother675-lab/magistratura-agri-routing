# OpenRouter: актуальный скрининг 21 моделей — 02.10.2026

## Фактический итог

**Заблокировано на проверке доступа.** Все 21 названия сопоставлены с точными ID официального каталога. По опубликованным ценам разрешены 18 текстовых кандидатов; фактически попытки сделаны для двух, остальные 16 **NOT RUN**. Две Lyria платны за музыкальный результат и исключены; Content Safety — классификатор, исключён из общей генеративной оценки.

**3 completion-попытки, 0 генераций, 0 полных DEV-бенчмарков.** Ошибки всех версий сохранены: Ling/Novita с management-ключом → HTTP 401; Ling/Novita с обычным ключом лимита $0 → HTTP 403; отдельно разрешённый connectivity-only LFM/Liquid → HTTP 404. Нулевых ответов нельзя превращать в оценку качества модели. Задержки 0.260/0.145/0.099 с — время отказа, не время inference.

## Ключи, приватность и установленные причины

Исходный `openrouter_api_key_2` — management/provisioning-ключ. Эти флаги подтверждены `GET /key`; [официальная документация](https://openrouter.ai/docs/guides/overview/auth/management-api-keys) исключает его использование для completion. Это объясняет исходный HTTP 401.

По разрешённой настройке создан **один** обычный inference-ключ в том же аккаунте через официальный `POST /keys` (HTTP 201), только в игнорируемом `.env`: `OPENROUTER_INFERENCE_KEY_ZERO_20261002`. Исходный ключ и его байты сохранены. Подтверждены `is_management_key=false`, `is_provisioning_key=false`, `limit=0`, `limit_remaining=0`, `include_byok_in_limit=true`, отсутствие сброса лимита, срок до 09.10.2026 23:59:59 UTC. Значения, префиксы, fingerprint и creator ID в артефакты не записаны. [API создания ключа](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key).

**Точная причина HTTP 403 для Ling с обычным ключом UNKNOWN**: исходный безопасный runner сохранил код ошибки, но не её тело. Валидный `GET /key` не доказывает разрешение inference. [Документация ошибок](https://openrouter.ai/docs/api/reference/errors-and-debugging) допускает для 403 ограничения прав, guardrail и moderation.

**Причина HTTP 404 отдельного LFM-запроса подтверждена** очищенным ответом сервиса:

> 0 endpoints out of 1 requested are available matching your guardrail restrictions and data policy.
> Free model training violation (account settings): 1 endpoint excluded.
> ZDR violation (account settings): 1 endpoint excluded.

Это доказательство несовместимости данного free endpoint с текущими настройками аккаунта. Другие 16 текстовых моделей не вызывались; им не приписываются измеренные HTTP-ошибки. Публичный `GET /endpoints/zdr` получен отдельно: наличие endpoint в списке ZDR не гарантирует доступ текущего аккаунта и согласие на условия free-моделей. Например, Ling/Novita в списке есть, но фактический запрос получил 403. [ZDR и фильтрация данных](https://openrouter.ai/docs/guides/features/zdr), [ограничения guardrail](https://openrouter.ai/docs/guides/features/guardrails/overview).

Настройки приватности, обучение на данных, ZDR, денежный лимит и аккаунт **не изменены**. Платных fallback, пополнения, ротации ключей ради обхода квоты и повторов нет. Дополнительный ключ исправил тип аутентификации, а не создал новую квоту.

## Актуальная матрица

| Запрошенная модель | Точный ID | Закреплённый endpoint | Актуальный статус | Попытки / ответы |
|---|---|---|---|---:|
| inclusionAI: Ling 3.1 Flash | `inclusionai/ling-3.1-flash` | novita | BLOCKED_ACCESS_HTTP401_AND_HTTP403 | 2 / 0 |
| Apodex: Apodex 1.1 Mini (free) | `apodex/apodex-1.1-mini:free` | novita/bf16 | NOT_RUN | 0 / 0 |
| Space Bunny Alpha | `stealth/space-bunny-alpha` | stealth | NOT_RUN | 0 / 0 |
| inclusionAI: Ling 3.0 Flash Sante (free) | `inclusionai/ling-3.0-flash-sante:free` | novita | NOT_RUN | 0 / 0 |
| Qwen: Qwen3.8 27B (free) | `qwen/qwen3.8-27b:free` | modelrun/fp4 | NOT_RUN | 0 / 0 |
| Dots Studio: Dots3-Note Preview (free) | `dots-studio/dots-3-note-preview:free` | atlas-cloud/fp8 | NOT_RUN | 0 / 0 |
| LiquidAI: LFM2.5-2.6B (free) | `liquid/lfm-2.5-2.6b:free` | liquid/fp8 | BLOCKED_ACCOUNT_PRIVACY_DIAGNOSTIC_HTTP404 | 1 / 0 |
| NVIDIA: Nemotron 3.5 Lightning (free) | `nvidia/nemotron-3.5-lightning:free` | nvidia/nvfp4 | NOT_RUN | 0 / 0 |
| Thinking Machines: Inkling Small (free) | `thinkingmachines/inkling-small:free` | thinkingmachines/nvfp4 | NOT_RUN | 0 / 0 |
| Poolside: Laguna S 2.1 (free) | `poolside/laguna-s-2.1:free` | poolside/fp4 | NOT_RUN | 0 / 0 |
| Thinking Machines: Inkling (free) | `thinkingmachines/inkling:free` | thinkingmachines/nvfp4 | NOT_RUN | 0 / 0 |
| Poolside: Laguna XS 2.1 (free) | `poolside/laguna-xs-2.1:free` | poolside/fp8 | NOT_RUN | 0 / 0 |
| Cohere: North Mini Code (free) | `cohere/north-mini-code:free` | cohere | NOT_RUN | 0 / 0 |
| NVIDIA: Nemotron 3.5 Content Safety (free) | `nvidia/nemotron-3.5-content-safety:free` | — | SPECIALIZED_NOT_COMPARABLE | 0 / 0 |
| NVIDIA: Nemotron 3 Ultra (free) | `nvidia/nemotron-3-ultra-550b-a55b:free` | nvidia | NOT_RUN | 0 / 0 |
| NVIDIA: Nemotron 3 Nano Omni (free) | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | nvidia | NOT_RUN | 0 / 0 |
| Google: Gemma 4 26B A4B (free) | `google/gemma-4-26b-a4b-it:free` | google-ai-studio | NOT_RUN | 0 / 0 |
| Google: Gemma 4 31B (free) | `google/gemma-4-31b-it:free` | google-ai-studio | NOT_RUN | 0 / 0 |
| Google: Lyria 3 Pro Preview | `google/lyria-3-pro-preview` | — | PAID_NOT_AUTHORIZED | 0 / 0 |
| Google: Lyria 3 Clip Preview | `google/lyria-3-clip-preview` | — | PAID_NOT_AUTHORIZED | 0 / 0 |
| NVIDIA: Nemotron 3 Super (free) | `nvidia/nemotron-3-super-120b-a12b:free` | nvidia | NOT_RUN | 0 / 0 |


Для `NOT_RUN` общий prerequisite скрининга заблокирован; собственная совместимость модели UNKNOWN. Полные цены, модальности, context length, объявленная квантовка endpoint, список версий попыток и ресурсные поля сохранены в `current_21_model_matrix.json`. Реальная удалённая квантовка/веса/RAM/VRAM/GPU-offload UNKNOWN. Технический паспорт endpoint не является измерением этих ресурсов.

Lyria Pro имеет опубликованную цену **$0.08 за песню**, Lyria Clip — **$0.04 за результат** в описании каталога, даже когда token pricing равно нулю. Ни одного музыкального запроса не было. Анонимная Space Bunny и Dots preview обозначены exploratory; кодовые Laguna/North и медицинская Ling Sante отделены по scope. Ни одна из них не оценивалась по содержанию ответов.

## Квота, токены и внешние запросы

Последний фактический `GET /key`: общая бесплатная дневная квота **50**, использовано **0**, осталось **50**; лимит ключа **$0**, aggregate usage **$0**. [Квоты действуют глобально](https://openrouter.ai/docs/api/reference/limits), а не обновляются с новым ключом.

Итого ветка: **111 внешних запросов** = **107 metadata GET + 1 setup POST + 3 completion POST**. Последний публичный ZDR-каталог добавил один metadata GET к ранее зафиксированным 110. Стоимость, input/output tokens отдельных неуспешных completion-запросов **UNKNOWN**, покрытие **0/3**. Нулевой aggregate usage не подменяет отсутствующую детализацию invoice. TTFT, tok/s, качество, генеративные p50/p95 и структурная надёжность **NOT RUN**.

## Протокол и сохранённые артефакты

Скрининг development-only: общий старый DEV12 selector, первый extractive EN пример и затем RU missing-input, только публичные input/context/inputs; gold, категория и expected route в провайдерный payload не передавались. План: сначала все 18 endpoint по одному примеру, затем 14 общих текстовых по второму, максимум две стабильные модели по 9 различным DEV-примерам. Нормальный максимум — 46 запросов; жёсткий cap49 и один резерв глобальной квоты. До этого этапа фактические запуски не дошли. Новый confirmatory holdout **NOT RUN**.

temperature=0, max_tokens=512, concurrency=1, минимум 3.1 с между стартами, timeout45 с, stream=false. Модель/endpoint закреплены, allow_fallbacks=false, require_parameters=true, опубликованные monetary-компоненты строго равны нулю; max_price prompt/completion/request/image=0. Структурный формат зависит от опубликованной поддержки endpoint и записан в точном payload. HTTP 401/403/402/429 останавливает свою версию после одной ошибки. В отдельно разрешённом диагностическом запуске был ровно один фиксированный LFM POST, без автоматического перехода между моделями.

**24 профильных теста PASS** перед ordinary-key запуском: поиск точных ID и credential sources, запрет paid siblings/unknown prices/media fees, сохранение приватности, исключение gold из payload, схема JSON, остановки на ключевых ошибках. Это проверяет harness, не доказывает успешную генерацию.

- Исходная metadata-фаза: `results/20261002_172052Z_682669ff_openrouter21_metadata`.
- Management-key401: `results/20261002_181544Z_454d35c7_openrouter21_screen`, исходный driver сохранён и SHA256 совпадает с run config.
- Создание ordinary-key и checkpoint: `results/20261002_182623Z_openrouter_zero_child_setup`.
- Свежий каталог ordinary-key: `results/20261002_182916Z_ef105dbe_openrouter21_metadata`.
- Ordinary-key403: `results/20261002_183356Z_32261f33_openrouter21_screen`, driver_executed.py совпадает с run config SHA256.
- Однократный LFM404 diagnostic, safe error, ZDR-каталог и текущая общая матрица: `results/20261002_183639Z_openrouter_zero_diagnostic`.

Старые raw/config/summary и исторические научные результаты неизменны. Текущий документ является сводным статусом; первоначальные интерпретации сохранены в отдельных versioned JSON и не подменяют его.

## Точное условие продолжения

1. Проверить [OpenRouter Privacy](https://openrouter.ai/settings/privacy) и применимые права/guardrail. Для LFM сервис подтвердил блокирующие free-training и ZDR условия; для Ling403 точная причина всё ещё неизвестна.
2. Явно решить, допустима ли передача публичных/синтетических DEV-примеров выбранному бесплатному провайдеру с его политикой обработки данных. Настройки не ослаблять автоматически. Если приватность должна остаться строгой, использовать совместимый endpoint только после подтверждения доступа или продолжать локальные/другие уже доступные провайдеры.
3. Сохранить денежный лимит **$0**; не покупать credits, не повышать cap, не менять аккаунт/ключи для обхода лимитов и не переходить на paid sibling.
4. Перед новым запуском создать отдельный протокол/metadata/claim и получить новое изолированное окно. Уже использованные claims не запускать повторно; все три ошибки остаются в журнале.

Текущая ветка OpenRouter остановлена, окно освобождено для локальных работ. Лучший OpenRouter-кандидат, качество русской подвыборки и Pareto-сравнение **NOT RUN**.

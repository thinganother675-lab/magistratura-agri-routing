# OpenRouter после изменения приватности — 3 октября 2026

**PARTIAL:** каталог и ограниченный DEV screen завершены; часть endpoints недоступна. Исторический Mercury/HOME150 не заменён. Никаких изменений аккаунта/ключей/лимитов/приватности runner не выполнял.

21/21 FOUND; 7 разных моделей получили completion attempt, 4 вернули генерацию. 3 отдельных отказа, 9 текстовых кандидатов исключены filtered catalogue, 3 SKIPPED (2 paid music, 1 classifier), 2 eligible NOT RUN по ограниченному плану. Три новых run IDs: 20261003_044632Z_cba2c92c_openrouter_retry, 20261003_044847Z_ea685d74_openrouter_retry, 20261003_045116Z_54ff112b_openrouter_retry. Всего34 completion attempts,31 successful generations,183 внешних requests (149 metadata GETs); retries0.

## Причины прежних и новых отказов

- Старый401: `openrouter_api_key_2` остаётся management/provisioning; официальная документация исключает inference этим типом. Выбран уже существующий ordinary child того же аккаунта: limit0, include_byok_in_limit=true, usage0, expiry09.10; новый ключ не создавался.
- Ling3.1 новый403: точное очищенное сообщение `Key limit exceeded (total limit)`. Это уточняет старый403, тело которого не было сохранено. При этом публичные model/endpoint token-price fields нулевые. Причина внутренней проверки/резерва стоимости alias сервисом не раскрыта; лимит не повышался.
- СтарыйLFM404: одновременно Free model training и ZDR exclusions. Сейчас LFM отсутствует в authenticated `/models/user`, поэтому повторное inference NOT RUN. Точные значения переключателей account privacy API не раскрывает; нельзя утверждать, что все исключения сняты.
- Apodex400: endpoint metadata заявляет structured_outputs, но provider body говорит json_schema unsupported, supported json_object. Параметры не менялись для повторного тюнинга; отдельная будущая совместимость допустима как новая DEV-версия.
- Gemma26 429: provider identifies `upstream_provider_shared_pool`; не account-wide exhausted quota. Автоповторов, BYOK/paid fallback нет. Этот отказ не блокировал отдельно объявленный screen других доступных free моделей.

[Management keys](https://openrouter.ai/docs/guides/overview/auth/management-api-keys), [provider price/pinning](https://openrouter.ai/docs/guides/routing/provider-selection), [ZDR](https://openrouter.ai/docs/guides/features/zdr), [filtered catalog](https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails).

## Общие девять DEV задач

| Model | Correct/9 | Median seconds | Input/output tokens | Provider | Cost USD |
|---|---:|---:|---:|---|---:|
| inclusionai/ling-3.0-flash-sante:free | 4/9 | 1.163 | 4343/358 | Novita | 0 |
| qwen/qwen3.8-27b:free | 5/9 | 0.673 | 4205/272 | ModelRun | 0 |
| dots-studio/dots-3-note-preview:free | 4/9 | 1.763 | 4077/309 | AtlasCloud | 0 |

27/27 HTTP200,27/27 exact JSON schema,27/27 reported cost0; key usage до/после0. Нулевая стоимость общего screen подтверждена API; отказавшие попытки имеют UNKNOWN individual usage/cost, не подставляются как измеренный0. Zero-cap/provider price guards соблюдены. Макс512tokens,temperature0,parallelism1; nonstream end-to-end latency, TTFT/backend TPS UNKNOWN. Remote version/quantization UNKNOWN.

Это9 наблюдавшихся DEV задач с прежним strict exact scorer: ошибки QA-span и numeric могут снижать score без полной человеческой семантической оценки. Scorer v2 не использовался. Новые ответы не являются confirmatory holdout; качество по9 нельзя обобщать. Два успешных connectivity probes Ling не объединяются с9 для ranking. Qwen имеет лучшие наблюдаемые качество/latency из этой тройки, однако Pareto superiority на широком workload не установлена. Dots preview identity нестабильна. Численные/лексические source groups общие, независимая статистика здесь не рассчитывалась.

## Все запрошенные модели

| Display name / current ID | Status | Privacy | HTTP |
|---|---|---|---|
| inclusionAI: Ling 3.1 Flash / `inclusionai/ling-3.1-flash` | TESTED_BLOCKED | ELIGIBLE_FILTERED_CATALOG | 403 |
| Apodex: Apodex 1.1 Mini (free) / `apodex/apodex-1.1-mini:free` | TESTED_BLOCKED | ELIGIBLE_FILTERED_CATALOG | 400 |
| Space Bunny Alpha / `stealth/space-bunny-alpha` | NOT_RUN_BOUNDED_SCREEN | ELIGIBLE_FILTERED_CATALOG | NOT RUN |
| inclusionAI: Ling 3.0 Flash Sante (free) / `inclusionai/ling-3.0-flash-sante:free` | TESTED_OK | ELIGIBLE_FILTERED_CATALOG | 200/200/200/200/200/200/200/200/200/200/200 |
| Qwen: Qwen3.8 27B (free) / `qwen/qwen3.8-27b:free` | TESTED_OK | ELIGIBLE_FILTERED_CATALOG | 200/200/200/200/200/200/200/200/200 |
| Dots Studio: Dots3-Note Preview (free) / `dots-studio/dots-3-note-preview:free` | TESTED_OK | ELIGIBLE_FILTERED_CATALOG | 200/200/200/200/200/200/200/200/200/200 |
| LiquidAI: LFM2.5-2.6B (free) / `liquid/lfm-2.5-2.6b:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| NVIDIA: Nemotron 3.5 Lightning (free) / `nvidia/nemotron-3.5-lightning:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Thinking Machines: Inkling Small (free) / `thinkingmachines/inkling-small:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Poolside: Laguna S 2.1 (free) / `poolside/laguna-s-2.1:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Thinking Machines: Inkling (free) / `thinkingmachines/inkling:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Poolside: Laguna XS 2.1 (free) / `poolside/laguna-xs-2.1:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Cohere: North Mini Code (free) / `cohere/north-mini-code:free` | TESTED_OK | ELIGIBLE_FILTERED_CATALOG | 200 |
| NVIDIA: Nemotron 3.5 Content Safety (free) / `nvidia/nemotron-3.5-content-safety:free` | SKIPPED | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| NVIDIA: Nemotron 3 Ultra (free) / `nvidia/nemotron-3-ultra-550b-a55b:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| NVIDIA: Nemotron 3 Nano Omni (free) / `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |
| Google: Gemma 4 26B A4B (free) / `google/gemma-4-26b-a4b-it:free` | TESTED_BLOCKED | ELIGIBLE_FILTERED_CATALOG | 429 |
| Google: Gemma 4 31B (free) / `google/gemma-4-31b-it:free` | NOT_RUN_BOUNDED_SCREEN | ELIGIBLE_FILTERED_CATALOG | NOT RUN |
| Google: Lyria 3 Pro Preview / `google/lyria-3-pro-preview` | SKIPPED | ELIGIBLE_FILTERED_CATALOG | NOT RUN |
| Google: Lyria 3 Clip Preview / `google/lyria-3-clip-preview` | SKIPPED | ELIGIBLE_FILTERED_CATALOG | NOT RUN |
| NVIDIA: Nemotron 3 Super (free) / `nvidia/nemotron-3-super-120b-a12b:free` | PRIVACY_BLOCKED_NOT_RUN | EXCLUDED_FILTERED_CATALOG | NOT RUN |

Точные modalities,context,provider,prices,reason и числа попыток: [catalogue21.csv](../results/openrouter_integrated_20261003/catalogue21.csv), [summary](../results/openrouter_integrated_20261003/summary.json). Raw response/error metadata и request payloads сохраняются PRIVATE в трёх новых run folders; ключи и account key IDs очищены. Полная privacy модель не выводится из наличия модели в filtered catalog: доступность endpoint проверяется ответом. Первые два запуска диагностические; их отдельные code snapshots не были зафиксированы, ограничение записано в provenance. Shared DEV executed-source snapshot сохранён.

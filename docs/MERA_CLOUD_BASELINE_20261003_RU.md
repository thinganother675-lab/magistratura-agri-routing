# Облачная базовая модель MERA: ограниченная диагностика DEV

Дата: 3 октября 2026. Серии `20261003_cloud_baseline_7c019d4a` и `20261003_cloud_budget_only_c1184a27`. Все результаты имеют статус **DEV**. Частный TEST, MERA submissions и публикация не выполнялись. Существующие HOME150 и прежние Mercury/OpenRouter результаты сохранены.

**Предварительная direct cloud reference — Mercury2.5 instant512, temperature.5; PRIVATE_TEST_READY=NO.** Одна последующая проверка бюджета прошла operational DEV12 gate; профиль выбран до расширения по пригодности исполнения, после чего сохранены все60 попыток. На полном screen появились4 length failures, поэтому финальная пригодность протокола для TEST не установлена. Эти результаты нельзя трактовать как окончательный уровень агрономических знаний модели или подтверждение сохранения качества каскада.

## Что проверили

Прежний Mercury2 medium128 DEV60 дал 56 пустых ответов, завершившихся по ограничению длины. Прежний instant256 дал16/60 по старому strict parser и корректные буквы60/60, но другой prompt, temperature.75 и отдельный профиль. HOME Mercury2.5 DEV36 с27/36 относится к иному набору и composite scorer; его нельзя переносить в ruTXTAgroBench качество.

Текущая официальная [документация API Inception](https://docs.inceptionlabs.ai/api-reference/chat/create-a-chat-completion) указывает temperature.5–1 и замену значений вне диапазона на default; у Mercury2 это.75, у Mercury2.5 —1. `max_completion_tokens` включает скрытые reasoning и видимые токены. [Reasoning efforts](https://docs.inceptionlabs.ai/capabilities/reasoning-efforts) применимы к обоим моделям: instant/low/medium/high; instant означает наименьшую задержку, а не запрет reasoning. JSON schema описана в [Structured outputs](https://docs.inceptionlabs.ai/capabilities/structured-outputs).

До новых запросов сохранены code snapshots, source hashes, immutable DEV60 IDs и консервативный reserve24 попыток **$0.01490898**, общий diagnostic cap **$0.02**. DEV12 выбран как равномерные индексы0,5,…55 того же общего DEV60, без gold input. System instruction и JSON choices контракт совпадают с новым local screen. Mercury использует temperature.5 вместо local0, nonstream без seed/top_p/logprobs (эти параметры не заявлены текущей API reference). Различия записаны до вызовов. Модели запускались последовательно; cloud выполнялся в отдельное окно, когда локальные модели были выгружены.

| Профиль | Попытки / план | HTTP responses / завершено без ошибки | STRICT_SET_EM | STRICT_SET_F1 | length / timeout | p50 / p95, с | known input / output | known estimate, USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mercury2.5 instant256, temperature.5 | 8/12 | 7/5 | 4/8 =50.00% на частичных8 | .500000 | 2/1 | 1.356/39.816 | 1845/1190 | .00025230 +1 UNKNOWN |
| Mercury2 medium1024, temperature.5 | 12/12 | 12/10 | 4/12 =33.33% | .587302 | 2/0 | 1.638/2.898 | 5638/6155 | .00602575 |

Ошибки/length входят в знаменатель и дают0. Частичные8 нельзя ранжировать против12 или полного DEV60. Для первого профиля4/12=.333333 — только нижняя граница покрытия планового12, а не полный score. Provider responses19, attempts20, корректно завершённые responses15; **known token estimate $0.00627805 плюс неизвестная стоимость одного ReadTimeout**, без invoice. Paid retries0. Timeout не доказывает отсутствие тарификации.

## Причина и предел диагностики

Mercury2.5 instant256: оба length ответа пустые, у каждого243 completion tokens и243 reasoning tokens. Сумма reasoning по семи известным responses1120/1190 completion tokens. Mercury2 medium1024: два length ответа содержат975 и991 completion tokens, все они reported reasoning; у первого при этом присутствовал частичный JSON. В целом6014/6155 completion tokens reported reasoning. Таким образом, исчерпание общего бюджета скрытыми reasoning подтверждено для четырёх length случаев. Успешные outputs соблюдали небольшой JSON контракт; устойчивое игнорирование JSON schema этим не установлено.

ReadTimeout Mercury2.5 — отдельный сетевой/provider отказ, его причина не установлена. Замена модели, reasoning effort и бюджета одновременно не изолирует влияние каждого параметра на точность. Эта диагностика объясняет output-budget failure, но не доказывает, что Mercury непригоден как семейство, или что больший лимит автоматически даст лучшие агрономические знания.

Первая frozen версия runner считала HTTP response с length успешным и могла дать credit частичному JSON. Это выявлено при независимой проверке. Исходные raw, manifests и source snapshots не переписаны; **append-only `diagnostic_corrected.json`** устанавливает length→IncompleteCompletion,0 score, успешное-completion accounting. Четыре исправленных ID перечислены без содержания вопросов. Все научные числа таблицы используют corrected overlay; прежние summary сохранены как executed evidence. Новая версия runner содержит тот же guard до будущих вызовов.

## Одна дополнительная проверка бюджета и общий DEV60

Первые два профиля не прошли gate: все12 error-free completions, известный usage и минимум10 valid option sets; их extension48 не выполнялся. После завершения локального Stage1 в отдельное эксклюзивное cloud окно заранее объявлена **ровно одна** дополнительная конфигурация: Mercury2.5 instant512, temperature.5. От instant256 изменён только `max_completion_tokens`:256→512, остальные параметры/prompt/JSON/DEV12 IDs совпадают. Fresh plan `results/20261003_cloud_budget_only_c1184a27/plan_frozen.json`, код `a6627cf6d1d892576040db7d4caf4eb9302ac8c1`, reserve12 **$0.00164328**, cap диагностического этапа$0.02 и общего baseline$0.10.

DEV12:12/12 stop responses,12 valid sets,12 known usage; EM10/12=.833333,F1=.888889. Профиль **выбран по operational gate до extension**, а не по наибольшей точности; `cloud_primary_frozen.json` сохраняет время и причину. Затем ровно48 других IDs того же DEV60, без повторов первых12:

| Mercury2.5 instant512/.5 | Результат общего DEV60 |
|---|---:|
| Попытки / HTTP responses / завершено без ошибки | 60 / 60 /56 |
| STRICT_SET_EM | 31/59 =52.54% |
| STRICT_SET_F1 | .657627 |
| Reference issue | 1 исходный Cyrillic gold, не исправлен |
| Invalid / length / timeout | 4 /4 /0 |
| Input / output tokens | 15855 /9720 |
| Known uncached token estimate | $0.00209220 |

Все4 length outputs получают0 независимо от частично разбираемого текста. Main strict denominator59; conservative all-N31/60=51.67% — нижняя граница покрытия, не догадка о неправильном gold. Полный screen показывает, что успех маленького compatibility probe не гарантировал error-free coverage60:6.67% попыток усечены. Размер бюджета влияет на доступность видимого ответа, но stochastic generation/no seed и отсутствие повторов не дают независимой причинной оценки прироста качества. Никаких дальнейших Mercury настроек, full293 cloud или частного TEST не выполнялось.

Исходный extension48 manifest помечен `COMPLETE` по покрытию попыток, хотя44/48 завершены без ошибки. Это сохранённый недостаток метки, а не полная успешность модели. Новый `manifest_status_correction.json` явно устанавливает для общего60 статус **ATTEMPT_COVERAGE_COMPLETE_WITH_FAILURES**,56/60 error-free; исходный manifest и правильные zero-score метрики не переписаны. Будущий runner различает эти состояния.

Итого новых cloud generation attempts **80**, HTTP responses **79**, успешно завершённые responses **71**. Known estimate **$0.00837025 плюс один UNKNOWN ReadTimeout**. Probe12 профиля512 уже входят в его common60; их нельзя повторно складывать. TTFT/backendtok/s/cloudlogprobs UNKNOWN. 512 baseline legitimate direct model identity подтверждалась на каждом response, backend weights revision provider не раскрывает. Вариант рекомендован как **PROVISIONAL_DEV_REFERENCE_NOT_PRIVATE_TEST_READY**; решение о финальном бюджете и приёме ошибок принимается авторами до TEST, новые настройки должны иметь отдельный frozen protocol.

## OpenRouter supplement: quota guard

Три точечных read-only GET3 октября08:38:33UTC: `/key`, authenticated `/models/user`, endpoints ровно `qwen/qwen3.8-27b:free`. Existing ordinary key: limit$0, includeBYOK=true, usage$0; account-filtered eligibility есть. Единственный endpoint: provider tag `modelrun/fp4`, quantizationFP4, canonical slug `qwen/qwen3.8-27b-20260814`, цены prompt/completion0. Однако дневная quota remaining**19** из50, used31. **NOT_RUN_FREE_QUOTA_GUARD:** нельзя закончить общий60 сегодня или использовать этот free quota как bounded2642 TEST primary. Generations0, изменения ключа/лимита/privacy0, paid fallback0. Raw remote weights revision UNKNOWN; canonical slug/FP4 — metadata provider, не независимый hash весов.

Primary cloud candidate **Mercury2.5 instant512/.5**, provisional и не окончательно утверждён для TEST. Mercury token-logprobs не измерялись, self-reported уверенность не запрашивалась. Новый saved DEV60 replay использует этот профиль вместе с текущими локальными predictions, включая четыре cloud errors с0score. Форматный fallback у качественных локальных моделей даёт тривиальное сохранение local-only результата, если valid outputs60/60; это не доказательство полезности confidence-routing или неухудшения на TEST. Реальной экономии cloud calls от replay0; latency/cost savings live не измерены. Full293 cascade качество неизвестно, поскольку cloud293 отсутствует.

Основные артефакты: `results/20261003_cloud_baseline_7c019d4a/{plan_frozen.json,diagnostic_corrected.json}`, исходные два `_probe12_manifest.json` и `_metrics.jsonl`; новая серия `results/20261003_cloud_budget_only_c1184a27`, combined60 и `cloud_development_analysis.json`. Новая provenance `manuscript/CLAIM_PROVENANCE_CLOUD_BASELINE_20261003.json`. Restricted raw: ignored `.runtime/mera/<run_id>`. Dataset status **USE_WITH_RESTRICTIONS**; вопросы/gold/provider text не распространяются. Для TEST нужно повторно проверить актуальную [таблицу цен](https://docs.inceptionlabs.ai/get-started/models): нынешняя Mercury2.5 цена содержит скидку, а токенная оценка не является invoice.

# Mercury 2.5: отдельный HOME DEV12

01.10.2026, начало 20:01 UTC. **DEVELOPMENT ONLY. Это не новый final holdout и не freeze протокола.** Исторические данные и шесть core modules сохранены.

Реальный direct Inception pilot: `results/20261001_200100Z_ef3cc471_mercurydev/`. Выбраны ровно те же 12 DEV ID через `choose_samples(12)`, что использует HOME local selector: по два запроса из каждой из шести категорий. Saved `samples_dev.json` позволяет сопоставить их с отдельно измеренным LM Studio API run. Этот этап сам не вызывал локальную модель; парная оценка и политики требуют соответствующих local outputs.

| Показатель | Результат |
|---|---:|
| Cloud attempts / сохранённых строк | 12 / 12 |
| Получено успешных HTTP responses | 11 |
| Task correctness, ошибки в denominator | 10/12 = 83.3% |
| Ошибки | 1 ReadTimeout |
| Known input / output tokens | 6 436 / 2 029 |
| Usage coverage | 11/12 input; 11/12 output |
| Known token-based cost estimate | $0.00056179 |
| Запросы с неизвестным usage/cost | 1 |
| Mean / p50 / p95 HTTP wall time | 6.590 / 1.769 / 28.660 s |

Первый запрос `controlled_compound_reasoning_6_0` завершился ReadTimeout после 60.848 s. Его не повторяли. Timeout не доказывает, что provider не получил или не тарифицировал запрос: полный расход неизвестен, invoice не получен. Латентность выше включает эту ошибку. Во второй QA задаче `agxqa_300` ответ не прошёл исходный strict span EM; остальные десять outputs correct по неизменённому scorer. Все 11 полученных responses указали model `mercury-2.5`.

| Категория | Correct / n |
|---|---:|
| Compound reasoning | 1/2 |
| Extractive QA | 1/2 |
| Missing data | 2/2 |
| Numeric | 2/2 |
| Rule interpretation | 2/2 |
| Tool selection | 2/2 |

Endpoint зафиксирован `https://api.inceptionlabs.ai/v1/chat/completions`, temperature 0, max_tokens 512, response_format json_object, reasoning_effort instant. Поля, отправленные client, сохранены в manifest; их фактическая реализация provider не считается отдельной валидацией. Seed облачного вызова не задавался. Paid retries — 0, максимум 12 calls, плановый budget guard $0.02. Плановая оценка при 6000 input + 512 output на запрос была $0.0038016; это не tokenizer ceiling или invoice.

На 01.10.2026 официальная таблица Mercury 2.5 показывала $0.04/M input и $0.15/M output; cached discount в оценке не применяется. [Официальные модели и цены Inception](https://docs.inceptionlabs.ai/get-started/models). Известная сумма считается только по сохранённому provider usage; отсутствующие показания не подменены нулём.

Credential source — **project_env:mercury_api_key**. Значения ключей, Authorization headers и account attribution не сохранялись. OpenRouter credential не используется как Mercury credential. Новый `home_config.py` распознаёт allowlisted aliases отдельно для local, Mercury, OpenRouter и Jev; исторический configured_models() не изменён.

До и после вызовов сверены hashes models.py, routing.py, evaluation.py, benchmark.py, tools.py, cli.py, benchmark.jsonl и protocol_frozen.json против исходного completed test manifest. Новый runner `scripts/home_cloud_pilot.py` создаёт отдельные timestamp directories и журналирует попытку до обращения к provider. Raw responses не перезаписываются.

Прогон воспроизводит программные настройки, но новый paid запуск создаёт новые ответы и расход. Для анализа готового результата достаточно сохранённых JSON; не повторять cloud calls ради пересчёта.

```powershell
# Только план: нет credentials/network calls или result directory.
.venv\Scripts\python.exe scripts\home_cloud_pilot.py --n 12 --plan-only
# Новый paid DEV run в новой директории, если исследовательский этап требует его.
.venv\Scripts\python.exe scripts\home_cloud_pilot.py --n 12 --execute
```

Meaningful mocked checks resolver/pilot boundaries прошли: 21 тест Mercury suite; вместе с отдельным API reporting suite root проверил 25 тестов. Проверены aliases precedence, отделение provider keys, call ceiling, plan-only, non-DEV/duplicate rejection, отсутствие paid retries, preservation неизвестного usage/cost, interruption journal, redaction и append-only run directories. Доказательство live API — только фактический DEV12 выше; тесты его не заменяют.

## Дополнение до общего DEV36 без повтора первых 12

В отдельной папке `results/20261001_200720Z_e2dad72a_mercurydev36/` сохранены только **24 новых вызова** и объединённая копия `combined_mercury_raw.jsonl` с 36 результатами в порядке исходного HOME selector. Первые 12 IDs, включая timeout, исключены из новых запросов. Parent manifest/raw/samples hashes зафиксированы и сверены после расширения; исходные файлы не менялись. Два pure mocked tests подтвердили ограничение 24 и пропуск parent IDs, включая ошибку, а также отказ при duplicate/mismatched samples.

| Показатель | Новые 24 | Объединённые 36 |
|---|---:|---:|
| Actual attempts / saved rows | 24 / 24 | 36 / 36 |
| Task correctness | 17/24 = 70.8% | 27/36 = 75.0% |
| Errors | 3 | 4 |
| Successful HTTP responses | 23 | 34 |
| Known input / output tokens | 13 383 / 4 434 | 19 819 / 6 463 |
| Input / output usage coverage | 23/24 | 34/36 |
| Known token-based estimate | $0.00120042 | $0.00176221 |
| Calls with UNKNOWN usage/cost | 1 | 2 |

Общие HTTP latency mean/p50/p95 — **4.981 / 1.697 / 17.359 s** с включением обеих timeout ошибок. Объединённый результат по категориям: compound 5/6, strict extractive QA 1/6, missing data 3/6, numeric 6/6, rule 6/6, tool selection 6/6. Этот DEV36 нужен для парного development анализа и не является независимым holdout.

Новое расширение добавило ReadTimeout для `agxqa_55` и две structured failures: ValueError для `controlled_missing_data_8_0` (поле answer содержит null вместо обязательной строки) и JSONDecodeError для `controlled_missing_data_7_2` (provider finish_reason length). Usage структурных failures сохранён и входит в известную сумму; timeout usage неизвестен. Errors входят в correctness denominator. Оценка полного billing неизвестна из-за двух timeouts; их не повторяли.

Плановая оценка новых 24 была $0.0076032 при budget $0.02. Настройки и direct provider не менялись. Шесть исторических core modules и frozen dataset/protocol снова проверены после расширения. `summary.json` отделяет new от combined, `analysis_metrics.json` содержит воспроизводимые latency/category агрегаты из raw. Не складывать combined cost повторно с parent cost: она уже включает сохранённый DEV12.

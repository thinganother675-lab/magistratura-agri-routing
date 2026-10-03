# Agro Route Lab

**Ресурсный этап, вечер 03.10.2026:** [Qwen9 vs Qwen27: системы](docs/QWEN9_VS_QWEN27_SYSTEMS_ANALYSIS_RU.md),
[парный DEV-анализ](docs/QWEN9_VS_QWEN27_DEV_ANALYSIS_20261003_RU.md),
[Study C](docs/STUDY_C_RESULTS_20261003_RU.md),
[subscription CLI baselines и effort](docs/CLI_PRODUCT_BASELINES_20261003_RU.md).
Qwen9 сохраняет 94% наблюдаемого EM Qwen27 (141/289 vs 150/289), а в отдельном
TELEMETRY40 native-профиле его p50 ниже в 5,338 раза. Qwen27 лучше в model-only
Study C; V1 отказ по RAM сохранён. Это DEV / systems characterization, не
подтверждённая non-inferiority. [Ограничения](docs/RESOURCE_SESSION_LIMITATIONS_20261003_RU.md),
[новый draft-протокол](experiments/next_resource_protocol_20261003.json) и
[source-bound claims](manuscript/CLAIM_PROVENANCE_RESOURCE_SESSION_20261003.json)
разделяют историческое качество, телеметрию, симуляцию и product harness.
[Единственный backup](docs/BACKUP_AGRICULTURAL_BENCHMARK_20261003_RU.md) пока NOT_READY.
MERA scorer WAITING_FOR_MAINTAINER; private TEST не запускался. Новый paid API
расход отсутствует; подписка обозначена SUBSCRIPTION_INCLUDED.
[Лист решений Дениса](docs/DENIS_DECISION_SHEET_20261003_RU.md) и
[пакет будущей редакции Claude](outputs/claude_paper_editor_package/README.md)
готовятся для совместного согласования; редактура/публикация не запускались.

**Следующий этап, 03.10.2026:** [разделение исследований A / B / C](docs/NEXT_RESEARCH_STAGE_20261003_RU.md).
HOME150 сохраняется замороженным. Новый агрономический эталон предпочтительно
берётся из экспертного ruTXTAgroBench; [аудит прав и метрик](docs/MERA_RUTXTAGROBENCH_AUDIT_RU.md)
пока закрывает шлюз итогового TEST. review40 сохранён как внутренний пакет
разработки методики; его заполнение не является требованием нового Study B.
Антоний и Денис проверяют техническую часть и выводы, не выступают агрономами.

Рабочий исследовательский MVP для первой статьи Антония и Дениса: сравнение локального LLM, облачного LLM, детерминированных агрометеорологических инструментов и каскада. Основной исторический эксперимент и его срез цен — 30.09.2026; отдельное дополнение HOME PC — 01.10.2026. Минимальный Python/HTML стенд; данные и raw ответы сохранены. Исследуются контролируемые задачи, пригодность рекомендаций для хозяйства не проверялась.

Начать чтение: [результаты](docs/RESULTS_RU.md), [one-pager для руководителя](docs/SUPERVISOR_ONE_PAGER_RU.md), [дизайн](docs/EXPERIMENT_DESIGN_RU.md), [возможность публикации](docs/RGAU_PUBLICATION_OPPORTUNITIES_2026_RU.md). Все девять требуемых исследовательских документов расположены в `docs/`, дополнительные ограничения hardware и roadmap — там же.

Актуальная публикационная стратегия по дополнительным требованиям преподавателя: **две отдельные статьи**. [Обзорная](docs/REVIEW_ARTICLE_PLAN_RU.md) — 15–20 страниц, ≥50 научных источников; [исследовательская](docs/RESEARCH_ARTICLE_PLAN_RU.md) — 6–8 страниц, УДК, аннотация 200–300 знаков, ≥15 научных источников. GitHub используется для поиска/повторного использования ПО и технического происхождения, не как научная ссылка. Прежние 3–5 страниц / ≤10 refs относятся к отдельному декабрьскому сборнику и не заменяют учебные форматы.

## Что реализовано

- 360 versioned records: 120 AgXQA extractive QA и 240 controlled RU/EN scenarios; train/dev/test180/90/90.
- GDD, VPD, daily FAO-56 ET0, rainfall deficit; проверка основных входов и C/mm, ASK_FOR_DATA. Полный контракт и ограничения проверки единиц описаны в [TOOL_VALIDATION_HOME_PC_RU.md](docs/TOOL_VALIDATION_HOME_PC_RU.md).
- local/cloud/rule/cascade/tool_cloud/offline; verifier по supported substring, не calibrated confidence.
- Исторические реальные paired local/cloud calls, raw cache, normalized trace replay, bootstrap CI, paired differences, descriptive McNemar, charts CSV/JSON/PNG/JPG/SVG.
- Русская UI с маршрутами, elapsed time, cloud cost, моделями, offline checkbox и NASA POWER Moscow Oblast snapshot.
- Unit/failure tests, фиксированный protocol, SHA-256 модели/данных/code/prompt, отдельные run folders. Никаких ключей в репозитории.

## HOME PC: актуальный результат 02.10.2026

**Финальный сбор и анализ завершены:** 150 новых заданий, по 75 на русском и английском, 750 уникальных измеренных решений для пяти политик. Данные объединяют 25 групп источников/семейств задач; 110 заданий синтетические. Перед запуском прошли 213 тестов. Исторический test90 не использован для настройки: его данные, основные модули и статистика отдельно проверены и воспроизведены без изменений.

| Политика | Правильно | Точность | Облачных вызовов | Mean / p50 / p95, с | Известная оценка USD |
|---|---:|---:|---:|---:|---:|
| LOCAL ONLY | 102/150 | 68.0% | 0 | 1.508 / 1.422 / 2.349 | 0.00000000 |
| CLOUD ONLY | 130/150 | 86.7% | 150 | 4.758 / 1.446 / 38.115 | 0.00721649 + UNKNOWN |
| TOOLS+CLOUD | 139/150 | 92.7% | 100 | 2.682 / 1.277 / 3.340 | 0.00433758 + UNKNOWN |
| TOOLS→LOCAL→CLOUD | 133/150 | 88.7% | 20 | 0.844 / 1.094 / 1.561 | 0.00079139 |
| OFFLINE | 114/150 | 76.0% | 0 | 0.655 / 1.042 / 1.458 | 0.00000000 |

Заранее замороженная совокупная гипотеза **не подтверждена**: разница точности гибрида и TOOLS+CLOUD составляет −4 п.п., парный кластерный 95% CI [−17.65; +5.83] п.п. При допустимом снижении 5 п.п. данных недостаточно, чтобы доказать сохранение качества; это также не доказывает статистически значимого ухудшения. Облачных вызовов стало на 80% меньше (100 → 20), средняя задержка снизилась с 2.682 до 0.844 с. Значительная часть ошибок гибрида относится к неверно выбранной ветке составного правила, которую пропускала буквальная проверка опоры на контекст.

Модель выбрана на DEV: Gemma 4 26B-A4B IQ4_NL_XL, context 4096, parallel 1, requested GPU offload 0.70. Qwen 27B качественнее на DEV36 (25/36 против 22/36), но медленнее (p50 3.030 против 1.532 с). Qwen 35B-A3B при данном профиле остановлен после 13 ответов по защите RAM; полный API DEV36 **NOT RUN**. У GPT-OSS после 13 ответов были четыре ошибки исчерпания output budget. Всего API inference измерена для 13 из 15 установленных текстовых моделей; две небезопасные конфигурации не повторялись. CLI и API серии анализируются отдельно.

Протокол и научный код зафиксированы до inference в commit `b063c079af44cdd6353db39293671f6d8d11f3d2`. Из-за Windows manifest replacement первый сегмент остановился после шести заданий. Оставшиеся 144 выполнены отдельным техническим продолжением без повторения первых запросов; settings, dataset и scoring не изменились. Перерыв и две загрузки модели показаны отдельно от latency запросов. Это контролируемое сравнение с раскрытым процедурным отклонением, а не непрерывный запуск.

Mercury 2.5 фактически меняет запрошенную temperature 0 на 1: предупреждение сохранено во всех 258 полученных ответах. Из 270 облачных вызовов у 12 timeouts отсутствует usage; полная стоимость **UNKNOWN**, известная сумма оценок $0.01234546. Для гибрида usage всех 20 облачных вызовов известен: $0.00079139 за 150 заданий, или $0.005276 за 1000 при том же составе нагрузки. Это оценка по токенам, не счёт провайдера; электричество и амортизация не включены.

Полные результаты, категории, языки, CI и таблица 30 примеров: [FINAL_EXPERIMENT_RESULTS_RU.md](docs/FINAL_EXPERIMENT_RESULTS_RU.md). [Замороженный протокол](docs/FINAL_EXPERIMENT_PROTOCOL_RU.md), [токены и ресурсы API-моделей](docs/HOME_API_TOKEN_RESOURCE_TABLE_RU.md), [скорость backend из логов](docs/HOME_API_BACKEND_LOG_METRICS_RU.md), [проблемы](docs/HOME_PC_PROBLEMS_RU.md), [MVP](docs/HOME_MVP_DEMO_RU.md). Статистика: `results/analysis_input_reconciled_20261002_052358Z_804ced2b/analysis_20261002_052438Z_2c0beea8/statistics_reporting_corrected.json`. Неизменённый исходный анализ сохранён рядом; отдельный reporting overlay исправляет только отображение ASK_FOR_DATA.

Для повторного анализа сохранённых данных использовать `scripts/analyze_home_final.py <reconciled_analysis_input>` и затем `scripts/correct_home_final_reporting.py <new_analysis>/statistics.json`. Это не выполняет inference. Повторный holdout ради таблиц не нужен. Наличие claims препятствует автоматическому повтору экспериментального запуска.

Дополнительные generative weights не скачивались: подготовлен [список девяти HF-кандидатов](docs/HF_MODELS_HOME_PC_SHORTLIST_RU.md). Открытый typed baseline Laya установлен и проверен отдельно на CPU для сопоставления с Jev. Mercury использует локально заданный `project_env:mercury_api_key`, Jev — `project_env:jev_api_key`; значения, .env и веса исключены из Git. Принадлежность исторического Mercury-ключа тому же платёжному аккаунту не установлена. OpenRouter пропущен по указанию пользователя после HTTP401.

Материала достаточно для узкой исследовательской статьи с отрицательным результатом проверки общей гипотезы и измеренным компромиссом ресурсов/качества. Перед рукописью требуется ручной аудит 30 примеров, ответов и перевода, а также полное чтение выбранных научных источников. Составленный shortlist из 16 источников не означает 16 прочитанных полных текстов. Контролируемая выборка не подтверждает пригодность рекомендаций в реальном хозяйстве. Корректность abstention не оценивается: gold ABSTAIN отсутствует.

Git delivery 02.10.2026: результат зафиксирован локально в `d41e90d8ef7ec31b4d0e6846c17f66b8629cfaf8`. Обычный `git push origin main` отклонён GitHub HTTP403 для аккаунта Apartman36; remote main остался `2a2037df62842b0389dc52c4dfbd38e8a04f3b8b`. **NOT PUSHED**. Нужны права записи на существующий repository; данные не отправлялись в другой репозиторий. Проверяемая запись: `results/git_delivery_20261002_054527Z_cdc20f2b/git_delivery.json`.

## Исторический CPU путь запуска на Windows

PowerShell из корня проекта. Требуется Python 3.12+ и `uv` (либо обычное venv/pip). Model files/runtime исключены из Git; их наличие на ноутбуке не означает наличие CPU artifacts в свежем clone. Для отдельного воспроизведения исторического CPU inference на чистой машине:

```powershell
uv venv --python 3.12
$env:UV_CACHE_DIR = Join-Path $PWD '.cache\uv'
uv --system-certs pip install --python .venv\Scripts\python.exe -r requirements-lock.txt
uv --system-certs pip install --python .venv\Scripts\python.exe --no-deps -e .
.venv\Scripts\python.exe scripts\prepare_assets.py --size 2B
```

`prepare_assets.py` скачивает Qwen3.5-2B GGUF Q4_K_M и официальный llama.cpp CPU b11292; поддерживает bounded Range resume, сверяет SHA с upstream LFS, безопасно извлекает zip и не перезаписывает идентичные загруженные DLL. Download size2B≈1.281GB, не размер полной RAM. SHA/revision в `data/model_assets_2B.json`. Переход на иную модель создаёт новый эксперимент, а не продолжение frozen test.

Первый терминал:

```powershell
.\scripts\start_local.ps1 -Size 2B
```

Второй терминал: создайте `.env` из `.env.example`, заполните CLOUD_API_KEY только для облака, актуальные prices проверьте в [Inception docs](https://docs.inceptionlabs.ai/get-started/models). Затем:

```powershell
.\scripts\load_env.ps1
.venv\Scripts\python.exe -m agro_route.cli serve --port 8090
```

Открыть http://127.0.0.1:8090. `.env` автоматически Python не загружает: script явно импортирует разрешённые model config variables в текущий процесс. По умолчанию example `CLOUD_AVAILABLE=false`; для реальных live cloud calls установите `$env:CLOUD_AVAILABLE='true'` **до** serve. Учитывайте стоимость. Offline UI работает без ключа. CLI paired benchmark требует CLOUD_API_KEY независимо от demo cloud switch.

Без `.env` задайте LOCAL_MODEL=Qwen3.5-2B-Q4_K_M, LOCAL_BASE_URL=http://127.0.0.1:8081/v1, CLOUD_MODEL=mercury-2.5, CLOUD_INPUT_USD_PER_M=.04, CLOUD_OUTPUT_USD_PER_M=.15 и CLOUD_API_KEY в process environment. Python legacy defaults — 0.8B/Mercury2; не запускайте 2B endpoint с неверным model ID. Proxy не используется для loopback. Серверы закрываются Ctrl+C в своих терминалах; скрытые процессы текущей сессии перечислены в `.runtime/local.pid` и `.runtime/web.pid`.

## Воспроизведение анализа без нового API расхода

Completed analysis не перезаписывается. Для повторного анализа создайте отдельную папку с manifest/pairs/normalized, затем analyze; это не новый model run:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
# analyze accepts a new folder with normalized.jsonl and pairs.jsonl
.venv\Scripts\python.exe -m agro_route.cli analyze results\YOUR_REPLAY_COPY
```

Для нового paired run с существующим frozen protocol и теми же моделями/данными:

```powershell
.venv\Scripts\python.exe -m agro_route.cli run --split test
```

Повторный test не независимая новая выборка. Для нового исследования используйте отдельную versioned task folder/dataset/protocol. Первичный development flow: run--splitdev--limit36 → analyze → freezePILOT → run--splittest → analyze. `freeze` create-new; model/dataset mismatch в test отвергается. Train оставлен для будущего learned router.

`scripts/prepare_data.py` воспроизводит subset из pinned AgXQA commit и controlled seed20260930, а также получает NASA snapshot. **Не изменять текущие данные после freeze.** Upstream weather revisions могут изменить snapshot hash, поэтому новая загрузка должна считаться новой data version. Для готового corpus достаточно файлов в `data/`. Источники/ограничения лицензий — DATA_LICENSES.md.

## Артефакты и честные границы

`results/<UTC_timestamp>_<id>/manifest.json` хранит модель, платформу, prices, code/prompt/dataset hashes и статус. `pairs.jsonl` содержит sample+raw outputs/usage/errors/HTTP latency. `normalized.jsonl` — политики на cached responses; `analysis.json`, `summary.csv`, `quality_cost_latency.*` — отчёт. Платные автоматические повторы отсутствуют. Если соединение оборвало run, сохранённые строки остаются, manifest не объявляется completed; новый запуск создаёт новую папку. Гибридная latency в benchmark — reconstructed trace replay, live UI time измеряется отдельно.

Исторический laptop: RAM 7.73 GiB, 8 logical CPU, CPU inference 4 threads, GPU UNKNOWN. Эти характеристики относятся к сентябрьским Qwen0.8B/Mercury2 и Qwen2B/Mercury2.5 pilots/final. Домашний PC использован 01.10 дляDEV и02.10 для независимого150-case сравнения с техническим продолжением, описанного выше. OpenAI/Claude/Gemini direct API NOT RUN. Не переносить результаты на весь класс local/frontier моделей и не объединять DEV и старый test в одну выборку.

MVP не включает trained/calibrated router, retrieval index, external agronomist workflow, crop-specific recommendation или production hosting. Все thresholds crop-independent либо заданы formal scenario. Правильность фрагмента в контексте не гарантирована substring check. Общий выигрыш tools+local+cloud необходимо сравнивать с tools+cloud, прежде чем утверждать вклад local LLM.

Инструкции переноса и восстановления окружения: [CROSS_MACHINE_SETUP_RU.md](docs/CROSS_MACHINE_SETUP_RU.md).

Продолжение 02.10.2026: [единый индекс](docs/CONTINUATION_20261002_INDEX_RU.md) объединяет PRIVATE backup на Apartman36, новые pre-inference Jev/Laya/rule DEV сравнения, Q8/BitNet baseline, все21 OpenRouter outcomes, Kaggle/source-overlap audit, blinded human-review pack и английский manuscript. Исторический final150 уже наблюдался; новый DEV не заменяет его независимым подтверждением. Исходный origin сохранён, upstream намеренно `apartman/main`. Подача на arXiv и человеческая проверка NOT RUN.

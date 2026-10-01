# Agro Route Lab

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

## HOME PC: дополнение 01.10.2026 — DEVELOPMENT ONLY

Репозиторий продолжает существующий research record; сентябрьские результаты и `data/protocol_frozen.json` сохранены. Текущая машина измерена: **Ryzen 7 8700F, RTX 5060 Ti с 16 311 MiB VRAM, 31.62 GiB RAM**, Windows 11 Pro. Изолированная `.venv` использует Python 3.12.12. LM Studio 0.4.25 слушает localhost:1234; HTTP API требует отдельный token. Фактический inventory включает **15 текстовых LLM**; локальные веса установлены отдельно от Git.

Попытки загрузки проверены для **всех 15 текстовых LLM**: inference выполнена для **14**, не менее шести DEV запросов — для **13**, одинаковый full36 — для **четырёх**. Результаты full36: GPT-OSS 20B **28/36, 77.8%**; Qwen3.8 27B **25/36, 69.4%**; Gemma 4 26B-A4B **21/36, 58.3%**; Qwen3.5 35B-A3B **19/36, 52.8%**. Для них p50/p95 CLI latency составили соответственно **3.604/8.531**, **3.042/4.450**, **1.472/2.362**, **1.992/2.777 s**. Разные N и resource stops не объединяются в один quality ranking.

Qwen3 Coder Next: inference **NOT RUN**. Две попытки загрузки остановлены: при requested offload 0.40 — из-за проверки GPU telemetry; при 0.35 — при доступной RAM **1.94 GiB**. Uncensored 35B вариант остановлен после **одного** запроса при доступной RAM **1.76 GiB**. Это ресурсные ограничения конкретной конфигурации, а не полноценные quality benchmarks.

GPT-OSS имеет лучшую общую correctness на full36, но в повторном paired QA probe получил **EN 4/6, RU 2/6** против первоначальных EN 6/6. Qwen27 и Gemma26 на тех же шести source pairs получили **EN 4/6, RU 5/6**; p50 составили **3.268 s** и **1.810 s**. Для отдельного contextual reader/replay предварительно выбран **Gemma26** как более быстрый из этих двух вариантов. **Final model NOT SELECTED:** temperature/seed/output budget CLI не контролируются, requested reasoning=off не гарантировал отключение reasoning у GPT-OSS. Перед окончательным выбором нужны controlled API revalidation; переводы имеют статус human validation PENDING.

**Новый holdout selected N=0, final NOT RUN; новые фактические cloud calls=0.** CLOUD ONLY, TOOLS+CLOUD и TOOLS→LOCAL→CLOUD на новом test не измерены: рабочий `CLOUD_API_KEY` отсутствует. Текущий offline DEV Gemma26 **16/36, 44.4%** — cached replay сохранённых local answers, не live offline benchmark. Прежний GPT-OSS replay **18/36** сохранён в отдельной сводке и не объединён с ним. Планируемая экономия эскалаций не является подтверждённым изменением качества, latency или billing. Файл `experiments/PROTOCOL_FREEZE_2026-10-01.md` содержит **NOT FROZEN** development snapshot.

Основные материалы дополнения:

- [HOME_PC_ENVIRONMENT_RU.md](docs/HOME_PC_ENVIRONMENT_RU.md) и `results/hardware/home_pc_2026-10-01.json` — измеренное окружение и inventory.
- [LOCAL_MODEL_COMPARISON_RU.md](docs/LOCAL_MODEL_COMPARISON_RU.md) и `results/20261001_home_analysis_d9a7acb8/` — текущая сводка четырёх full36 моделей, raw provenance, DEV manual table, Gemma offline replay и график. Первая GPT сводка сохранена в `results/20261001_home_analysis_b2a85b81/`.
- `results/20261001_inventory_summary_3f4378ba/` — итоговые статусы всех 15 текстовых моделей, различие load/inference/early/resource stops, token totals и ссылки на raw runs.
- [LOCAL_MODEL_TOKEN_RESOURCE_TABLE_RU.md](docs/LOCAL_MODEL_TOKEN_RESOURCE_TABLE_RU.md) — input/output tokens, coverage, quantization, offload, VRAM/RAM и TTFT; отсутствующие показания остаются UNKNOWN.
- [Excel: итоговые модели и все серии](outputs/home_pc_20261001/home_pc_models_20261001.xlsx) — 15 моделей и 25 run×model агрегатов, фильтры, tokens и ресурсы. Известны 135133 input /39087 output tokens для 286 из339 сохранённых запросов; остальные показания UNKNOWN.
- [HF_MODELS_HOME_PC_SHORTLIST_RU.md](docs/HF_MODELS_HOME_PC_SHORTLIST_RU.md) — отдельный список девяти кандидатов, точные файлы, лицензии, размеры и оценки fit, включая малые Q8 и native BitNet /IQ1.
- [JEV_LOCAL_ALTERNATIVE_RU.md](docs/JEV_LOCAL_ALTERNATIVE_RU.md) — скачанный открытый Laya multilingual decision baseline, отдельный CPU smoke12: routes9/12, missing-data6/12; не chat-модель и не подтверждённый эквивалент Jev.
- [FINAL_EXPERIMENT_RESULTS_RU.md](docs/FINAL_EXPERIMENT_RESULTS_RU.md) — количественные итоги HOME PC с разделением DEV, replay, projection и NOT RUN.
- [HOME_BILINGUAL_PROBE_RU.md](docs/HOME_BILINGUAL_PROBE_RU.md) и `data/home_dev_bilingual_20261001.jsonl` — шесть source pairs; это DEV, не независимый holdout.
- [FINAL_EXPERIMENT_PROTOCOL_RU.md](docs/FINAL_EXPERIMENT_PROTOCOL_RU.md) — проект следующего протокола; окончательный freeze и execution не выполнены.
- [MODEL_RESEARCH_2026_RU.md](docs/MODEL_RESEARCH_2026_RU.md), [LITERATURE_REVIEW_2026_RU.md](docs/LITERATURE_REVIEW_2026_RU.md) и `results/literature_20261001/` — новые кандидаты моделей и научных источников. В реестре 69 научных кандидатов, 50 в актуальном трёхлетнем окне; для 26 проверены abstract или отдельные методы. Это не 69 прочитанных full texts и не завершённые 50 источников обзорной статьи.
- [CLOUD_CREDENTIAL_AUDIT_RU.md](docs/CLOUD_CREDENTIAL_AUDIT_RU.md) — несекретные данные об используемых provider variables и границах атрибуции ключа.

CPU study можно оформлять как узкую первую статью с честными ограничениями. Сильная HOME PC гипотеза о дополнительном вкладе local stage сверх tools пока не подтверждена независимым экспериментом.

## Воспроизведение HOME PC без inference

PowerShell из корня проекта. Восстановление окружения выполняйте в чистой `.venv` по [CROSS_MACHINE_SETUP_RU.md](docs/CROSS_MACHINE_SETUP_RU.md); если текущая среда уже восстановлена, повторно устанавливать веса или создавать environment не требуется. LM Studio использует свой model inventory; `prepare_assets.py` ниже относится к историческому CPU пути.

```powershell
# Тесты и точное воспроизведение исторической статистики: без LLM/API calls.
$pytestRunDir = Join-Path $PWD ('.runtime\pytest-' + [guid]::NewGuid().ToString('N'))
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $pytestRunDir
.venv\Scripts\python.exe scripts\check_reproducibility.py
```

`check_reproducibility.py` сверяет исходные dataset/protocol/core hashes и создаёт новую игнорируемую копию исторического анализа. Существующие completed reports не перезаписываются. `scripts/report_home_pc.py` строит **новую** timestamped сводку из сохранённых DEV outputs без вызова моделей/облака и обновляет текущий документ сравнения; для изучения уже готового результата достаточно открыть сохранённую `analysis.json`.

После всех изменений 01.10.2026 основной test suite: **110 passed**. Исторические source/data/protocol checks проходят; число тестов не является доказательством качества или готовности незапущенного final experiment.

Для **нового запланированного DEV прогона**, который действительно выполняет локальную inference и создаёт отдельную папку:

```powershell
.venv\Scripts\python.exe scripts\home_pc_benchmark.py --n 12 --transport cli --models gemma-4-26b-a4b-it qwen3.8-27b gpt-oss-20b qwen3.5-35b-a3b --resource-guard
# Отдельный двуязычный DEV probe; не повторять ради воспроизведения готового отчёта.
.venv\Scripts\python.exe scripts\home_pc_benchmark.py --n 12 --transport cli --models gemma-4-26b-a4b-it --samples-path data\home_dev_bilingual_20261001.jsonl --resource-guard
```

Runner использует serial load/inference/unload, записывает failures/partial status и останавливается при неопределённом load либо resource guard. Sampled VRAM/RAM — totals устройства и системы, не точная per-model allocation. CLI generation controls UNKNOWN не заменяются выдуманными значениями.

Для контролируемого HTTP DEV сначала сохраните созданный самим пользователем LM Studio token только локально как `LOCAL_API_KEY` в project `.env`; это отдельный credential от Mercury. Проверенный адрес сервера — `http://127.0.0.1:1234/v1`, а HOME harness использует LM Studio `/api/v0/chat/completions` для дополнительной статистики. Исторический core default `127.0.0.1:8081/v1` относится к llama.cpp CPU. Для облачного DEV pilot требуется отдельный `CLOUD_API_KEY`; consumer subscriptions не дают автоматически API credits. Ни значения ключей, ни `.env`, ни веса в Git не добавляются. Текущий HOME CLI path работает без cloud credentials.

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

Исторический laptop: RAM 7.73 GiB, 8 logical CPU, CPU inference 4 threads, GPU UNKNOWN. Эти характеристики относятся к сентябрьским Qwen0.8B/Mercury2 и Qwen2B/Mercury2.5 pilots/final. Домашний PC фактически использован 01.10.2026 только для отдельного локального DEV этапа, описанного выше. OpenAI/Claude/Gemini direct API NOT RUN. Не переносить результаты на весь класс local/frontier моделей и не объединять DEV и старый test в одну выборку.

MVP не включает trained/calibrated router, retrieval index, external agronomist workflow, crop-specific recommendation или production hosting. Все thresholds crop-independent либо заданы formal scenario. Правильность фрагмента в контексте не гарантирована substring check. Общий выигрыш tools+local+cloud необходимо сравнивать с tools+cloud, прежде чем утверждать вклад local LLM.

Инструкции переноса и восстановления окружения: [CROSS_MACHINE_SETUP_RU.md](docs/CROSS_MACHINE_SETUP_RU.md).

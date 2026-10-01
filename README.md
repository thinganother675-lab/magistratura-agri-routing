# Agro Route Lab

Рабочий исследовательский MVP для первой статьи Антония и Дениса: сравнение локального LLM, облачного LLM, детерминированных агрометеорологических инструментов и каскада. Срез литературы и цен — 30.09.2026. Минимальный Python/HTML стенд; данные и raw ответы сохранены. Это первый контролируемый эксперимент, не готовые рекомендации для хозяйства.

Начать чтение: [результаты](docs/RESULTS_RU.md), [one-pager для руководителя](docs/SUPERVISOR_ONE_PAGER_RU.md), [дизайн](docs/EXPERIMENT_DESIGN_RU.md), [возможность публикации](docs/RGAU_PUBLICATION_OPPORTUNITIES_2026_RU.md). Все девять требуемых исследовательских документов расположены в `docs/`, дополнительные ограничения hardware и roadmap — там же.

Актуальная публикационная стратегия по дополнительным требованиям преподавателя: **две отдельные статьи**. [Обзорная](docs/REVIEW_ARTICLE_PLAN_RU.md) — 15–20 страниц, ≥50 научных источников; [исследовательская](docs/RESEARCH_ARTICLE_PLAN_RU.md) — 6–8 страниц, УДК, аннотация200–300 знаков, ≥15 научных источников. GitHub только для discovery/reuse ПО, не научная ссылка. Прежние3–5 страниц/≤10refs относятся к отдельному декабрьскому сборнику и не заменяют учебные форматы.

## Что реализовано

- 360 versioned records: 120 AgXQA extractive QA и 240 controlled RU/EN scenarios; train/dev/test180/90/90.
- GDD, VPD, daily FAO-56 ET0, rainfall deficit; валидация единиц/входов, ASK_FOR_DATA.
- local/cloud/rule/cascade/tool_cloud/offline; verifier по supported substring, не calibrated confidence.
- Реальные paired local/cloud calls, raw cache, normalized trace replay, bootstrap CI, paired differences, descriptive McNemar, charts CSV/JSON/PNG/JPG/SVG.
- Русская UI с маршрутами, elapsed time, cloud cost, моделями, offline checkbox и NASA POWER Moscow Oblast snapshot.
- Unit/failure tests, фиксированный protocol, SHA-256 модели/данных/code/prompt, отдельные run folders. Никаких ключей в репозитории.

## Запуск на Windows

PowerShell из корня проекта. Требуется Python3.12+ и `uv` (либо обычное venv/pip). Model files/runtime уже находятся локально, но исключены из Git. Для чистой машины:

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

Laptop: RAM7.73GiB, 8logicalCPU, CPU inference4threads, GPU UNKNOWN. Пользовательский отдельный PC RTX5060Ti16GB/32GBRAM/Ryzen78700 **не использован**. Qwen0.8B/Mercury2 и Qwen2B/Mercury2.5 имеют pilot results; OpenAI/Claude/Gemini direct API NOT RUN. Не переносить результаты на весь класс local/frontier моделей.

MVP не включает trained/calibrated router, retrieval index, external agronomist workflow, crop-specific recommendation или production hosting. Все thresholds crop-independent либо заданы formal scenario. Правильность фрагмента в контексте не гарантирована substring check. Общий выигрыш tools+local+cloud необходимо сравнивать с tools+cloud, прежде чем утверждать вклад local LLM.

Инструкции переноса и восстановления окружения: [CROSS_MACHINE_SETUP_RU.md](docs/CROSS_MACHINE_SETUP_RU.md).

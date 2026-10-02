# Окружение HOME PC

## Заключительная проверка продолжения — 02.10.2026, 19:28 UTC

Повторный Windows CIM/NVIDIA audit после всех timed compact trials: Ryzen 7 8700F **8 cores /16 threads**, Windows 11 Pro **10.0.26300**, visible RAM **31.62 GiB**, RTX 5060 Ti **16 311 MiB**, driver **617.14**. Свободно на C **196.13 GiB** в момент этой проверки; прежние дисковые значения ниже относятся к своим датам. Toolkit по-прежнему UNKNOWN. [Машиночитаемый snapshot](../results/hardware/home_pc_continuation_verified_20261002.json); первая sandbox CIM попытка получила ACCESS_DENIED и сохранена отдельно, повторный разрешённый read подтвердил CPU/OS.

LM Studio **0.4.25+1**, CLI **69d945a**, authenticated `http://127.0.0.1:1234` native API HTTP200. После cleanup inventory **23 entries**, loaded instances `[]`. Добавлены точные `qwen3.5-4b` Q8_0 и `phi-4-mini-instruct` Q8_0; native BitNet находится отдельно в ignored `.runtime` и исполняется на CPU. [Конечный LM snapshot](../results/20261002T170300Z_02a39af9_requested_local_metadata/final_lm_state_snapshot.json). Qwen research namespace `magistratura` — hard-link import того же pinned unsloth file, не новая модель или quantization; SHA и исходная provenance сохранены. Для Qwen main4,482,403,488B плюс mmproj1,334,075,072B; input text-only.

Три новые семьи получили fixed DEV12: Qwen3/12, Phi3/12, BitNet с проверенной official runtime configuration0/12. Remaining24 NOT RUN по предварительному gate. Исходный BitNet12 с legacy GGUF template сохранён отдельно как COMPATIBILITY_LIMITED; два CPU profiles не объединяются. Native portable LLVM-MinGW build проверен, CUDA OFF / GPU layers0, own process RSS отдельно от system RAM. Полные tokens, TTFT, decode TPS, requested/actual offload и resource scopes: [compact baseline report](REQUESTED_LOCAL_BASELINES_20261002_RU.md).

Одна локальная inference последовательно; downloads/builds и workbook export были разделены с timed windows. Qwen app descriptor всё ещё показывает active/downloading, но original314,093,791B partial не рос в восьмисекундных проверках до/после timed run. Собственные transfer clients остановлены; полной неактивности внутреннего job это не доказывает, остаточный риск явно сохранён. Daemon/app restart и пользовательские диалоги не изменялись. Собственные native CPU servers остановлены и проверены. Новые source/test changes проверяются заключительной suite; старые численные записи ниже сохранены как этапы исследования.

## Актуальное дополнение 02.10.2026

Повторный аппаратный аудит: Ryzen 7 8700F, 8 ядер / 16 потоков; RTX 5060 Ti, 16 311 MiB; RAM 31.62 GiB; Windows 11 Pro, build 26300; NVIDIA driver 617.14. На диске C перед final свободно 68.15 GiB. Snapshot: `results/hardware/home_pc_before_final_20261002.json`. CUDA compatibility 13.4 из драйвера не доказывает наличие установленного toolkit.

LM Studio 0.4.25+1. Авторизованный API `http://127.0.0.1:1234` работает: inventory `/api/v1/models`, inference `/v1/chat/completions`. Пользователь настроил LOCAL_API_KEY в ignored .env; значение не сохранено в отчётах. CLI commit: 69d945a. API DEV: 242 запроса для 13 текстовых моделей. Выбран Gemma 26B IQ4_NL_XL с context 4096, parallel 1 и requested GPU offload 0.70. Actual GPU layers остаются UNKNOWN; backend decode TPS извлечена отдельно из журналов только для DEV01.10, не для final02.10.

Финальный сбор завершён в двух сегментах из-за Windows manifest replacement failure. Суммарно 310 локальных и 270 облачных вызовов, без повторов первых шести заданий. Измеренные общие пики: GPU 13 758 MiB, system RAM 24.754 GiB. Это total устройства/системы, не private allocation модели. Две cold loads: 14.778 и 8.767 с; file cache и другие приложения не изолированы. LOCAL reasoning tokens = 0 в сохранённых final traces. После завершения собственный model instance выгружен; `lms ps --json` вернул `[]`.

Утром 02.10 сервер был выключен; `lms server start` восстановил порт 1234 с прежней авторизацией. Начальный snapshot ниже остаётся историческим: его ранние HTTP NOT RUN/empty credentials не описывают последующие API-прогоны. До final прошли 213 tests, после изменений — 241 PASS за 18.96 с. Validation: `results/delivery_validation_20261002_053454Z_64877e39/validation.json`; frozen SHA и все 16 файлов оригинального прерванного сегмента сохранились. Линтер в проекте не настроен.

## Первоначальный аппаратный и CLI snapshot 01.10.2026

Проверено 01.10.2026 на домашнем ПК. Snapshot: `results/hardware/home_pc_2026-10-01.json`. Исторические характеристики ноутбука в сентябрьских manifests сохранены.

| Компонент | Обнаружено |
|---|---|
| CPU | AMD Ryzen 7 8700F, 8 cores /16 logical processors |
| GPU | NVIDIA GeForce RTX 5060 Ti, WDDM |
| VRAM | 16 311 MiB по NVIDIA-SMI |
| RAM | 33 951 571 968 bytes =31.62 GiB; номинально32GB |
| ОС | Windows11 Pro, 10.0.26300, build26300 |
| NVIDIA driver | 617.14 |
| Driver CUDA compatibility | NVIDIA-SMI показывает CUDA UMD13.4; это не доказательство установленного CUDA Toolkit |
| Свободно на C при snapshot | 83 477 016 576 bytes =77.74 GiB |
| LM Studio | 0.4.25.0, executable file version0.4.25+1 |
| CLI | commit69d945a |
| Сервер | localhost1234; `http://127.0.0.1:1234/v1` OpenAI-compatible |
| HTTP доступ | Проверенные `/v1/models` и `/api/v0/models` возвращают401 без LM Studio API token |
| Начальная загрузка моделей | Нет загруженных моделей |
| Рабочий транспорт сессии | Документированный `lms load/chat/ps/unload`; sequential inference |
| Python | Изолированная .venv, CPython3.12.12; laptop был3.12.14 |

Список `lms runtime ls` сохранён в snapshot. Выбранный глобальный llama.cpp backend: `llama.cpp-win-x86_64-nvidia-cuda12-avx2@2.48.0`; установлены также2.49.0/2.46.0/2.44.0/2.43.0, другие CUDA/CPU/Vulkan версии. Backend на каждый loaded model отдельно CLI не раскрывает: глобальный preference не следует выдавать за per-model trace.

Inventory содержит 21 entry: 15 текстовых LLM, 3 embedding, 1 image generation и 2 TTS. Все 15 текстовых моделей включены в расширенный smoke по разрешению пользователя, включая coder и uncensored варианты. Изображения, TTS и embeddings не имеют применимой метрики в текстовом QA-бенчмарке. Полный inventory с model keys, paths, bytes, quantization и declared context сохранён в snapshot и manifests. Поле `trainedForToolUse` — metadata, а не результат проверки function calling.

## Настройки прогонов

Context4096, parallel1. Qwen9/Gemma12/GPT-OSS20: requested `--gpu max`; Qwen27:0.75, Qwen35-A3B:0.55, после оценки ресурсов. Запрос полного offload у больших двух моделей не выполнялся: файлы уже16.20GiB и20.48GiB доKV/runtime больше практически доступной GPU memory. Оценки памяти LM Studio не считаются измерением.

CLI принимает `--reasoning off`, однако GPT-OSS реально выводил reasoning channel. CLI не предоставляет temperature/max_tokens/JSON-schema options в установленной версии; они отмеченыUNKNOWN. HTTP harness заранее задаёт temperature0, seed42, max_tokens512/json_object, но authenticated live HTTP inference **NOT RUN**. Не заявлять поддержку JSON grammar, tool calls или logprobs по одним названиям моделей. См. [документацию LM Studio](https://lmstudio.ai/docs/developer/rest), [authentication](https://lmstudio.ai/docs/developer/core/authentication), [CLI load](https://lmstudio.ai/docs/cli/local-models/load).

VRAM считывается NVIDIA-SMI, RAM — Windows GlobalMemoryStatusEx; около0.5s плюс subprocess overhead. Это total device/system use, не per-model private memory и не точный мгновенный peak. Cold loading и начало первого ответа сохранены; load latency выделена отдельно, scored warmup не исключался. CLI wall latency включает процесс и IPC; она несопоставима напрямую с laptop HTTP latency.

## Восстановление

Создана новая `.venv`; lock24dependencies установлен черезuv, project editable installation завершена после sandbox WinError5 с разрешённой эскалацией. Перед inference24existingtestsPASS. Исторические dataset/protocol/core hashes совпали и cached statistics точно reproduced. Новые tests находятся отдельно; оригинальные шесть core modules не изменены. Линтер проектом не настроен; lint не заявляется.

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.cache\uv'
uv venv --python 3.12
uv --system-certs pip install --python .venv\Scripts\python.exe -r requirements-lock.txt
uv --system-certs pip install --python .venv\Scripts\python.exe --no-deps -e .
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts\check_reproducibility.py
# New development only; no cloud calls:
.venv\Scripts\python.exe scripts\home_pc_benchmark.py --n 12 --transport cli
```

Сервер/authentication не перенастроены, новые API tokens не созданы. Создана игнорируемая project `.env` с пустымиLOCAL_API_KEY/CLOUD_API_KEY; секреты не публикуются. Для authenticated HTTP API нужен отдельный LM Studio token из Developer → Server Settings → Manage Tokens, сохранённый локально вLOCAL_API_KEY. Mercury требует отдельныйCLOUD_API_KEY. ChatGPT/Claude подписки не использовались как API access. Все собственные экспериментальные model identifiers выгружаются после прогона; чужие модели runner не выгружает.

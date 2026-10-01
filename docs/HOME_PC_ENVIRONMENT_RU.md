# Окружение HOME PC

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

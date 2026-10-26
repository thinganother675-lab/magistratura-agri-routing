# Запрошенные компактные локальные baseline — 2 октября 2026

Статус на 19:27 UTC: **все запрошенные компактные baseline smoke завершены**. Qwen3.5-4B Q8_0 **3/12**, Phi-4-mini-instruct Q8_0 **3/12**, BitNet native I2_S после одной доказанной runtime коррекции **0/12**. По предварительному gate remaining DEV24 для всех **NOT RUN**. Исходный BitNet **0/12 — COMPATIBILITY_LIMITED** остаётся отдельным неизменным результатом, качество нельзя ранжировать из-за legacy template/pre-tokenizer. Исправленная серия — **DEV CONFIGURATION_CHANGE**, не fresh holdout; 7/7 token-ID и 2/2 chat-format parity, root approval до первой генерации сохранены. Qwen catalog зарегистрировался автоматически после research hardlink import; app/daemon restart не потребовался. Все собственные instance/server PID закрыты, LM Studio API показывает loaded instances **[]**. Старые результаты, final150 и протоколы сохранены.

## Точная идентичность и лицензии

| Baseline | Репозиторий / файл | Ревизия | Размер main-файла | Лицензия |
|---|---|---|---:|---|
| Qwen3.5-4B | unsloth/Qwen3.5-4B-GGUF / Qwen3.5-4B-Q8_0.gguf | e87f176479d0855a907a41277aca2f8ee7a09523 | 4 482 403 488 B | Apache-2.0 |
| Phi-4-mini-instruct | unsloth/Phi-4-mini-instruct-GGUF / Phi-4-mini-instruct.Q8_0.gguf | 78eb92a46fc37e6b524df991ed9aca9bc6aa7b80 | 4 084 611 040 B | MIT |
| BitNet b1.58 2B4T | microsoft/bitnet-b1.58-2B-4T-gguf / ggml-model-i2_s.gguf | a1f2f1c765812aa8af3f6eda4a313707064bba15 | 1 187 801 280 B | MIT |

Qwen — официальный post-trained checkpoint `Qwen/Qwen3.5-4B`, не Base/abliterated/merge. Phi — `microsoft/Phi-4-mini-instruct`, не Phi-mini-reasoning. Для Qwen и Phi выбраны обычные **Q8_0**, не UD-Q8_K_XL. LM Studio автоматически включает `mmproj-F32.gguf` Qwen (1 334 075 072 B); изображения в эксперимент не подаются.

Native BitNet обучен с ternary весами W1.58A8; его **I2_S GGUF не является обычным Q8 или post-training IQ1**. BF16-веса не скачиваются. CPU эффективность должна измеряться в официальном `bitnet.cpp`, а не при generic GGUF/Transformers исполнении.

Сводка точных ожидаемых SHA256, base revisions, метаданных альтернативных корректно сопоставленных quantizers, лицензий и первоначальной проверки диска: [metadata directory](../results/20261002T170300Z_02a39af9_requested_local_metadata/selection_manifest.json). API snapshot и LICENSE сохраняются отдельно; веса и runtime находятся вне Git.

Источники: [Qwen quantization](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF), [Phi quantization](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF), [официальный BitNet model card](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T), [официальный CPU runtime](https://github.com/microsoft/BitNet), [LM Studio CLI download](https://lmstudio.ai/docs/cli/local-models/get).

## Предварительно заданный DEV protocol

Контроллер: [local_baselines_20261002.py](../scripts/local_baselines_20261002.py). Новый код импортирует неизменные payload, public-request formatter, scorer, DEV selection и memory guards из исторического API harness.

Параметры: context 4096, parallel 1, temperature 0, top_p 1, seed 42, max_tokens 512, streaming usage и строгая пятиключевая JSON schema. Reasoning `none` запрашивается только при native capability `off`; наблюдаемые reasoning deltas/tokens сохраняются отдельно. Нет скрытого warm-up, повторов запросов или response cache. Модель загружается один раз на серию; cold-load время отдельно от HTTP wall latency.

Каждый Q8 кандидат проходит те же фиксированные первые **12 старых DEV**. Оставшиеся 24 добавляются однократно, без повтора первых 12, только если correct ≥6/12, completion errors ≤2/12 и safeguards не сработали. Это заранее заданный фильтр грубой пригодности компактного baseline; он не доказывает сопоставимость качества с Gemma/Qwen27. Старые DEV QA преимущественно английские; языковое ограничение остаётся явным. Final150 не читается и не применяется для выбора.

Обязательные поля: actual model ID/quantization/revision/checksum; load success и load config; input/output/total/reasoning tokens и coverage; клиентский TTFT/first-answer time и approximate tok/s; native backend speed только при однозначном логе; sampled total-device VRAM и total-system RAM; OS process RSS отдельно с UNKNOWN association при отсутствии доказанного PID; requested offload, actual offloaded layers UNKNOWN, если не подтверждены. Ошибки остаются в знаменателе.

Порог до загрузки: доступная RAM ≥3 GiB и GPU free ≥1024 MiB. Во время загрузки/перед inference: RAM ≥2 GiB и GPU free ≥512 MiB. Только один владелец управляет LM Studio, выгружает только собственные instance IDs. Downloads, builds и другая локальная inference запрещены во время timed measurement.

## Реально выполненный Phi smoke

[Неизменный run manifest](../results/20261002T182246Z_0265fdd0_requested_local_dev/manifest.json), raw responses и exact harness snapshot сохранены. Запрошенный GPU offload `max`; native config context 4096 / parallel 1 / flash attention true / KV-cache offload true. Число реально выгруженных слоёв **UNKNOWN**, backend TTFT **UNKNOWN**. Model-instance load занял 3,371 s; это загрузка нового instance, а не доказанный cold disk cache: перед ней SHA читается целиком.

| Model / quant | N | Correct | Input / output tokens | p50 / p95 HTTP, s | Client first-delta p50, s | Native decode p50, tok/s | VRAM peak, MiB | System RAM peak, GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Phi-4-mini-instruct Q8_0 | 12 | 3 (25,0%) | 5 052 / 364 | 0,429 / 0,499 | 0,034 | 77,35 | 5 396 | 13,24 |
| Qwen3.5-4B Q8_0 | 12 | 3 (25,0%) | 5 588 / 390 | 0,510 / 0,870 | 0,088 | 70,02 | 6 995 | 15,33 |
| BitNet native I2_S CPU, legacy metadata **COMPATIBILITY_LIMITED** | 12 | 0; **нельзя ранжировать качество** | 5 852 / 415 | 1,640 / 2,605 | 0,461 | 25,82 | 841, фон устройства | 12,27 |
| BitNet native I2_S CPU, corrected HF runtime **DEV CONFIGURATION_CHANGE** | 12 | 0 | 5 151 / 362 | 1,180 / 1,954 | 0,281 | 32,23 | 841, фон устройства | 11,69 |

Usage coverage 12/12, reasoning tokens 0, completion errors 0. Approximate client TPS p50 82,00 хранится отдельно от native decode TPS. Русская часть 1/5, английская 2/7. По категориям (по 2 случая): QA 1, missing input 2, numeric 0, tool selection 0, rule 0, compound 0. Короткие валидные JSON не означают правильного решения.

[Дополнительное log-derived evidence](../results/20261002T182246Z_0265fdd0_requested_local_dev/phi_backend_log_auxiliary.json) сопоставляет все 12 запросов по exact instance ID, порядку/числу, output token count, времени UTC+03 с точностью 1 s и token arithmetic; исходные raw/manifest не меняются. Prompt-eval token count является uncached subset и не подменяет input usage. Единственный новый llama-server PID 24240: RSS после серии 4 586 582 016 B (4,272 GiB), process peak 4 667 920 384 B (4,347 GiB), association **INFERRED_UNIQUE_NEW_BACKEND** — native API не сообщает PID. VRAM относится ко всему устройству, RAM — ко всей системе, sampled около 0,5 s плюс polling overhead. Собственный Phi instance выгружен; пользовательские instance IDs не затронуты.

## Реально выполненный Qwen smoke

[Qwen run](../results/20261002T192227Z_63b6c1bf_requested_local_dev/manifest.json): main SHA подтверждён, logical LM key `qwen3.5-4b`, actual path `magistratura/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q8_0.gguf`. `magistratura` — только namespace импорта: источник весов остаётся точным `unsloth/Qwen3.5-4B-GGUF@e87f176...`, подтверждённым checksum. Companion checksum совпал, vision inputs отсутствуют. Requested GPU=max, KV-cache offload true, context 4096 / parallel 1 / reasoning none / no speculative draft. Actual offloaded layers **UNKNOWN**, backend TTFT UNKNOWN. Instance load 4,487 s, filesystem cache после полной SHA-проверки не cold.

Correct 3/12, errors 0, usage/reasoning coverage 12/12, reasoning tokens 0. EN 2/7, RU 1/5; категории совпали с Phi: QA 1/2, missing data 2/2, остальные 0/2. Client approximate TPS 72,923 отдельно от native log median 70,02. [Qwen log auxiliary](../results/20261002T192227Z_63b6c1bf_requested_local_dev/qwen_backend_log_auxiliary.json) однозначно сопоставляет все 12 requests теми же строгими проверками. Новый backend PID 10980 имеет RSS 5 208 166 400 B (4,851 GiB), peak 5 305 614 336 B (4,941 GiB), association **INFERRED_UNIQUE_NEW_BACKEND**. Own instance cleanup подтверждён.

## BitNet Windows compatibility

Стандартная проверка documented VS2022/ClangCL generator **BLOCKED**: CMake не нашёл ни одного экземпляра Visual Studio. Основной runtime revision `0b341e582afbf9e1011f24744b554c96a3477eb5`; llama.cpp submodule `390c307752ab78fd8189f359d6954c9ba1be74af`.

Одна разрешённая альтернатива: переносимый LLVM-MinGW 20260922 UCRT x86_64 в `.runtime/bitnet/`, официальный zip SHA256 `e3ad77d117a4bea19a7a3b333341824d79a5a371004a10e25b8504e7b3047666`. Это отдельная совместимость, а не заявленное official VS build. Системный compiler, PATH, ОС, драйвер и virtualization не изменяются. При её неудаче CPU arm будет BLOCKED с точной ошибкой и resume-командой; остальные задачи продолжатся.

Сборка той же альтернативой завершилась: Clang 23.1.2, native server version 9918 (`390c30775`), CPU-only, все 296 targets. Параметры nested COMMON/TOOLS включены; для `CreateFile2` добавлен Windows API target `_WIN32_WINNT/WINVER=0x0A00`, исходный код не менялся. [Build evidence](../results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_native_build_verified.json) включает бинарные SHA, pinned source/submodule commits и logs. CUDA/OpenMP/BLAS выключены, native I2_S; 4 CPU threads, context 4096, parallel 1, `--no-warmup`, max tokens 512. Header подтверждает architecture `bitnet-b1.58`, 30 blocks, 210 I2_S tensor/type36, 121 F32 и 1 F16. BF16 не скачивался.

[Исходный native DEV12](../results/20261002T185320Z_1027a4c6_bitnet_native_dev/manifest.json): load 1,024 s, errors 0, usage coverage 12/12. Reasoning token counter **UNKNOWN**, отсутствуют reasoning deltas. Native SSE `predicted_per_second` median 25,816, client approx 31,920 отдельно; native TTFT UNKNOWN. Own PID 24348 RSS 1 632 518 144 B (1,520 GiB), peak working set 1 688 297 472 B (1,572 GiB), exact Popen association. GPU layers 0 подтверждены CPU-only binary/startup; 841 MiB — фоновая VRAM всего устройства, не память модели. Prefix KV-cache повторно используется у 11/12 запросов; `cache_n+prompt_n=usage.prompt_tokens` и `predicted_n=usage.completion_tokens` совпали 12/12. `--no-warmup` исключает пустой warmup, но не означает, что каждый prompt считается полностью заново. Собственный server завершён.

Качество legacy native arm невалидно для ранжирования: startup явно предупреждает `missing pre-tokenizer type`, а GGUF chat template использует `Human`/`BITNETAssistant` и пропускает system role. Официальный [HF tokenizer_config pinned revision](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T/blob/04c3b9ad9361b824064a1f25ea60a8be9599b127/tokenizer_config.json) задаёт role-capitalized `System/User/Assistant`, `<|eot_id|>` (128009); GGUF eos 128001 и legacy template отличаются. Это проверенная ошибка совместимости, не вывод о научной пригодности BitNet.

Одна минимальная runtime коррекция сохраняет исходные GGUF SHA/веса: `--override-kv` для `llama-bpe`, EOS128009, auto BOS/EOS=false и exact official HF chat template file. Негенеративный diagnostic сопоставил 7 фиксированных token-ID probes (EN/RU/whitespace/numeric/special/converter canonical) и 2 chat-format probes; **все точные**, generation requests **0**, own server cleanup true. Converter fingerprint `0ef9807a...` однозначно соответствует `llama-bpe`; regex совпадает с native LLAMA3. [Parity report](../results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_tokenizer_diagnostic/native_tokenizer_parity_v1.json) и [отдельный immutable protocol](../results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_tokenizer_diagnostic/BITNET_RUNTIME_OVERRIDE_PROTOCOL_V1.json). [Root approval annex](../results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_tokenizer_diagnostic/root_approval_corrected_runtime_20261002.json) записан 19:17:21 UTC до первой генерации; frozen protocol/parity не менялись.

[Corrected trial](../results/20261002T191731Z_61e3e23d_bitnet_native_dev/manifest.json) — новая **DEV CONFIGURATION_CHANGE**, не замена прежних 12 и не свежий holdout. Correct 0/12, errors 0, remaining24 NOT RUN; отсутствие warning подтверждено, template/tokenization parity проверена независимо от answers. [Native auxiliary](../results/20261002T191731Z_61e3e23d_bitnet_native_dev/bitnet_corrected_native_auxiliary.json): SSE native timing coverage 12/12, full-input/cache/predicted arithmetic точная, prefix reuse 11/12, native TPS median 32,228, client approximate 33,409. Backend TTFT UNKNOWN, reasoning counter UNKNOWN (coverage 0), no observed reasoning deltas. Own PID 6532 RSS 1 608 794 112 B (1,498 GiB), peak 1 632 014 336 B (1,520 GiB), exact Popen association; CPU GPU-layers 0, device VRAM841 MiB фон. Load 1,037 s относится к новой instance, диск уже прогрет предыдущими SHA/diagnostic reads. Это отрицательный результат конкретного короткого строгого agricultural/JSON screen; не утверждение о всех CPU/BitNet задачах.

## Qwen import и остаточное ограничение

[Main/companion checksum и hardlink evidence](../results/20261002T170300Z_02a39af9_requested_local_metadata/qwen_import_verified.json) сохраняет промежуточный catalog blocker. Main 4 482 403 488 B SHA `10cc391b...`, companion 1 334 075 072 B SHA `758b74e6...`; metadata `qwen35`, Qwen3.5-4B, 249 Q8_0 tensors. Старый app partial 314 093 791 B сохранён. CLI import создал hardlinks в исходном `unsloth` и одну research namespace `magistratura`, физические веса одни. Затем [catalog-ready evidence](../results/20261002T170300Z_02a39af9_requested_local_metadata/qwen_catalog_ready.json) подтвердило автоматическую регистрацию research namespace, checksum, Q8 и actual key. App-wide restart/изменение job database/другая quantization не потребовались.

[Final LM state](../results/20261002T170300Z_02a39af9_requested_local_metadata/final_lm_state_snapshot.json): LM Studio 0.4.25+1, CLI commit 69d945a, authenticated native API200, server1234, inventory23, new Qwen/Phi доступны, loaded instances []. Собственных transfers/builds/CPU servers нет. Старый app job metadata всё ещё `active`, main task `downloading`, companion `completed`; его partial не менялся при восьмисекундных start/end checks Qwen. **Остаточная неопределённость background transfer явно сохраняется:** стабильность файла не доказывает отсутствие job активности. Timing интерпретируется в условиях отсутствия наблюдаемого роста и собственных конкурирующих задач.

## Resume

Для чистых latency measurements основные downloads были остановлены. Закрытие CLI не остановило Phi app-transfer: он завершился самостоятельно. Попытка Computer Use открыть существующее окно LM Studio зависла на 1396 секунд и была прервана; UI pause не подтверждена. Qwen app-job сохранил `active`, но main partial не менялся около 40 минут. В восьмисекундной проверке 17:57 UTC все partial-файлы были стабильны. Этот остаточный риск раскрыт координатору; start/end file growth проверяется отдельно. Ни один пользовательский instance не выгружался. Для root DEV загружен только `preroute-reference-gemma26`, context 4096 / parallel 1 / requested GPU 0,70; actual GPU layers UNKNOWN.

Точное checkpoint evidence: [measurement_window_checkpoint.json](../results/20261002T170300Z_02a39af9_requested_local_metadata/measurement_window_checkpoint.json).

Точные уже выполненные команды для воспроизводимости; **не повторять** для скрытого отбора модели:

```powershell
& .venv\Scripts\python.exe scripts\local_baselines_20261002.py --model-root C:\Users\hustlePC\.lmstudio\models
& .venv\Scripts\python.exe scripts\local_baselines_20261002.py --run --n 36 --models qwen --model-root C:\Users\hustlePC\.lmstudio\models
& .venv\Scripts\python.exe scripts\local_baselines_20261002.py --run --n 36 --models phi --model-root C:\Users\hustlePC\.lmstudio\models
& .venv\Scripts\python.exe scripts\local_baselines_20261002.py --run --bitnet-server .runtime\bitnet\build-mingw\bin\llama-server.exe --bitnet-model .runtime\bitnet\models\BitNet-b1.58-2B-4T\ggml-model-i2_s.gguf --n 36
& .venv\Scripts\python.exe scripts\local_baselines_20261002.py --run --bitnet-server .runtime\bitnet\build-mingw\bin\llama-server.exe --bitnet-model .runtime\bitnet\models\BitNet-b1.58-2B-4T\ggml-model-i2_s.gguf --bitnet-runtime-protocol results\20261002T170300Z_02a39af9_requested_local_metadata\bitnet_tokenizer_diagnostic\BITNET_RUNTIME_OVERRIDE_PROTOCOL_V1.json --n 36
```

Все команды завершились на gate12, даже когда planned36. Повторять их для выбора запрещено. Публичные transfers `--resume-public bitnet/qwen/llvm` уже завершены; каждая требует exact206 Content-Range и fullSHA, verified final artifact переиспользуется без повторного transfer. Checkpoints сохраняются; runtime/weights/cache вне Git. Точные выполненные driver/helper snapshots и SHA находятся в run directories; текущий driver изменялся после Phi/nativelegacy, поэтому не подменяет их сохранённый source.

Практический вывод ограничен DEV12: новые компактные baseline не проходят установленный gross-screen threshold. Исторические Gemma/Qwen references остаются основными исследовательскими конфигурациями; модели не выбираются по этим новым малым denominator или наблюдённому final150. Следующий исследовательский шаг — независимая ручная проверка scorer/примеров и выводы основной routing-серии, без расширения неуспешного local screen на confirmatory holdout.

Повторная команда создаёт новую developmental серию; она не возобновляет старую и не должна применяться для скрытых выборочных повторов. Уже проведённые запросы всегда сохраняются.

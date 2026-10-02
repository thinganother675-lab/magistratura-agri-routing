# LM Studio: токены и ресурсы контролируемых API-серий

01.10.2026. Развивающий набор; подтверждающий holdout здесь не запускался.

Сводка: `results/20261001_api_tables_35768dbf/summary.json`. Все серии, включая режим reasoning по умолчанию и двуязычные повторы, — в all_api_runs.csv.

| Модель | Correct/N | p50 / p95, с | Input / output tokens | Reasoning tokens | TTFT client, с | Client approx tok/s | VRAM MiB total | RAM GiB system | Offload requested | Quant | Ошибки |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| gemma-4-26b-a4b-it | 22/36 | 1.532 / 2.440 | 17016 / 1307 | 0 (36/36) | 0.649 | 42.98 | 14042 | 26.88 | 0.70 | IQ4_NL_XL | 0 |
| qwen3.8-27b | 25/36 | 3.030 / 4.244 | 16486 / 1109 | 0 (36/36) | 0.834 | 14.36 | 15189 | 27.80 | 0.75 | Q4_K_M | 0 |
| qwen3.5-35b-a3b | 7/13 | 1.734 / 5.268 | 6124 / 411 | 0 (13/13) | 0.715 | 31.09 | 14101 | 29.77 | 0.55 | Q4_K_L | 0 |
| gpt-oss-20b | 8/13 | 3.157 / 5.133 | 6437 / 4515 | 4181 (13/13) | 0.182 | 109.71 | 12455 | 23.48 | max | Q8_0 | 4 |
| qwen3.5-9b | 5/12 | 0.930 / 1.364 | 5588 / 425 | 0 (12/12) | 0.120 | 46.18 | 11478 | 20.29 | max | Q8_0 | 0 |
| gemma-4-12b-it | 8/12 | 0.990 / 1.525 | 5764 / 481 | 0 (12/12) | 0.299 | 59.94 | 8660 | 17.53 | max | Q4_K_S | 0 |
| minicpm5-1b | 1/12 | 0.241 / 0.537 | 5289 / 711 | 0 (12/12) | 0.022 | 251.66 | 2196 | 11.80 | max | Q8_0 | 0 |
| webworld-8b-i1 | 6/12 | 0.548 / 0.798 | 5493 / 371 | 0 (12/12) | 0.071 | 63.29 | 7770 | 16.88 | max | Q6_K | 0 |
| granite-4.1-8b | 6/12 | 0.800 / 1.465 | 5254 / 555 | 0 (12/12) | 0.090 | 74.82 | 6796 | 16.44 | max | Q4_K_M | 0 |
| dr-venus-4b-rl | 1/6 | 4.859 / 4.957 | 2782 / 2523 | 2450 (6/6) | 0.075 | 105.69 | 4200 | 14.20 | max | Q4_K_M | 4 |
| qwen3-vl-8b-instruct | 5/12 | 0.585 / 0.706 | 5445 / 313 | 0 (12/12) | 0.055 | 50.44 | 11024 | 19.50 | max | Q8_0 | 0 |
| qwen3-8b-deepseek-v3.2-speciale-distill | 8/12 | 0.419 / 0.523 | 5493 / 281 | 0 (12/12) | 0.057 | 68.77 | 6304 | 15.47 | max | Q4_K_M | 0 |
| qwen3-omni-30b-a3b-instruct | 6/12 | 1.337 / 2.173 | 5493 / 407 | 0 (12/12) | 0.554 | 42.53 | 14908 | 29.03 | 0.60 | Q4_K_M | 0 |
| qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | NOT RUN | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN (0/0) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 0.55 | Q4_K_M | UNKNOWN |
| qwen3-coder-next | NOT RUN | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN (0/0) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 0.35 | Q3_K_S | UNKNOWN |

Все API-серии: 242 запросов, известно 113332 входных и 17259 выходных токенов; coverage 242/242 и 242/242. Reasoning входит в output; его нельзя повторно прибавлять к расходу.

Temperature=0, top_p=1, seed=42, max_tokens=512, strict JSON schema; context=4096, parallel=1. off-or-low использует экспериментальное поле reasoning_effort=none либо low для GPT-OSS; фактические reasoning deltas/usage сохранены. Нулевая reasoning coverage не доказывает отсутствие reasoning.

Выбор представительной серии сделан по размеру, затем дате, без отбора лучшего результата. Ранние остановки и NOT RUN сохранены. Для сравнений качества используйте одинаковые ID и N; категории и языки доступны в summary.json.

TTFT и скорость измерены клиентом по SSE. Client TPS приблизителен и исключает первый межтокенный интервал; он не равен старому backend decode tok/s. VRAM/RAM включают другие процессы. Число фактически выгруженных на GPU слоёв UNKNOWN; requested ratio приведён явно.

Catalog size Gemma26 — 16847892149 bytes суммарных артефактов: основной GGUF 14556687680, mmproj 2291200608 и config 3861 bytes. Это размер model directory, а не только одного файла весов. SHA256 каждого файла сохранён в results/hardware/selected_gemma26_fingerprint_20261001.json; сами веса в Git не добавляются.

## Скорость backend из логов — 02.10.2026

После основной таблицы отдельно извлечены native decode/prompt TPS из серверных логов для 242/242 собственных API requests. [Связь с raw и отдельная таблица backend](HOME_API_BACKEND_LOG_METRICS_RU.md). Например, полные DEV36: Gemma 26 backend median 33.53 tok/s против client approximate 42.98; Qwen 27 backend 13.545 против client approximate 14.36. Исходные client-колонки остаются клиентскими; input usage не заменяется uncached prompt counts из логов. Actual GPU layers и native TTFT UNKNOWN. Final 02.10 не наследует эти DEV-метрики.

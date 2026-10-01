# Все текстовые модели LM Studio: HOME-PC DEV

01.10.2026. Проверяются 15 текстовых LLM из 21 установленного артефакта. Три embeddings, image generation и две TTS не имеют применимой метрики в этом текстовом benchmark.

Сводка: `results/20261001_inventory_summary_3f4378ba/summary.json`; полные model IDs, quantization, bytes и raw hashes сохранены.

| Model key | Quant | File GiB | Correct/N | p50 / p95 s | tok/s | VRAM MiB total | RAM GiB system | Errors | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| qwen3.5-9b | Q8_0 | 10.57 | 4/12 | 1.053 / 1.351 | 42.94 | 11421 | 21.38 | 4 | EARLY STOP |
| gemma-4-12b-it | Q4_K_S | 6.50 | 4/12 | 1.196 / 1.383 | 47.67 | 8593 | 18.24 | 4 | EARLY STOP |
| qwen3.8-27b | Q4_K_M | 16.20 | 25/36 | 3.042 / 4.450 | 14.15 | 15095 | 27.76 | 0 | COMPLETED DEV |
| qwen3.5-35b-a3b | Q4_K_L | 20.48 | 19/36 | 1.992 / 2.777 | 28.76 | 14187 | 29.79 | 0 | COMPLETED DEV |
| gpt-oss-20b | Q8_0 | 11.28 | 28/36 | 3.604 / 8.531 | 106.20 | 12478 | 24.05 | 3 | COMPLETED DEV |
| minicpm5-1b | Q8_0 | 1.07 | 0/7 | 0.406 / 0.724 | 249.78 | 2241 | 12.56 | 4 | EARLY STOP |
| webworld-8b-i1 | Q6_K | 6.26 | 2/10 | 1.756 / 5.414 | 55.80 | 7810 | 17.35 | 4 | EARLY STOP |
| granite-4.1-8b | Q4_K_M | 4.98 | 2/6 | 6.451 / 9.960 | 64.14 | 6834 | 16.28 | 4 | EARLY STOP |
| dr-venus-4b-rl | Q4_K_M | 2.53 | 6/12 | 6.283 / 23.026 | 99.20 | 4297 | 16.09 | 2 | COMPLETED DEV |
| qwen3-vl-8b-instruct | Q8_0 | 9.19 | 4/12 | 0.964 / 1.036 | 44.02 | 11058 | 19.63 | 2 | COMPLETED DEV |
| qwen3-8b-deepseek-v3.2-speciale-distill | Q4_K_M | 4.68 | 5/9 | 0.642 / 2.352 | 66.74 | 6343 | 16.44 | 4 | EARLY STOP |
| gemma-4-26b-a4b-it | IQ4_NL_XL | 15.69 | 21/36 | 1.472 / 2.362 | 36.55 | 13937 | 25.74 | 1 | COMPLETED DEV |
| qwen3-omni-30b-a3b-instruct | Q4_K_M | 19.34 | 5/12 | 1.732 / 2.241 | 36.99 | 14947 | 28.73 | 1 | COMPLETED DEV |
| qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | Q4_K_M | 20.55 | 0/1 | 3.593 / 3.593 | 31.12 | 13849 | 30.13 | 0 | RESOURCE STOP |
| qwen3-coder-next | Q3_K_S | 31.03 | NOT RUN | — | — | — | — | — | LOAD STOP |

Четыре ошибки среди первых запросов прекращают smoke после минимум шести примеров. N поэтому различается. Доли на неполных smoke-срезах не ранжируются против full36; ранняя остановка отражает непригодность текущего adapter/settings, а не доказанную непригодность весов.

Локальный токен HTTP не настроен: использовался CLI с неизвестными temperature и output limits. Structured failures включают parser/transport errors; native function calling не проверялся. Для GPT-OSS tok/s включает reasoning. Latency включает запуск CLI и IPC.

VRAM — sampled total device use, RAM — whole-system use. Значения не равны private allocations модели. Guard контролирует запас памяти во время загрузки и перед inference; он не гарантирует непрерывной отмены запроса. Requested GPU ratio — не измеренное количество offloaded layers.

Эти измерения относятся к старому DEV и новым DEV translations. Новый независимый holdout NOT RUN; вывод о подтверждении основной гипотезы не получен.

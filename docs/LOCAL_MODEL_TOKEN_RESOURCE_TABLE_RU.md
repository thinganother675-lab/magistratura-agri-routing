# Токены и offload: итоговые локальные прогоны

01.10.2026. Одна репрезентативная серия на модель: расширенный DEV36, где он выполнен, иначе последний smoke. Все серии и общий расход сессии сохранены в summary.json. Повторы языкового probe и диагностические серии не смешаны с основным качеством.

| Model key | N | Input tokens known | Output tokens known | Usage coverage | GPU offload requested | Quant | File GiB | VRAM MiB total peak | RAM GiB system peak | TTFT s | Decode tok/s |
|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| qwen3.5-9b | 12 | 5588 | 348 | 12/12 input; 12/12 output | max | Q8_0 | 10.57 | 11421 | 21.38 | 0.101 | 42.94 |
| gemma-4-12b-it | 12 | 5764 | 406 | 12/12 input; 12/12 output | max | Q4_K_S | 6.50 | 8593 | 18.24 | 0.192 | 47.67 |
| qwen3.8-27b | 36 | 16486 | 1100 | 36/36 input; 36/36 output | 0.75 | Q4_K_M | 16.20 | 15095 | 27.76 | 0.714 | 14.15 |
| qwen3.5-35b-a3b | 36 | 16486 | 1248 | 36/36 input; 36/36 output | 0.55 | Q4_K_L | 20.48 | 14187 | 29.79 | 0.628 | 28.76 |
| gpt-oss-20b | 36 | 16004 | 14529 | 33/36 input; 33/36 output | max | Q8_0 | 11.28 | 12478 | 24.05 | 0.072 | 106.20 |
| minicpm5-1b | 7 | 3195 | 315 | 7/7 input; 7/7 output | max | Q8_0 | 1.07 | 2241 | 12.56 | 0.011 | 249.78 |
| webworld-8b-i1 | 10 | 4664 | 1181 | 10/10 input; 10/10 output | max | Q6_K | 6.26 | 7810 | 17.35 | 0.044 | 55.80 |
| granite-4.1-8b | 6 | 2708 | 2053 | 6/6 input; 6/6 output | max | Q4_K_M | 4.98 | 6834 | 16.28 | 0.044 | 64.14 |
| dr-venus-4b-rl | 12 | 5474 | 10449 | 12/12 input; 12/12 output | max | Q4_K_M | 2.53 | 4297 | 16.09 | 0.026 | 99.20 |
| qwen3-vl-8b-instruct | 12 | 5450 | 315 | 12/12 input; 12/12 output | max | Q8_0 | 9.19 | 11058 | 19.63 | 0.041 | 44.02 |
| qwen3-8b-deepseek-v3.2-speciale-distill | 9 | 4231 | 127 | 9/9 input; 9/9 output | max | Q4_K_M | 4.68 | 6343 | 16.44 | 0.039 | 66.74 |
| gemma-4-26b-a4b-it | 36 | 17016 | 1123 | 36/36 input; 36/36 output | 0.70 | IQ4_NL_XL | 15.69 | 13937 | 25.74 | 0.428 | 36.55 |
| qwen3-omni-30b-a3b-instruct | 12 | 5498 | 416 | 12/12 input; 12/12 output | 0.60 | Q4_K_M | 19.34 | 14947 | 28.73 | 0.526 | 36.99 |
| qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | 1 | 539 | 37 | 1/1 input; 1/1 output | 0.55 | Q4_K_M | 20.55 | 13849 | 30.13 | 2.067 | 31.12 |
| qwen3-coder-next | 0 | UNKNOWN | UNKNOWN | 0/0 input; 0/0 output | 0.35 | Q3_K_S | 31.03 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Все сохранённые локальные серии: 339 запросов. Известно 135133 input / 39087 output tokens; coverage 286/339 input и 286/339 output. Это нижняя известная сумма при пропущенных stats, не полный расход и не API billing.

Offload max означает запрос полной GPU загрузки; число фактически перенесённых layers CLI не раскрывает. Значение 0.75/0.55/0.70 означает requested fraction, а не измеренную долю VRAM. Файлы крупных моделей дополнительно используют RAM. Coder не завершил загрузку при 0.40 и 0.35; его inference/tokens NOT RUN.

Prompt/Predicted tokens сообщает LM Studio CLI. Reasoning tokens GPT-OSS входят в output и decode speed; их отдельное количество UNKNOWN. При ошибке без stats число tokens неизвестно. Старый диагностический run без stderr stats сохранён с null, а не пересчитан по символам.

CSV с полными колонками: `results/20261001_inventory_summary_3f4378ba/all_text_models.csv`. Raw и все attempts связаны через `summary.json`.

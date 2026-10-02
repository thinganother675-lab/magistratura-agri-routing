# Скорость backend из логов LM Studio: дополнение 02.10.2026

Дополнительно к client SSE timing прочитан серверный журнал 01.10.2026. Полные логи, prompts, headers и посторонние разговоры не скопированы. Извлечены метрики только 17 собственных home-api instances: **242/242 API requests однозначно связаны с сохранёнными raw outputs** по instance, порядку/количеству, completion tokens и timestamp UTC+03:00 в пределах 1 с. Исходные usage, prompts и результаты не менялись.

Таблица использует ту же представительную серию, что HOME_API_TOKEN_RESOURCE_TABLE_RU: наиболее полная old_dev off-or-low серия, затем поздняя дата, без отбора по качеству. Backend decode tok/s — median логовых eval timing; client tok/s — отдельная приближённая SSE оценка. Reasoning включён в output counts у моделей с reasoning. Prompt eval токены в логах относятся к uncached prefill и не заменяют input usage. Native cache counters имеют отдельные диагностические расхождения и не служат token billing.

| Фактический model key | N | Backend decode tok/s | Backend uncached prompt tok/s | Client approximate tok/s | Requested GPU |
|---|---:|---:|---:|---:|---:|
| gemma-4-26b-a4b-it | 36 | 33.53 | 164.18 | 42.98 | 0.70 |
| qwen3.8-27b | 36 | 13.54 | 105.78 | 14.36 | 0.75 |
| qwen3.5-35b-a3b | 13 | 28.74 | 132.20 | 31.09 | 0.55 |
| gpt-oss-20b | 13 | 106.26 | 969.20 | 109.71 | max |
| qwen3.5-9b | 12 | 43.21 | 819.35 | 46.18 | max |
| gemma-4-12b-it | 12 | 47.92 | 418.87 | 59.94 | max |
| minicpm5-1b | 12 | 247.68 | 6859.44 | 251.66 | max |
| webworld-8b-i1 | 12 | 58.62 | 1862.91 | 63.29 | max |
| granite-4.1-8b | 12 | 60.28 | 1331.15 | 74.82 | max |
| dr-venus-4b-rl | 6 | 105.53 | 3153.53 | 105.69 | max |
| qwen3-vl-8b-instruct | 12 | 46.70 | 1880.49 | 50.44 | max |
| qwen3-8b-deepseek-v3.2-speciale-distill | 12 | 63.27 | 2162.11 | 68.77 | max |
| qwen3-omni-30b-a3b-instruct | 12 | 38.39 | 140.08 | 42.53 | 0.60 |
| qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive | NOT RUN | UNKNOWN | UNKNOWN | UNKNOWN | 0.55 |
| qwen3-coder-next | NOT RUN | UNKNOWN | UNKNOWN | UNKNOWN | 0.35 |

**Actual GPU offloaded layers и backend TTFT по-прежнему UNKNOWN.** Их нельзя вывести из GPUpeak, requestedratio или decodeTPS. Для нового final02.10 backendmetrics не подставляются из01.10DEV: другой timestamp и другие запросы. Фактический final clienttiming/usage анализируется отдельно.

Proof/coverage, source raw/manifestSHA и logline ranges сохранены в `outputs/home_pc_final_20261002_analytics7b4c/backend_log_metrics.json` и CSV. Loghash служит provenance файла; значения credentials не печатались. Excel содержит обе скорости в разных колонках.

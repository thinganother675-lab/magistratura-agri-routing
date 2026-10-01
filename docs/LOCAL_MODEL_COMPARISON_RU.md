# Сравнение локальных моделей HOME PC

01.10.2026. Только development: старый test90 не использован для выбора модели. Основные generative кандидаты были установлены до сессии. Полный inventory smoke и отдельный typed decision аналог Jev документируются отдельно.

Основной machine-readable анализ: `results/20261001_home_analysis_d9a7acb8/analysis.json`. Raw и ресурсы сохраняются в отдельных timestamped CLI runs.

## Сопоставимый общий smoke-срез

| Модель | Common correct/n | Quality | N расширенного dev | Correct в расширенном dev | p50 / p95 s | Decode tok/s | TTFT s | VRAM total MiB | RAM system GiB | Ошибки |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3.5-9b | 4/12 | 33.3% | 12 | 4/12 | 1.053 / 1.351 | 42.94 | 0.101 | 11421 | 21.38 | 4 |
| gemma-4-12b-it | 4/12 | 33.3% | 12 | 4/12 | 1.196 / 1.383 | 47.67 | 0.192 | 8593 | 18.24 | 4 |
| qwen3.8-27b | 7/12 | 58.3% | 36 | 25/36 | 3.042 / 4.450 | 14.15 | 0.714 | 15095 | 27.76 | 0 |
| qwen3.5-35b-a3b | 7/12 | 58.3% | 36 | 19/36 | 1.992 / 2.777 | 28.76 | 0.628 | 14187 | 29.79 | 0 |
| gpt-oss-20b | 8/12 | 66.7% | 36 | 28/36 | 3.604 / 8.531 | 106.20 | 0.072 | 12478 | 24.05 | 3 |
| gemma-4-26b-a4b-it | 9/12 | 75.0% | 36 | 21/36 | 1.472 / 2.362 | 36.55 | 0.428 | 13937 | 25.74 | 1 |

## Категории на одном DEV36

| Модель | Compound | QA | Missing | Numeric | Rule | Tool selection | QA mean F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3.8-27b | 3/6 | 4/6 | 4/6 | 2/6 | 6/6 | 6/6 | 0.913 |
| qwen3.5-35b-a3b | 2/6 | 3/6 | 5/6 | 0/6 | 3/6 | 6/6 | 0.868 |
| gpt-oss-20b | 6/6 | 6/6 | 1/6 | 5/6 | 5/6 | 5/6 | 1.000 |
| gemma-4-26b-a4b-it | 1/6 | 4/6 | 4/6 | 0/6 | 6/6 | 6/6 | 0.883 |

Расширенное N различается: Qwen9/Gemma12 остановлены после четырёх format failures на 12 примерах. Их нельзя ранжировать против full36 по несопоставимым долям. Common12 одинаков для основных кандидатов; сравнение full36 парное.

## Интерпретация

Для отдельного offline/replay анализа выбран предварительный context reader gemma-4-26b-a4b-it. Окончательный выбор требует controlled HTTP DEV и парного языкового аудита. GPT-OSS получил 6/6 EN QA в первом full36, но повтор EN дал 4/6. Qwen3.8 27B — стабильный dense comparator с 0 CLI/parser errors на full36 и частичным offload75%. Qwen35-A3B при offload55% быстрее27B, но слабее на full36. Family, quantization, reasoning и offload различаются; причинное преимущество архитектуры не устанавливается.

GPT-OSS визуально возвращает reasoning несмотря на requested off; decode speed включает reasoning tokens. Поэтому106tok/s не означает меньшую end-to-end задержку. Три GPT CLI failures не исчезают из качества/ошибок. Первая попытка6 была остановлена из-за неподдержанной раздельной передачи reasoning/final; raw сохранён, но она исключена из model ranking.

Qwen9/Gemma форматные ошибки могут быть свойством текущего adapter/settings. Нельзя объявлять сами веса непригодными без JSON-schema HTTP pilot. Temperature/max_tokens CLI не проверены. Structured JSON по prompt протестирован; grammar-constrained JSON, native function calls и logprobs через HTTP NOT RUN.

Peak VRAM — sampled total device allocation, RAM — total system use; это не per-model memory. Частота примерно0.5s плюс subprocess overhead, точный максимум мог быть пропущен. GPU layers как фактическое число не доступны: сохранён requested ratio и loaded context4096/parallel1. Prompt-processing speed отдельно не предоставлен CLI.

## Вклад локального reader и offline на DEV

Сохранённые ответы дают routing plan tools+cloud 24/36 → tools+local+cloud 18/36: 25.0% относительного сокращения, 16.67 п.п. от всех запросов. Это ожидаемые эскалации, а не выполненные cloud calls; качество и latency пары с облаком NOT RUN.

Offline v2: 16/36 (44.4%), answers 12, ASK_FOR_DATA 6, ABSTAIN 18; cloud0, local traces6, tools6. Mean/p50/p95 reconstructed 0.271/0.000/1.611s. Это cached trace replay, не live benchmark каждой политики.

Доля правильных abstentions не оценивается: gold ABSTAIN здесь отсутствует. Coverage нужно различать: ответы, уточнения и безопасные отказы. Строгий EM не заменяет агрономическую экспертизу. ManualDEV30.csv содержит только dev и пустые cloud/hybrid NOT RUN.

## Русский язык

В full36 — RU15 controlled и EN21, включая EN6 QA. Эти неодинаковые составы нельзя интерпретировать как причинный языковой эффект. Отдельный paired QA probe имеет шесть source groups, перевод AI-assisted и human validation PENDING; он также dev.

## Ограничение финального вывода

Новый независимый holdout NOT RUN. Окончательное подтверждение гипотезы, качество tools+cloud/hybrid, latency difference и реальные API cost differences не получены. Нужны controlled API revalidation, один fixed cloud baseline, новая независимая выборка и реальная фиксация протокола до её запуска.

Paired dev QA: EN 4/6; RU 5/6; overall 9/12. Вывод только описательный, n_groups6.

| Парный DEV QA | EN correct/6 | RU correct/6 | p50 / p95 s | Errors |
|---|---:|---:|---:|---:|
| gpt-oss-20b | 4/6 | 2/6 | 2.168 / 2.907 | 2 |
| qwen3.8-27b | 4/6 | 5/6 | 3.268 / 4.142 | 0 |
| gemma-4-26b-a4b-it | 4/6 | 5/6 | 1.810 / 2.585 | 0 |

Gemma 26B и Qwen 27B имеют одинаковый aggregate score на этом малом paired probe; Gemma быстрее. Это обосновывает предварительный выбор reader, но не доказывает equivalence или устойчивую русскоязычную generalization.

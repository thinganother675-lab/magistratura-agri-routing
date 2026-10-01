# Выбор данных и происхождение

Дата обращения: 30.09.2026. Наличие названия в paper не считается фактической доступностью файлов.

| Dataset / первичный источник | Размер и язык | Ground truth / scoring | License / доступ / решение |
|---|---|---|---|
| [AgXQA author repo](https://github.com/MSU-CECO/agxqa_benchmark_v1) | Скачанная публичная Part B: **570 вопросов, 155 paragraphs**, EN. Полная работа описывает более широкий corpus; эти числа не смешиваются. | Ответы spans и контекст; EM/token F1. Без images. | Repo Apache-2.0; исходные Extension документы имеют собственное происхождение. Выбрано 120 независимых context groups, один QA на paragraph. |
| [AWM-Bench](https://dsiweb.cse.msu.edu/awm-bench/) | Family: AgXQA, DEW logical/math, FarmPro | Разные schemas, MCQ/semantic parsing/simulation | Не один dataset. DEW/FarmPro license/access отдельно не установлены; в первый run не включены. |
| [AgriLLM eval 800](https://huggingface.co/datasets/AI71ai/agrillm-qa-eval-800) | 800, EN, text | Reference free-form QA; автоматические lexical метрики не равны factuality | Apache-2.0 card. Не выбран: отсутствующие источники в отдельных вопросах и потребность в domain review. |
| [AgroBench author card](https://huggingface.co/datasets/risashinoda/AgroBench), [standardized mirror](https://huggingface.co/datasets/Project-AgML/AgroBench) | 4 342, images + MCQ | Exact option accuracy | Mirror CC-BY-NC-4.0; нужно сохранить attribution и сверить author/original terms. Несколько GB; NOT RUN в text MVP. |
| [AgMMU author card](https://huggingface.co/datasets/AgMMU/AgMMU_v1) | Eval: 746 MCQ и 746 OEQ по card; отдельный AgBase 57 387 facts. Viewer ~50k images не равен eval size. EN. | MCQ exact; OEQ сложнее; images обязательны | Card generic `cc`, точная версия условий UNVERIFIED; огромные archives. Отложен. |
| [AgroTools](https://huggingface.co/datasets/AgroTools/AgroTools), [paper](https://arxiv.org/abs/2605.22366) | 539 QA, 1 097 images, 14 tools | Process traces и executable outcome | License `other`; redistribution UNVERIFIED. Очень близкий prior art, без скачивания raw в этот MVP. |
| Новые controlled scenarios, scripts/prepare_data.py | 240, RU/EN, без images | Независимые formula gold, exact labels, missing-input action | CC0 для новых сценариев. Синтетические, не экспертно размеченные natural agronomist questions. |

## Фактически выбранный corpus

360 samples; train 180, dev 90, test 90. QA: train 60/dev30/test30. Для каждой из пяти controlled categories: train24/dev12/test12. Seed 20260930. Категории: extractive_qa, numeric, missing_data, tool_selection, rule_interpretation, compound_reasoning.

AgXQA groups — hash контекста; дубликаты контекстов удалены, один вопрос на контекст, ответы должны быть точными подстроками. Отфильтрованы contexts длиннее 1600 chars и невозможные/невалидные spans. Это наш deterministic subset/split, **не оригинальный официальный test**, поэтому результаты нельзя ставить рядом с leaderboard без оговорки. Source document identity за пределами paragraph не восстановлена: междокументная/семантическая утечка остаётся риском.

Controlled groups — category и family ID, четыре variants в одном split. При этом вопросы имеют общий шаблон; это chiefly parameter holdout, а не независимые авторы или строгий semantic OOD. RU/EN чередуются по family, но не являются парными переводами. Test-срез не используется для настройки, train оставлен как future development corpus; learned router в текущем MVP не обучался.

Schema каждого sample: id/group/split/category/language/input/context/inputs/expected/scoring/source/license/difficulty. Difficulty отмечена not_assigned: длина контекста не объявляется агрономической трудностью. public_request передаёт только input/context/inputs, скрывая gold/category/split.

Manifest фиксирует dataset hash, upstream commit **8626771b289d48cff113f0c13d0603ac644628c0**, raw hash и число реально прочитанных rows. v0.1 сохранён в data/versions; в v0.2 удалена подсказка правильного названия из tool-selection вопросов. Все completed runs сохраняют собственные samples и hashes.

## Россия и Московская область

Использован [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/): grid point 56.0 N, 37.3 E, 01–07.05.2025, UTC, T2M_MIN/T2M_MAX/PRECTOTCORR, AG community. Raw JSON, unit metadata, URL и hash сохранены. Это открытый метеорологический продукт, не собственные измерения на ферме. Его семь дней не используются как независимый QA benchmark.

Региональная уместность картофеля подтверждается университетскими [исследованиями в Московской области](https://elib.timacad.ru/dl/full/gmgup-10-2025-4.pdf/info). В демо base=5 C — заданное учебное значение; оно **не** выдаётся за физиологический порог сорта или прогноз урожайности. Snapshot достаточен для явно определённой GDD, недостаточен для полной ET0 без дополнительных величин.

Альтернативы: [AgERA5](https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators?tab=overview), ежедневные agricultural indicators с 1979, [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview), [Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api), [NOAA GHCN Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/). Они пригодны для spatial/seasonal расширения, но не содержат автоматически gold пользовательских запросов. Их files не скачивались; license/version, временную агрегацию и покрытие конкретного grid/station нужно зафиксировать перед новым run. Достаточно NASA для первого demonstrator; отдельный российский открытый QA corpus с проверенными rights не установлен.

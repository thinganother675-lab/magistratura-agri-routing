# Аудит внешних данных — 2 октября 2026

Статус: **выполнен аудит файлов и provenance; human_review=false; новый независимый confirmatory holdout НЕ создан**. Исторические 150 примеров и их результаты сохранены. После анализа ошибок они считаются наблюдавшимися данными для всех следующих изменений router/scorer.

Машинные метаданные, SHA-256, схема, пересечения и 40 примеров для человеческого просмотра: [results/20261002_170443Z_21722066_dataset_literature](../results/20261002_170443Z_21722066_dataset_literature/). Скачанные научные PDF, HTML, архив Kaggle и полные сторонние split-файлы хранятся в игнорируемой `.runtime`; никакой скачанный Python-код не исполнялся. Данные получены анонимными публичными запросами, без аккаунтов и чтения браузерных credentials.

## Kaggle: фактически опубликованный пакет пользователя

[SARYCH-LM Instruction-Lite Eval Suite & Research](https://www.kaggle.com/datasets/antoniisarychev/sarych-lm-instruction-lite-eval-suite-and-research): публичная версия 1, обновлена **4 июня 2026, 18:13:48 UTC**, владелец Antonii Sarychev, заявленная лицензия **CC BY-NC-SA 4.0**. Публичный API метаданных, перечень файлов и архив доступны без авторизации. Архив 35 762 байта, SHA-256 `2af3ff37efc81e1b8c178a3cfa80fbcb0825269324d8024dfa4730412639bab6`; 17 файлов, 116 413 байт после распаковки. API `totalBytes` означает здесь распакованный размер, а не размер ZIP.

Это сохранённый checkpoint исследования адаптации маленькой модели приблизительно 30M на TinyStories. Карточка прямо обозначает **NO_GO**, ограниченный набор простых инструкций и отсутствие доказанной детской безопасности. Это другой проект и другой измеряемый конструкт, а не готовый аграрный benchmark для general-purpose LLM.

| Проверка фактических файлов | Результат |
|---|---|
| Evaluation prompts / expected records | 40 / 40, ID A001–A040 |
| Схема prompts | id, category, prompt, expected_behavior, failure_modes, notes |
| Категории | identity_chat 8; simple_explanation 8; simple_list 6; simple_qa 5; story_request 6; simple_reasoning 4; safety_kindness 3 |
| Язык | English; 0 строк с кириллицей |
| Дубли нормализованного prompt | 0 |
| Нет соответствующего expected ID | 0 |
| Совпадения вопросов с 882 строками существующих project JSONL | 0 точных; максимум token-set Jaccard 0,333 — грубая диагностика, не доказательство отсутствия смыслового overlap |
| Реальный accepted training JSONL | Отсутствует |
| Train/eval разбиение, тренировочный overlap | Проверить невозможно по опубликованным артефактам |
| Teacher / происхождение train corpus | Часть workflow описана; полный generation manifest и реальный принятый корпус отсутствуют |
| Агро-пригодность | Предметных аграрных QA, численных агро-tools и русского поднабора нет |

Прочитаны DATASET_CARD, README, LIMITATIONS, MISSING_ARTIFACTS, expected JSON и prompts. Упомянутые в заметках TinyStories/EverydayConversations/Dolly и тренировочные смеси не превращаются в доступные данные: их конечные артефакты и права на конкретные производные отсутствуют. Лицензия пакета не подтверждает права на каждый отсутствующий upstream corpus.

Первичная проверка строк всех 17 файлов: найдено **0 email patterns**, **0 credential-assignment-like patterns**, **31 Windows absolute-path pattern** из старых workflow. Это ограниченный поиск по шаблонам, а не исчерпывающая проверка PII/секретов. Полные пути пользователя и reference scripts не копировать автоматически в новый публичный release. Safety-kindness задания — простые инструкции, а не валидированный детский safety benchmark.

Решение: **USE FOR DEVELOPMENT**, только отдельная версия общих instruction-following/JSON diagnostics после корректной адаптации scoring. Пример identity с обязательным именем «sarych» нельзя честно оценивать у всех моделей как общую способность. **REJECT для нового независимого аграрного holdout**. Тестирования моделей на этом пакете в рамках данного аудита не выполнялось.

## Более подходящие внешние источники

| Источник | Что реально проверено | Права/язык/предмет | Решение |
|---|---|---|---|
| [AgXQA 1.1, официальный HF автора](https://huggingface.co/datasets/msu-ceco/agxqa_v1) | Карточка, metadata и все 3 JSONL; 2 186 строк, train 1 503 / validation 353 / test 330; revision `9fb0cf2a6d03ccfccbd67d5966179b43b5b77e2c` повторно получена и SHA совпали с anonymous main | MIT указана на конкретной HF dataset card; English, irrigation, преимущественно US/Midwest corn/soybean; права первичных Extension документов надо проверять отдельно | **USE FOR DEVELOPMENT / EXTERNAL TEST**, exploratory с source-group split; **HOLD** для независимого confirmatory test |
| [AWM Bench, официальный MSU сайт](https://dsiweb.cse.msu.edu/awm-bench/) | HTTP 200 фактически вернул 212-byte WAF/Incapsula challenge, а не leaderboard; corpus/schema/license недоступны | Нельзя переносить лицензию AgXQA на семейство benchmark; challenge не обходился | **HOLD / NEEDS REVIEW**, ACCESS_BLOCKED; discovery lead, не заявлять download/evaluation |
| [AgriEval, PaperHarvester](https://huggingface.co/datasets/PaperHarvester/AgriEval) | Доступны HF metadata и README; заявлены 20 634 MCQ + 2 104 QA, китайские аграрные экзамены/банки | Заголовок Apache-2.0, дополнительные community restrictions в карточке; русская агро-QA задача и scoring отличаются | **HOLD / NEEDS REVIEW** до согласования полного license/provenance и task adapter |
| [AgriEvalCombined](https://huggingface.co/datasets/rokayon/AgriEvalCombined) | Публичный поиск показывает multilingual карточку; прямые metadata/README запросы дали HTTP 401 | Фактические файлы и upstream translation/gold не проверены | **HOLD**, AUTH_BLOCKED; не обходить доступ |
| [AgroBench, ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/papers/Shinoda_AgroBench_Vision-Language_Model_Benchmark_in_Agriculture_ICCV_2025_paper.pdf) | Первичный научный источник обнаружен; benchmark image+text | Другая модальность, не текстовая irrigation-routing абляция | **REJECT для текущего сравнения**; научно полезен для будущей VLM работы |
| [AgriGPT / AgriBench-13K](https://arxiv.org/abs/2508.08632) | Прочитаны Data Engine, training, evaluation, generalization и multilingual разделы PDF | Смешанная синтетика/teacher augmentation, 13 задач; reported Chinese/Japanese transfer не доказывает русский; реальные файлы/license здесь не проверены | **HOLD / NEEDS REVIEW**, потенциальный external stress test после corpus/rights audit |
| [Open-Meteo ERA5 historical API](https://open-meteo.com/en/docs/historical-weather-api) | Сохранён один ответ: 20 дней 1–20 мая 2025, Moscow, Tmax/Tmin/precipitation/ET0; HTTP 200, JSON schema, units и координаты проверены | CC BY 4.0 данные; бесплатный API ограничен noncommercial use; public-institution research допустим по [условиям](https://open-meteo.com/en/terms) | **USE FOR EXTERNAL TEST**, controlled exploratory weather/tool cases; не полевые измерения и не готовый natural QA gold |

Научный источник AgXQA: Kpodo, Kordjamshidi, Nejadhashemi (2024), *AgXQA: A benchmark for advanced Agricultural Extension question answering*, Computers and Electronics in Agriculture 225:109349, [DOI](https://doi.org/10.1016/j.compag.2024.109349). HF tag `arxiv:1606.05250` относится к SQuAD, **не** к статье AgXQA: не использовать его как citation AgXQA. Старый локальный Git-корпус имеет repository LICENSE Apache-2.0, а новая конкретная HF карточка MIT; эти лицензии относятся к разным артефактам, общий upstream copyright всё равно требует проверки.

## AgXQA: почему официальный test нельзя автоматически считать независимым

Сравнены ID, нормализованные вопросы, SHA-256 exact context и строка `references`. Старый локальный `annotations.json` содержит 570 QA. Эти проверки не выявляют неизвестное pretraining contamination моделей.

| Split | Строк | Source groups | Unique contexts | Дубли вопроса внутри split | Вопросы из прежних 570 | Контексты из прежних 570 |
|---|---:|---:|---:|---:|---:|---:|
| train | 1 503 | 76 | 374 | 29 | 426 | 154 |
| validation | 353 | 41 | 159 | 1 | 60 | 23 |
| test | 330 | 46 | 183 | 3 | 78 | 25 |

| Между splits | Общие source groups | Общие точные contexts | Общие нормализованные questions |
|---|---:|---:|---:|
| train / validation | 38 | 148 | 5 |
| train / test | 44 | 170 | 4 |
| validation / test | 39 | 125 | 3 |

После исключения test источников, присутствующих в train/validation, и старых известных контекстов/вопросов остаётся **1 запись**. Этого недостаточно для честного holdout 120–200 примеров или 30–40 полностью независимых external QA. Пересечение по `references` — консервативная документная группировка; изменения написания библиографии могут скрывать дополнительные совпадения. Не пересоздавать случайный row split и не приравнивать 330 строк к 330 независимым наблюдениям.

## Подготовленный human-review pack

[human_review_pack](../results/20261002_170443Z_21722066_dataset_literature/human_review_pack/) содержит **40 строк = 20 авторских сценариев × RU/EN**. Численные значения происходят из лицензированного публичного ERA5 ответа, текст задач и экспериментальные пороги созданы для проверки. Категории: numeric 10; rule 6; compound 8; insufficient_data 8; provenance 4; abstention 4. Это **100% controlled synthetic/derived-weather cases, EXPLORATORY_UNRUN**. Один общий погодный блок, поэтому 20 сценариев не означают 20 независимых источников. Никакой LLM на этих ID не запускался; ID не использовать для DEV настройки.

`blinded_questions.csv/jsonl` не показывают предварительный gold, model answers и provider identities. Antonii и Denis должны независимо заполнить свои action/answer/confidence/notes, затем сверить отдельный `provisional_gold_separate.csv/jsonl`, обсудить спорные случаи и сохранить adjudicated новую версию. Сейчас человеческие поля пусты, **human_review=false**. Даже правильный Decimal расчёт не заменяет предметную проверку формулировки и допущений.

Погодные данные — grid reanalysis ERA5, не sensor ground truth фермы. Запрошенная longitude **37.62**, возвращённая grid longitude **37.5**; metadata сохранена. ET0 API — модельная reference evapotranspiration, не измеренное потребление культуры. GDD использует явно заданное основание; missing-input случаи не подставляют типовые параметры. Deficit-примеры содержат упрощения «все осадки эффективны» и «нет runoff/storage» и не представляют реальные рекомендации по поливу.

Отдельное исправление integrity: [manifest_v2_integrity_20261002.json](../results/20261002_170443Z_21722066_dataset_literature/human_review_pack/manifest_v2_integrity_20261002.json) исключает self-hash и фиксирует hash окончательного README; provenance прежних записей сохранена. [delivery_manifest_v2.json](../results/20261002_170443Z_21722066_dataset_literature/delivery_manifest_v2.json) отражает актуальные файлы. Исходный manifest, вопросы и provisional gold не перезаписаны, human_review остаётся false; генератор повторно не запускался.

Последующее усиление сохранности подтверждено [offline integration smoke](../results/20261002_170443Z_21722066_dataset_literature/review_pack_generator_integration_20261002.json): в новой `.cache` папке получены 40 строк и пять корректных hashes без self-hash; повтор в существующую папку отвергнут до чтения weather source. Семь исходных файлов unchanged, provider requests=0, human_review=false. [delivery_manifest_v3.json](../results/20261002_170443Z_21722066_dataset_literature/delivery_manifest_v3.json) содержит текущую опись после этого guard и ссылки на точный [snapshot генератора](../results/20261002_170443Z_21722066_dataset_literature/builder_snapshot_20261002.py). V1/V2 остаются датированными archival records; это проверка воспроизводимости файлов, не запуск моделей и не новое подтверждение gold.

## Что необходимо для следующего независимого набора

1. Новые внешние документы/погодные периоды или независимые farm scenarios, разрешение на reuse и проверенный источник; источники не пересекаются с DEV и уже наблюдавшимся old150.
2. Независимый человеческий gold для QA, ASK/ABSTAIN, numeric inputs/units, complete compound actions. Согласовать различие ASK и ABSTAIN.
3. Разбиение по исходному документу/сценарию/погодному блоку; EN/RU перевод всегда в одной группе. Сохранить нативный текст и факт перевода.
4. Зафиксировать model/prompt/router/scorer до inference; gold не использовать для настроек; 120–200 строк означают меньше независимых групп, что отражается в статистике.
5. После freeze выполнить новый holdout один раз. Этот аудит и текущий 40-case pack не считаются таким запуском.

# Дизайн эксперимента

Срез 30.09.2026. Это воспроизводимый exploratory experiment первого этапа, не оценка готового агрономического сервиса.

## Задачи и gold

| Категория | Задача | Оценка | Предметное ограничение |
|---|---|---|---|
| extractive_qa | Краткий ответ из предоставленного сельскохозяйственного paragraph | Нормализованный exact match и token F1 | Только supplied-context QA, retrieval не оценивается |
| numeric | GDD, single-temperature VPD, daily FAO-56 ET0, разность заданной цели и осадков | Action ANSWER, число с abs tolerance 0.02 или rel 1%, точная единица | Порог/цель задаёт сценарий, не культура |
| missing_data | Пропущенный обязательный вход или неподдержанная единица | ASK_FOR_DATA | Текст уточнения не оценивается семантически |
| tool_selection | Выбор одного из четырёх исполнителей без расчёта | Exact tool label | Подсказка ID удалена в v0.2 |
| rule_interpretation | Применение явно заданного температурного правила | RISK/NO_RISK | Формальная логика, не crop diagnosis |
| compound_reasoning | Совместное условие тепловой суммы и осадков | ALERT/OK | Без реального решения о поливе |

360 samples: 120 AgXQA paragraphs и 240 controlled examples. Train/dev/test 180/90/90. В test 30 QA и по 12 остальных категорий. Macro average по всем запросам здесь sample-weighted: QA занимает 1/3; дополнительно сохраняются категории и RU/EN. Контексты AgXQA и controlled families разделены по группам. Общая структура шаблонов остаётся; это не строгий semantic OOD. Разбиение и seed фиксируются до запуска моделей. Подробности происхождения в DATASET_REVIEW_RU.md.

## Сравниваемые методы

1. local: прямой ответ локальной модели без numerical gate.
2. cloud: прямой ответ Mercury без numerical gate.
3. rule: общий gate; оставшиеся вопросы идут в cloud при длине question+context выше dev-порога, иначе в local.
4. cascade: общий gate; локальная попытка; принимается только ANSWER, дословно поддержанный контекстом; иначе cloud.
5. tool_cloud: тот же gate, затем сразу cloud. Это обязательная абляция вклада локального LLM.
6. offline: gate, local, проверка поддержки; при неудаче ABSTAIN, cloud не вызывается.

Gold-informed local/cloud oracle — отдельная диагностическая верхняя граница без инструментов. Она недоступна runtime. Learned router не обучен: текущих независимых labels недостаточно для убедительной калибровки. Правило support не является confidence score; ECE/Brier к нему неприменимы.

## Пилот и фиксация

Первый пилот 36 dev-запросов: Qwen3.5-0.8B Q4_K_M / Mercury 2. После него исправлены tool-selection hint, учёт отсутствующего ответа в критических ошибках и metadata модели. Второй пилот 36 dev: Qwen3.5-2B Q4_K_M / Mercury 2.5. Пилотные пары моделей меняются совместно, поэтому разность между пилотами нельзя приписывать одному размеру локальной модели.

До первого test-вызова `freeze` выбирает rule threshold из сетки 400/900/1600 chars по dev-quality, затем cost. Сетка — локальный выбор MVP, не пороги RouteLLM. Protocol записывается create-new в data/protocol_frozen.json. Quality utility margin = min(0.05, max(1/n_dev, abs(Q_cloud-Q_local)/2)); target cloud reduction = половина dev reduction; critical error margin = 0. Это pilot-derived exploratory planning rule, а не доказанное агрономическое определение приемлемости. Для confirmatory статьи margin нужно заранее согласовать с руководителем и доменным экспертом на новом test.

H1 оценивается по инструментальной абляции и критическим ошибкам. Общий hybrid utility target требует lower paired quality CI >= -margin, cloud reduction >= target и upper critical-error difference CI <=0. H2 дополнительно требует экономии local-stage относительно tool_cloud без значимой потери качества. Если инструменты выиграли, а local-stage нет, H2 не подтверждена. Test не используется для пересмотра порогов или prompt.

## Исполнение и метрики

Каждый sample получает реальный local и cloud ответ с одинаковым SYSTEM_PROMPT, temperature=0, max_tokens=512; local seed42, reasoning off; cloud instant. Чередуется порядок local/cloud, вызовы последовательны. API alias не фиксирует неизменяемые веса provider; сохраняется фактический `raw.model`. Endpoint timeout60s, платных автоматических повторов нет. Ошибки входят в denominator.

Cached paired responses позволяют воспроизвести политики без новых API расходов. HTTP latency individual models измерена; cascade latency складывается из выбранных реальных стадий и времени replay-gate. Это **reconstructed trace latency**, не независимый live end-to-end замер каждой политики. Отдельный live smoke test проверяет фактический UI→API→executor/model→UI путь; не заменяет performance trial. Prompt-cache runtime может влиять на последовательные замеры. Cold/warm distinction и GPU сравнение в первом этапе не исследованы.

Сохраняются correctness и 95% clustered bootstrap CI (group, 2000 draws, seed42), cloud/local/tool call rates, answer coverage, selective error, operational critical errors, QA F1, mean/p50/p95 latency, usage и cloud cost. Critical error — неправильный ANSWER в numeric/missing_data, не любой отказ. Отсутствие ответа снижает quality, но не означает ложную агрономическую рекомендацию. Это proxy, не safety validation и не универсальная hallucination rate.

Paired quality/critical differences bootstrap по тем же groups. McNemar exact p — описательный: correlated variants нарушают independent-pair assumption, multiple comparisons не корректированы. Cluster CI предпочтительнее; маленькое число families делает CI нестабильным. Wilcoxon для реконструированной задержки не навязывается. Неэквивалентные модели, инструменты и cost access явно раскрыты.

Стоимость: usage input/output × опубликованные uncached цены, cache discount не применён. Missing usage → unknown, не ноль. $/1000 — линейный пересчёт, не 1000 фактических вызовов. Ограничение $1 upper estimate на paired run. Локальная энергия и амортизация не измерены; local cloud bill=0 не означает бесплатную обработку. Raw, normalized и analysis разделены; завершённые файлы не перезаписываются.

## Надёжность и необходимые следующие проверки

Unit/range mismatch, missing inputs, no gold leakage, definition versus execution, malformed JSON, timeout, cloud unavailable и verifier false-positive покрыты тестами. Фактические wrong answers сохраняются как failures. Prompt injection, полнота всех русских парафраз, полномасштабный RAG и устойчивость к произвольному runtime overload ещё не оценены.

Следующий эксперимент: на отдельном PC выбрать 2–3 реальные GGUF artifacts, одну фиксированную cloud модель, новый expert-reviewed RU/EN corpus с source-document split, calibration subset, сетку cost budgets и независимый semantic holdout. Затем learned/pre-generation router сравнить с tool_cloud, random cost-matched routing и source-supported cascade на одном оборудовании. Это продолжение исследования, а не условие работоспособности текущего MVP.

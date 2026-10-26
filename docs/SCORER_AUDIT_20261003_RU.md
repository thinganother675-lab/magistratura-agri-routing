# Аудит scorer и слепая человеческая проверка — 03.10.2026

**Исторические HOME150 scores заморожены.** Новый этап — независимая диагностика уже наблюдавшихся ответов и кандидат DEV scorer/verifier v2. Нового inference, human review или confirmatory эксперимента здесь нет. Новый protocol freeze остаётся **DATA_BLOCKED**: программные тесты не заменяют человеческий gold и независимые источники.

Авторитетный diagnostic run: [20261003_045910Z_cf66b554_scorer_audit](../results/20261003_045910Z_cf66b554_scorer_audit/summary.json). Исходный reconciled raw имеет SHA256 `70cdc82fe4d9f01a09b10287304c6a7f7f25f61d13c3fbdab91c1cf7c0a6e922`. Таблицы содержат неизменённый historical score, независимо пересчитанную опору и отдельные диагностические признаки; они не заменяют raw и не создают новый вариант HOME150 accuracy.

Для 30 LOCAL numeric ответов получено:

| Диагностическая причина | Число строк | Что установлено |
|---|---:|---|
| Неверный численный результат по заданной формуле | 30 | Все вне исходной tolerance 1% relative / 0.02 absolute |
| Несовпадение unit | 0 | Все output units совпадают с исходным gold |
| Schema/action | 0 | ANSWER и конечное числовое поле во всех 30 |
| Formatting | 0 | Нет markdown wrappers в raw final content |
| Parsing | 0 | Raw JSON и сохранённый parsed output совпадают |
| Incomplete response | 0 | Finish=stop, поток завершён |
| Обнаруженный evaluator artifact | 0 | Независимая формула согласна с исходным gold 30/30 |

Классы могут пересекаться; тест специально проверяет одновременное обнаружение неверного числа, unit и неполного ответа. В этой серии пересечения не обнаружены. Число в текстовом answer также равно numeric во всех 30. Это исключает объяснение результата `0/30` простой потерей поля/единицы или парсером в этих записях. Raw не содержит вывод формулы по шагам: отличить неверную арифметическую операцию от выбора иной формулы невозможно. Поэтому причина называется `arithmetic_or_formula`, а не выдуманный конкретный механизм ошибки модели.

Независимый reference использует Decimal с precision 50 для GDD, rainfall deficit, VPD и ET0, включая Decimal.exp для VPD; исходные `tools.execute` и `evaluation.score` при диагностике не вызываются. Значения параметров FAO56 используются такими, как они явно заданы в историческом task, без их повторного оценивания из другой погоды. Historical tolerance рассчитана по исходной семантике math.isclose с максимумом величин результата и gold.

Построчная таблица: [JSON](../results/20261003_045910Z_cf66b554_scorer_audit/home150_local_numeric_diagnostics_v2.json), [CSV](../results/20261003_045910Z_cf66b554_scorer_audit/home150_local_numeric_diagnostics_v2.csv). Хеши защищённых исходников, data/protocol и старых result файлов: [frozen_historical_hashes.json](../results/20261003_045910Z_cf66b554_scorer_audit/frozen_historical_hashes.json). Inventory включает Git-tracked исторические source/test/data/protocol и все файлы каталогов результатов до 03.10; текущие новые untracked scripts исключены. Проверка до/после аудита — PASS.

В compound категории независимо пересчитаны heat, precipitation, оба строгих сравнения и AND. Gold согласен с независимым расчётом во всех 100 policy decisions (20 задач × 5 policies). **Hybrid и offline реально приняли по 12 неправильных ветвей через literal verifier.** В fixed LOCAL также 12 неправильных ответов с токеном, присутствующим в контексте, но verifier там не определял маршрут; это отдельно отмечено как `literal_would_accept_false_branch`. Ни наличие ALERT/OK в публичном описании двух ветвей, ни узкий historical critical_error не доказывают правильности выбранной ветви.

Compound таблица: [JSON](../results/20261003_045910Z_cf66b554_scorer_audit/home150_compound_diagnostics_v2.json), [CSV](../results/20261003_045910Z_cf66b554_scorer_audit/home150_compound_diagnostics_v2.csv). Первый новый diagnostic `20261003_045441Z_59b9e788_scorer_audit` сохранён: он объединял fixed-local потенциальный literal pass с фактическим verifier acceptance. Следующий `20261003_045520Z_1bd51445_scorer_audit` исправил интерпретацию. Финальный run дополнительно уточнил historical inventory, чтобы не включать параллельно создаваемые новые source files. Исторические таблицы и conclusions не менялись.

Кандидат v2 находится в [scoring_v2_dev.py](../src/agro_route/scoring_v2_dev.py). Он не подключён к существующему router или историческому scorer. `score_dev(sample, output)` принимает только `split=dev` и новый `expected_v2`; HOME150/review40 ID и любой final/test split отвергаются. Проверяются action, конечные числа, отдельные units, согласованность численного display, полные components, точные ответы с сохранением отрицания/сущностей/пунктуации. Для единиц допустимы только перечисленные типографические RU/EN aliases (например mm/мм); преобразования cm→mm или day→window автоматически не выполняются. Для ASK_FOR_DATA требуется полный набор конкретных `requested_fields` и `reason_code=MISSING_INPUTS`; для ABSTAIN — `reason_code=INSUFFICIENT_REFERENCE`, отсутствие numeric/components и, при заданных reference answers, точный утверждённый текст. Семантика произвольного объясняющего текста этим кодом не гарантируется; для проверяемого отказа следует задавать утверждённые reference answers.

Минимальный DEV reference:

```json
{"id":"new_dev_001","split":"dev","expected_v2":{"action":"ANSWER","numeric":2,"unit":"mm","rel_tol":0.01,"abs_tol":0.02}}
```

`verify_public_dev(request, output)` получает только `input`, `context`, `inputs` и не получает `expected_v2`. `public_request_v2` выполняет deep projection и рекурсивно отвергает expected/gold/provisional aliases и другие перечисленные private evaluation keys. Тест доказывает одинаковый public payload при изменении hidden gold/category; проверены вложенные alias variants. Этот синтаксический guard не способен доказать, что автор не спрятал смысл gold в произвольной строке. Поэтому provenance публичного contract должен проверяться человеком до freeze.

Typed `inputs.verification` — **формальное авторское DEV семейство задач**. Допустимы:

- `kind=rule`: публичные facts с entity/field/value/unit/id, одна запрошенная entity, полностью заданное дерево all/any/not и сравнения, обе публичные branches. Проверяются все атомы даже после ложного первого условия; output evidence_ids должен покрывать все используемые факты.
- `kind=fact`: публичный заданный inventory текстовых фактов, entity и field. Ответ должен совпадать с полной записью и её evidence ID. Отсутствие записи позволяет принять ABSTAIN только при явно объявленном `scope=closed_world_supplied_facts`; это ограничение формальной задачи, не вывод о полноте реального Extension документа.
- `kind=calculation`: явно названный existing tool, полный публичный required_fields и measurements. Он сверяет ответ с deterministic executor. Это проверка вычисления по публичным измерениям, а не независимое подтверждение качества upstream источника.

Нельзя строить public facts, branches, summaries, required_fields или closed-world scope из hidden expected_v2, provisional gold, target labels или просмотренных final answers. Contract должен происходить из заранее заданной полной постановки и опорных данных, включая все ветви и условия. Нельзя помечать естественный QA как `kind=unsupported` по его gold: такой маркер специально отвергается. Untyped natural-language QA, неподдержанная структура, неизвестная entity/units или неоднозначный inventory возвращают **UNKNOWN / accepted=false**. Здесь нет универсального semantic entailment verifier; нельзя выдавать typed DEV success за проверку natural QA.

51 новых целевых tests — **PASS**: conjunction, negation, strict/equality branches, wrong entity, неполные compound компоненты/evidence, lexical overlap, units/display, schema/duplicate JSON/nonfinite values, insufficiency, ASK/ABSTAIN, противоречивый текст ASK при заданных reference answers, неизменность public payload при изменении gold, запрет HOME150/review40 rescore, Decimal boundaries и reviewer workflow. Test fixtures с заполненными synthetic judgments существуют только во временной директории pytest, явно обозначены как fixtures и не являются реальной человеческой проверкой. Скрипты pytest использовали отдельный workspace basetemp: sandbox runtime запрещал создание обычного pytest temp, поэтому тесты выполнены с разрешённой эскалацией для локальной записи временных файлов.

Чистые формы Reviewer A — Antoniy Sarychev, Reviewer B — Denis Shesternin находятся в [clean_human_review40](../results/20261003_045520Z_1bd51445_scorer_audit/clean_human_review40/manifest.json): [Antoniy CSV](../results/20261003_045520Z_1bd51445_scorer_audit/clean_human_review40/reviewer_A/reviewer_A_antoniy.csv), [Denis CSV](../results/20261003_045520Z_1bd51445_scorer_audit/clean_human_review40/reviewer_B/reviewer_B_denis.csv). Reviewer folders содержат reference_weather.json и инструкции, без model/policy/provisional gold/category. Порядок независимый, IDs обезличены; private ID mapping отделён. Исходный review pack и все его хеши сохранены. **human_review=false**, обе формы пустые; публикация или отправка человеку не выполнялась.

Review40 — 40 незапущенных вопросов, а не model answers. Поэтому judgments CORRECT / INCORRECT / AMBIGUOUS / INSUFFICIENT_REFERENCE / TRANSLATION_PROBLEM / DOMAIN_EXPERT_NEEDED оценивают постановку и достаточность опоры. При CORRECT человек независимо заполняет action и reference_answer, для численного gold — numeric/unit. Это не manual model accuracy. Один ERA5 source block и 20 translated pairs не становятся независимой confirmatory выборкой после заполнения форм. Экспертная агрономическая проверка не подразумевается; DOMAIN_EXPERT_NEEDED сохраняется как unresolved.

Скрипт [human_review_workflow_20261003.py](../scripts/human_review_workflow_20261003.py) требует обе полные возвращённые формы и отдельные human attestations (имя, completed_by_human=true, фактическое timezone-aware время после создания pack, SHA256 соответствующего returned CSV). Он проверяет все IDs, неизменность вопросов/reference, допустимые judgments, отсутствие пропусков, конечные numeric/unit и сохранность исходных файлов. Attestation — заявление человека с provenance, не техническое доказательство его личности или независимости. Blank form отвергается даже с attestation; до проверки обоих reviewers output не создаётся. Он создаёт только новую adjudication directory с input SHA256 и двумя исходными оценками. Совпадающий CORRECT/action/answer/numeric/unit становится AGREED_GOLD_CANDIDATE; расхождения и DOMAIN_EXPERT_NEEDED не решаются машиной. `final_gold_frozen=false` и `confirmatory_eligible=false` сохраняются даже после согласованных кандидатов: требуется авторское научное решение и отдельный freeze.

Команда после фактического возврата обоих humans (пути к возвращённым CSV/attestations задают авторы):

```powershell
.venv\Scripts\python.exe scripts\human_review_workflow_20261003.py adjudicate --pack results\20261003_045520Z_1bd51445_scorer_audit\clean_human_review40 --form-a <returned_A.csv> --attestation-a <attestation_A.json> --form-b <returned_B.csv> --attestation-b <attestation_B.json> --output <new_adjudication_directory>
```

Готовность: diagnostic audit DONE; candidate DEV v2 и adversarial software verification DONE; reviewer workflow PREPARED; реальный human gold / adjudication NOT RUN; natural-QA semantic verifier PARTIAL/UNKNOWN; source-disjoint protocol freeze DATA_BLOCKED; confirmatory experiment NOT RUN. Необходимы реальные независимые формы Antoniy/Denis, author adjudication, domain expert для отмеченных claims, внешние source-disjoint groups и фиксированный публичный task contract до первой final generation.

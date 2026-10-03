# DEV replay и повторное покрытие исходного screen

3 октября 2026. Основной [final_analysis.json](../results/20261003_local_screen_571682f5/final_analysis.json) заморожен с SHA256 `a097fc75056a4477cf452e0064464eaa8da7eb3fffe0ee894c59bc70a7d10f44`. Этот appendix отдельно связывает его с [независимой проверкой перекрытия DEV60](../results/20261003_local_screen_session/independent_qa_overlap_20261003T093341.json), SHA256 `efe3f26cab8c294a9c86ead669d0220e6cf127f40eb66b06d68bcf2a9eaabfb1`, и [финальным QA](../results/20261003_local_screen_session/independent_qa_final_20261003T093559.json), SHA256 `2bc09eb226f7b742aad9fa60a050e4a9e5051fb73bb84f71f0748d604bc47479`. Основной analysis и его759 provenance claims не переписаны.

Все пять shortlist моделей на общих60 вопросах получили одинаковые request parameters, system и user prompts в обеих стадиях. Четыре модели повторили все60 пригодных наборов вариантов; Qwen4 повторил59 пригодных и один тот же invalid набор. Изменений strict-correctness на59 разбираемых references не было. Это проверка сохранения протокола и результатов на перекрытии; **DEV293 включает DEV60 и не является независимым holdout**. Совпадение seed/temperature вообще не гарантирует идентичность outputs; совпадение здесь проверено по фактически сохранённым ответам.

Все72 комбинации восьми завершённых local models и девяти exploratory thresholds пересчитаны из сохранённых commonDEV60 outputs. Сетка `[None,.5,.7,.8,.9,.95,.98,.99,1]` объявлена после наблюдения screenDEV, до offline grid evaluation. Выбор минимизирует долю cloud при EM≥cloud−5п.п., затем предпочитает больший F1 и меньший threshold. Это post-DEV разработка, а5п.п. требуют согласования авторами; confirmatory non-inferiority не проверена.

| Модель/правило на общем DEV60 | Cloud /60 | STRICT_SET_EM | STRICT_SET_F1 | Потенциальное сокращение вызовов против cloud-only |
|---|---:|---:|---:|---:|
| Mercury2.5 instant512 direct, cloud-only | 60 | 31/59 =52.54% | .657627 | 0% |
| Qwen27, только format/transport/abstain fallback, thresholdNone | 0 | 38/59 =64.41% | .733898 | 100% |
| Qwen9, то же правило | 0 | 37/59 =62.71% | .720743 | 100% |
| Qwen4, exploratory lexical threshold.5 | 25 | 29/59 =49.15% | .704237 | 58.33% |
| Gemma12, exploratory lexical threshold.99 | 27 | 32/59 =54.24% | .710573 | 55.00% |

Для primary Qwen27 правило вырождается в local-only: пригодный формат не обнаруживает его неправильные ответы. Поэтому100% потенциального сокращения здесь не доказывают пользу confidence-routing или надёжность каскада. Польза confidence не установлена. Результат Qwen4 показывает только exploratory DEV tradeoff:25 потенциальных cloud calls и EM на2/59 ниже cloud-only. Он не заморожен для private TEST, не доказывает неухудшение и не определяет безопасность агрономических советов.

Routing каждого вопроса использует только наблюдаемые local signals: пригодность набора, ошибку исполнения, abstention и при наличии геометрическое среднее вероятностей выпущенных choice tokens. Gold используется для DEV-выбора threshold и оценки, не для routing decision. Эти logprobs не являются калиброванной вероятностью правильности; self-reported confidence не запрашивалась.

Статус всех строк каскада — **SIMULATED / SAVED_DEV_OUTPUTS_ONLY**. Фактически сэкономлено0запросов: cloud outputs уже получены для сравнения. Live latency/cost savings не измерены. Cloud DEV293 отсутствует, поэтому качество каскада на293 не известно. Предложение primary format-only с confidenceNone и отдельный [private TEST draft](../experiments/mera_private_test_protocol_draft_20261003.json) остаются незамороженными; [readiness](../results/20261003_local_screen_session/private_test_readiness.json) содержит девять blockers. TEST не запускался.

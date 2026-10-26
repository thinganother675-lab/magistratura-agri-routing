# Локальный screen ruTXTAgroBench DEV: 3 октября 2026

Статус: **DEV / DEVELOPMENT_ONLY**. Исторический HOME150 и исходные рукописи сохранены. Частный TEST не запускался, официальная серверная оценка отсутствует. Серия `20261003_local_screen_571682f5`.

Проверенный хост: Ryzen7 8700F, RAM31.620GiB, RTX5060Ti16GB (16311MiB); LMStudio0.4.25+1, endpoint `http://127.0.0.1:1234`. Установлены24inventory entries, назначены10generaltext конфигураций; один Qwen4 duplicate byte-identical и не считается отдельной архитектурой. Глобальный runtime `llama.cpp-win-x86_64-nvidia-cuda12-avx2@2.51.0`, per-model runtimeidentity UNKNOWN. Полный безопасный inventory, scope exclusions и измеренные SHA — `inventory_analysis.json`, `inventory_scope_review.json`, `installed_weight_checksums.json`; source-linked claims — `CLAIM_PROVENANCE_SCREEN_INVENTORY_20261003.json`.

Идентичность оцениваемой конфигурации задаётся локальным GGUF SHA256, а не одним displayname. Исходный upstream receipt `weight_upstream_identity.json` сопоставил8/10 GGUF с текущими public HF LFS hashes; два установленных Gemma не совпали с текущим revision/filename. Новая отдельная проверка `weight_upstream_historical_verified.json` нашла точные исторические SHA256+size для обоих Gemma:12B revision `faacc07cd184152e87f520a91e1112947b0751da`,26B revision `b68961b3c96e42475123a39fe3f8aa149163cf8b`. Поэтому опубликованная fileidentity подтверждена для всех10 конфигураций:8current+2historical. Установленные bytes и исходные receipts сохранены. Installation-time repo revision и семантическая причина отличия от latest остаются UNKNOWN; latest alias не задаёт tested artifact. Подробности — [приложение об идентичности весов](MERA_WEIGHT_IDENTITY_APPENDIX_20261003_RU.md), provenance `CLAIM_PROVENANCE_SCREEN_UPSTREAM_20261003.json`.

Для десяти кандидатов назначена одна фиксированная выборка DEV60 по историческому selector: по шесть задач десяти исходных дисциплин, распределённых по ID без обращения к gold. Фактически восемь моделей завершили60/60, GPTOSS20 получил одну benchmarkзадачу без успешного завершения, Qwen35 не дошёл до benchmarkвызовов из-за loadguard. System/JSON контракт, исходный prompt, контекст2048, reload каждые10 задач и синтетический warmup одинаковы; запрос temperature0, top_p1, seed42, max_tokens512. Off/low reasoning и GPU ratio по модели записаны как явные поддерживаемые исключения. Результаты полного DEV293 используются для разработки выбора, а не независимого подтверждения.

STRICT_SET_EM — точное совпадение множества; STRICT_SET_F1 — среднее per-question multilabel F1=2|intersection|/(|gold|+|prediction|). Только presentation normalization, латинский A сохраняется. Кириллические gold не исправлялись: знаменатель59/60 на screen и289/293 на полном DEV; original referenceissues видны. Conservative all-N — нижняя граница покрытия при нулевом вкладе unresolved, не известная истинная неправильность gold. Ошибки/незавершённые outputs дают0.

## Stage1: одинаковый DEV60

| Модель / квант | Статус; попытки / завершено | EM (correct/N) | F1 | invalid / errors | p50 / p95, с | GPU / RAM peak |
|---|---|---:|---:|---:|---:|---:|
| `gemma-4-12b-it` / {'name': 'Q4_K_S', 'bits_per_weight': 4} | COMPLETE; 60/60 | 25/59 = 42.37% | 0.651 | 0/0 | 0.529 / 0.630 | 8537.000 MiB / 18.767 GiB |
| `gemma-4-26b-a4b-it` / {'name': 'IQ4_NL_XL', 'bits_per_weight': 4} | COMPLETE; 60/60 | 33/59 = 55.93% | 0.730 | 0/0 | 0.818 / 0.986 | 13850.000 MiB / 25.438 GiB |
| `gpt-oss-20b` / {'name': 'Q8_0', 'bits_per_weight': 8} | PARTIAL; 1/0 | 0/1 = 0.00% | 0.000 | 1/1 | 5.057 / 5.057 | 12220.000 MiB / 20.339 GiB |
| `granite-4.1-8b` / {'name': 'Q4_K_M', 'bits_per_weight': 4} | COMPLETE; 60/60 | 14/59 = 23.73% | 0.473 | 0/0 | 0.238 / 0.348 | 6382.000 MiB / 14.511 GiB |
| `minicpm5-1b` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 60/60 | 0/59 = 0.00% | 0.429 | 0/0 | 0.087 / 0.111 | 2053.000 MiB / 10.064 GiB |
| `phi-4-mini-instruct` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 60/60 | 4/59 = 6.78% | 0.450 | 1/0 | 0.231 / 0.453 | 5281.000 MiB / 12.987 GiB |
| `qwen3.5-35b-a3b` / None | FAILED_LOAD; 0/0 | 0/0 = UNKNOWN | UNKNOWN | 0/0 | UNKNOWN / UNKNOWN | 5193.000 MiB / 17.920 GiB |
| `qwen3.5-9b` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 60/60 | 37/59 = 62.71% | 0.721 | 0/0 | 0.313 / 0.418 | 11327.000 MiB / 20.535 GiB |
| `qwen3.8-27b` / {'name': 'Q4_K_M', 'bits_per_weight': 4} | COMPLETE; 60/60 | 38/59 = 64.41% | 0.734 | 0/0 | 1.406 / 1.896 | 14113.000 MiB / 28.740 GiB |
| `unsloth/qwen3.5-4b` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 60/60 | 19/59 = 32.20% | 0.557 | 1/0 | 0.237 / 0.322 | 7031.000 MiB / 16.041 GiB |

`n_attempted` включает ошибки; `n_completed` — полученные error-free завершённые responses. Partial проценты только описательны, не входят в основной ranking. Invalid обозначает непригодный набор/формат; ошибки исполнения отдельны. Published-compatible scorer сохраняется исключительно диагностически и не называется official MERA score.

Причины неполного выполнения: `[{"model_key": "gpt-oss-20b", "status": "PARTIAL", "stop_reason": {"type": "IncompleteCompletion", "finish_reason": "length", "stream_done": true}, "model_load_failure": false}, {"model_key": "qwen3.5-35b-a3b", "status": "FAILED_LOAD", "stop_reason": {"type": "TimeoutExpired", "resource_guard": null}, "model_load_failure": true}]`. Qwen35 не установил OOM: resourceguard потерял ответ `nvidia-smi` через10s во время load, после чего кандидат безопасно выгружен. GPTOSS20 завершил warmup, но первый benchmarkresponse исчерпал512tokens с reasoninglow; качественный ranking для него отсутствует. Native quant labels не гарантируют однородное хранение: GPTOSS descriptor `Q8_0` фактически имеет91.3723% storedtensor-elements MXFP4,8.5838% Q8_0 и0.0439% F32 по GGUF header; это не распределение активных параметров. Точные native IDs, bytes/checksums и actualtensor types — `installed_weight_checksums.json` и `installed_gguf_tensor_types.json`.

## Замороженный shortlist

Модели: `qwen3.8-27b`, `qwen3.5-9b`, `unsloth/qwen3.5-4b`, `gemma-4-26b-a4b-it`, `gemma-4-12b-it`. Роли: `{"HIGH_QUALITY": "qwen3.8-27b", "FAST_BALANCED": "qwen3.5-9b", "BALANCED": "qwen3.5-9b", "PRACTICAL_SMALL": "unsloth/qwen3.5-4b", "LOW_RESOURCE": "unsloth/qwen3.5-4b", "F1_ALTERNATIVE": "gemma-4-26b-a4b-it", "MIDDLE_RESOURCE": "gemma-4-12b-it"}`. Файл `shortlist_frozen.json` создан до DEV293, с hashes всех Stage1 manifests/rows и protocol amendments. Pareto: maximize EM/F1, minimize p95/invalid/errors/измеренные peaks. Исходный automated selector сохранён в `automated_shortlist_diagnostic.json`; он включал MiniCPM1B как fastest/lowestresource несмотря на0/59 EM. Практические пять выбраны явно **после DEV60 и до DEV293**: `{"selection_timing": "Explicit choice AFTER DEV60 observed scores and BEFORE DEV293; allfive complete Pareto candidates; preserves original automated selector separately", "qwen3.8-27b": "Highest observed completeDEV60 EM38/59 and F1.7339; slower and near RAM guard, fullDEV feasibility still measured", "qwen3.5-9b": "37/59 EM with p50.313s, practical latency-quality balance", "unsloth/qwen3.5-4b": "19/59 EM, p50.237s, practical small normal instruct model", "gemma-4-26b-a4b-it": "33/59 EM with F1.7303, alternative MoE quality behavior", "gemma-4-12b-it": "25/59 EM, lower GPU/RAM than larger highquality candidates, middle resource alternative", "minicpm5-1b": "Retained complete low-end reference0/59; not worth293 merely for fastest/lowest-resource Pareto extreme", "phi-4-mini-instruct": "4/59 EM vs19/59 Qwen4 at nearly same p50; no useful role within ceiling5", "granite-4.1-8b": "14/59 EM vs19/59 Qwen4 with similar request latency, no useful role within ceiling5", "partials": "Qwen35 FAILED_LOAD0 and GPTOSS partial1 not ranked"}`. Это объявленная разработческая поправка, а не заранее автоматический выбор и не человеческая научная валидация. Partial не добавлялись; zero-EM low-end reference сохранён в Stage1 без полного повторного293.

## Stage2: весь публичный DEV293

| Модель / квант | Статус; попытки / завершено | EM (correct/N) | F1 | invalid / errors | p50 / p95, с | GPU / RAM peak |
|---|---|---:|---:|---:|---:|---:|
| `gemma-4-12b-it` / {'name': 'Q4_K_S', 'bits_per_weight': 4} | COMPLETE; 293/293 | 132/289 = 45.67% | 0.635 | 0/0 | 0.499 / 0.611 | 8522.000 MiB / 17.532 GiB |
| `gemma-4-26b-a4b-it` / {'name': 'IQ4_NL_XL', 'bits_per_weight': 4} | COMPLETE; 293/293 | 147/289 = 50.87% | 0.667 | 0/0 | 0.807 / 0.948 | 13917.000 MiB / 25.012 GiB |
| `qwen3.5-9b` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 293/293 | 141/289 = 48.79% | 0.629 | 0/0 | 0.295 / 0.402 | 11151.000 MiB / 19.957 GiB |
| `qwen3.8-27b` / {'name': 'Q4_K_M', 'bits_per_weight': 4} | COMPLETE; 293/293 | 150/289 = 51.90% | 0.647 | 0/0 | 1.374 / 1.753 | 13963.000 MiB / 28.992 GiB |
| `unsloth/qwen3.5-4b` / {'name': 'Q8_0', 'bits_per_weight': 8} | COMPLETE; 293/293 | 97/289 = 33.56% | 0.564 | 1/0 | 0.225 / 0.273 | 6853.000 MiB / 15.177 GiB |

Предварительный primary local: **`qwen3.8-27b`**. Лучший latency/quality: **`qwen3.5-9b`**. Практический небольшой вариант shortlist: `unsloth/qwen3.5-4b`; absolute low-resource reference — MiniCPM1B с0/59EM, Phi также меньше по RAM/VRAM, но4/59EM. Пригодность нельзя выводить только из памяти/скорости. Числа выше не доказывают перенос на private TEST. **DEV293 включает исходный DEV60 выбора shortlist**, поэтому независимого holdout и confirmatory validation нет.

| Модель | EM, описательный Wilson95% |
|---|---|
| `gemma-4-12b-it` | 40.03–51.44% |
| `gemma-4-26b-a4b-it` | 45.13–56.58% |
| `qwen3.5-9b` | 43.08–54.53% |
| `qwen3.8-27b` | 46.16–57.60% |
| `unsloth/qwen3.5-4b` | 28.37–39.19% |

Wilson95% intervals описывают binomial sampling uncertainty при условных предположениях; они не учитывают post-selection, зависимость/кластеризацию вопросов или переиспользование DEV60. Paired Qwen27(left) vsQwen9(right) на тех же289разбираемых оригинальных references: `{"status": "DEV", "n_expected": 293, "n_scored": 289, "reference_issues": 4, "both_correct": 113, "left_only_correct": 37, "right_only_correct": 28, "both_incorrect": 111, "em_difference_left_minus_right": 0.031141868512110725, "independent_holdout": false, "confirmatory_p_value": null}`. P-value и научное подтверждение превосходства не заявляются.

| Исходная дисциплина; N / scored | `gemma-4-12b-it` EM% / F1 | `gemma-4-26b-a4b-it` EM% / F1 | `qwen3.5-9b` EM% / F1 | `qwen3.8-27b` EM% / F1 | `unsloth/qwen3.5-4b` EM% / F1 |
|---|---|---|---|---|---|
| Ботаника; 25 / 25 | 44.00 / 0.736 | 56.00 / 0.850 | 44.00 / 0.683 | 72.00 / 0.851 | 32.00 / 0.669 |
| Кормопроизводство и луговодство; 30 / 30 | 33.33 / 0.559 | 40.00 / 0.537 | 30.00 / 0.542 | 36.67 / 0.533 | 20.00 / 0.500 |
| Мелиоративное земледелие; 30 / 30 | 63.33 / 0.691 | 56.67 / 0.654 | 56.67 / 0.611 | 66.67 / 0.710 | 30.00 / 0.450 |
| Общая генетика; 29 / 28 | 64.29 / 0.793 | 53.57 / 0.695 | 53.57 / 0.720 | 60.71 / 0.773 | 50.00 / 0.658 |
| Общее земледелие; 30 / 30 | 56.67 / 0.722 | 46.67 / 0.622 | 60.00 / 0.716 | 70.00 / 0.793 | 40.00 / 0.693 |
| Основы селекции; 29 / 29 | 62.07 / 0.791 | 72.41 / 0.866 | 75.86 / 0.839 | 75.86 / 0.866 | 65.52 / 0.818 |
| Растениеводство; 37 / 35 | 17.14 / 0.400 | 48.57 / 0.628 | 40.00 / 0.464 | 25.71 / 0.386 | 14.29 / 0.345 |
| Семеноводство и семеноведение; 24 / 24 | 54.17 / 0.756 | 50.00 / 0.682 | 58.33 / 0.758 | 50.00 / 0.728 | 41.67 / 0.690 |
| Системы земледелия на различных агроландшафтах; 30 / 30 | 43.33 / 0.634 | 40.00 / 0.619 | 46.67 / 0.724 | 43.33 / 0.644 | 36.67 / 0.644 |
| Технологии возделывания сельскохозяйственных культур; 29 / 28 | 25.00 / 0.350 | 46.43 / 0.560 | 25.00 / 0.282 | 25.00 / 0.268 | 10.71 / 0.244 |

| Модель | Single N/scored, EM/F1 | Multi N/scored, EM/F1 | Unresolved |
|---|---|---|---|
| `gemma-4-12b-it` | 212/212, 46.70% / 0.585 | 77/77, 42.86% / 0.775 | 4 |
| `gemma-4-26b-a4b-it` | 212/212, 51.89% / 0.627 | 77/77, 48.05% / 0.777 | 4 |
| `qwen3.5-9b` | 212/212, 50.47% / 0.573 | 77/77, 44.16% / 0.783 | 4 |
| `qwen3.8-27b` | 212/212, 55.19% / 0.601 | 77/77, 42.86% / 0.772 | 4 |
| `unsloth/qwen3.5-4b` | 212/212, 28.30% / 0.488 | 77/77, 48.05% / 0.773 | 4 |

Full293 per-domain N/EM/F1 и single/multiple/unresolved также находятся в `final_analysis.json` и `stage2_domains.csv`; названия дисциплин взяты буквально из meta.domain, категории не придуманы.

Ресурсы — sampled peak всей GPU и всей системной RAM на обычном хосте, не allocation отдельной модели. Request latency исключает reload/warmup: их отдельные amounts доступны в CSV/JSON. Requested GPU ratio не подтверждает actualoffload layers, если native API их не раскрывает. BackendTPS и TTFT публикуются только при фактическом измерении. Token logprobs, если есть, — lexicalconfidence; AUC по DEV диагностичен, калиброванной вероятности правильности нет. Exploratory threshold grid ниже не заморожен для privateTEST.

## Cascade DEV replay

Статус **SIMULATED**. Неразбираемый набор вариантов/transport/abstain → cloud; presentation-normalized plain Latin list может быть допустим даже без исходного JSON, поэтому это не проверка полной strict JSONschema. Дополнительный порог реальной lexicalconfidence выбирается только на DEV из сетки [None,.5,.7,.8,.9,.95,.98,.99,1], объявленной после наблюдения screenDEV, до offline grid evaluation; это не preregistration до model inference. Цель — минимальная доля cloud при EM не ниже cloud−5 п.п.; ties higherF1/lowerthreshold.5 п.п. — exploratory design choice, требующая подтверждения авторами для TEST; это не доказанное неухудшение и не агрономический норматив. Каждое routing decision использует только local observable signal, не gold. Результат primary: `{"threshold": null, "strict_em_count": 38, "n_scored": 59, "strict_set_em": 0.6440677966101694, "strict_set_f1": 0.7338983050847457, "cloud_calls_if_deployed": 0, "relative_cloud_call_reduction_if_deployed": 1.0, "actual_requests_saved": 0}`. Confidence benefit установлен: `False`; local-only suffices на DEV: `True`. Если выбран thresholdNone и0cloudcalls при локальном EM выше cloud, это тривиальный local-only результат, не установленная польза confidence/cascade.

Replay не вызывает моделей: фактически сэкономленных в этом screen запросов0. Возможное сокращение по сохранённым ответам относится только к общему DEV60; full293 cloud не выполнялся, full293 cascade качество неизвестно. Live cascade latency/cost savings не измерены.

## Следующий этап статьи

Рекомендуется **OPTION B как основной следующий дизайн**: MERA для аграрных знаний; HOME150 и StudyC поддерживают технические части. Нынешнее расширение materially усиливает выбор локальной модели и методику, но DEV нельзя назвать final scientific validation. OPTIONC не обоснован числом публикаций.

**MERA_PRIVATE_TEST_READY=NO; server metric UNKNOWN**. Нужны ответ сопровождающих о production scorer/optionA и правах, приёмка official submissionworkflow, согласованная cloudidentity, утверждение авторами замороженных local/cloud/rule/protocol и отдельное разрешение TEST. Maintainermessage подготовлен отдельно, не отправлен. Антоний: проверить рекомендации и вместе с Денисом утвердить небольшой следующий protocol. Денис: независимо проверить denominator/partial/metrics/счёт обращений и согласовать вопросы к MERA; review40 не требуется заполнять.

Агрегаты/CSV: `results/20261003_local_screen_571682f5`. Новая provenance: `manuscript/CLAIM_PROVENANCE_LOCAL_SCREEN_20261003.json`. Source questions/gold/raw remain ignored `.runtime/mera`; datasetrights USE_WITH_RESTRICTIONS.

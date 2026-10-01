# Обзор первичных источников на 30 сентября 2026

Дата обращения ко всем ссылкам: **30.09.2026**. Поиск: local/cloud LLM routing, weak/strong cascades, quality-cost Pareto, uncertainty calibration, agricultural QA and tool use, 2025–2026. Web/arXiv, материалы конференций, официальные model cards и GitHub. Это тематический обзор с проверкой ближайших конкурентов, не систематический PRISMA-review и не гарантия полного покрытия сентября.

Уточнение по новым требованиям преподавателя: этот файл является рабочими исследовательскими и техническими заметками, **не готовой научной библиографией обзорной статьи**. В manuscript берутся только проверенные научные работы; Wikipedia/GitHub запрещены как научные ссылки. Все GitHub links ниже относятся к software discovery/reuse или техническому происхождению файлов. Model/dataset cards, API docs и prices не входят в минимумы50/15 научных источников. Полная обзорная публикация планируется отдельно в REVIEW_ARTICLE_PLAN_RU.md.

## Маршрутизация и каскады

| Работа | Проверено | Значение для эксперимента |
|---|---|---|
| [FrugalGPT, 2023 preprint / последующая публикация](https://arxiv.org/abs/2305.05176) | Abstract и библиографическая страница | Последовательные обращения и cost-aware selection уже известны. Учитывать стоимость всех ступеней. |
| [RouterBench, 2024](https://arxiv.org/abs/2403.12031) | Abstract | Оценка routing по общей матрице ответов; oracle — диагностическая верхняя граница. |
| [RouteLLM, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html), [код](https://github.com/lm-sys/RouteLLM) | Конференционная страница, README, evaluate.py | Preference-trained binary routers; исходная пара старых моделей не переносит quality guarantee на агрономию. Это сильный prior art, не готовая аграрная калибровка. |
| [RouterEval, 2025](https://arxiv.org/abs/2503.10657) | Abstract | Много моделей и задач; удобен для расширения, но не даёт аграрного ground truth. |
| [LLMRouterBench, 2026](https://arxiv.org/html/2601.07206v1) | HTML, методы и evaluation | Унификация сравнения router-методов. Наш узкий corpus не заменяет широкий benchmark. |
| [Dynamic Model Routing and Cascading: Survey, 2026](https://arxiv.org/abs/2603.04445) | Abstract | Нужно различать pre-generation routing и post-generation cascade; MoE внутри модели — другая задача. |
| [UCCI, май 2026](https://arxiv.org/html/2605.18796v1) | HTML | Неопределённость и калибровка используются для экономичного каскада. Самооценка confidence не является эмпирической вероятностью правильности. |
| [Cluster, Route, Escalate, июнь 2026](https://arxiv.org/html/2606.27457v1) | HTML, sections 3–5, appendix | Clustering, cost budget, отдельная quality-estimation ступень. Прямой конкурент общей архитектурной идеи; кластерный или QE router нельзя объявить нашим первым изобретением. |

Вывод: сама local/cloud маршрутизация давно исследуется. Наиболее защищаемый небольшой вклад здесь — контролируемое разложение эффекта инструментов, русские unit/missingness cases и локальное CPU-исполнение на сельскохозяйственном QA. В первой версии нет learned router, ECE/Brier и conformal guarantee. Добавлять их после независимой разметки train/calibration, а не на основании JSON-поля confidence.

## Аграрные близкие работы — проверка против новизны

| Источник | Доступная проверка | Что нельзя объявлять новым |
|---|---|---|
| [AgXQA, 2024, DOI 10.1016/j.compag.2024.109349](https://doi.org/10.1016/j.compag.2024.109349), [авторский repository](https://github.com/MSU-CECO/agxqa_benchmark_v1) | Фактический annotations JSON и license | Аграрный extractive QA и encoder-baselines уже существуют. |
| [AWM-Bench](https://dsiweb.cse.msu.edu/awm-bench/) | Primary leaderboard, описание отдельных задач | Это семейство benchmarks для water management; агрегированное имя не означает один скачанный corpus. |
| [AgroBench, ICCV 2025](https://huggingface.co/datasets/risashinoda/AgroBench) | Авторская карточка и schema | Multimodal MCQ с images уже существует; текстовый subset без изображений меняет задачу. |
| [AgMMU, 2025](https://huggingface.co/datasets/AgMMU/AgMMU_v1) | Авторская карточка и список файлов | Grower/expert-derived agricultural VLM evaluation уже существует. |
| [AgriAgent, январь 2026](https://arxiv.org/abs/2601.08308) | Abstract | Complexity-aware direct reasoning, planning, capability-aware tools и recovery уже предложены. В abstract release условен acceptance. |
| [AgroTools, май 2026](https://arxiv.org/abs/2605.22366) | Abstract, [данные](https://huggingface.co/datasets/AgroTools/AgroTools) | Executable agricultural tool-use benchmark, process и outcome metrics; самый близкий конкурент идее «аграрного агента с инструментами». |
| [AgriLLM eval 800](https://huggingface.co/datasets/AI71ai/agrillm-qa-eval-800) | Карточка | Свободные QA уже есть; reference answer без точного источника не гарантирует factuality. |

Ни отсутствие совпадающего названия, ни отсутствие одного ключевого слова не доказывает новизну. Полные reproduce runs чужих papers не выполнялись. Нужны backward/forward citations и предметная проверка, прежде чем писать «новый метод».

## Реальные open-weight модели

| Проверенный источник | Кандидат / свойства | Применимость к текущей машине |
|---|---|---|
| [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B), [2B](https://huggingface.co/Qwen/Qwen3.5-2B) | Мультиязычная модель, Apache-2.0; поддержка современных engines. Карточки рекомендуют малые размеры для prototyping/task-specific work. | Text-only GGUF Q4_K_M; 0.8B файл 0,533 GB, 2B — 1,281 GB. Обе модели реально протестированы; SHA-256 сверены с upstream LFS. Изображения/vision projector не используются. |
| [Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B) | Действительное название модели; «Qwen 3.8 27B» из устной беседы не принято как точный ID. | Нижняя оценка только 4-bit weights ≈13,5 GB, плюс runtime/cache. 7,73 GiB RAM недостаточно. |
| [Gemma 4 E2B](https://huggingface.co/google/gemma-4-E2B-it) | Официальное open model семейство Google. E2B не следует автоматически считать полным размером RAM. | Проверять actual weights, architecture и license в карточке; в этой сессии NOT RUN. |
| [Ministral 3 3B](https://docs.mistral.ai/models/ministral-3-3b-25-12) | Компактная text/vision модель, Apache-2.0 | Альтернатива для независимой проверки; приблизительно 1,5 GB только 4-bit weights, реальная RAM выше. NOT RUN. |

Оценки памяти P×bits/8 — нижняя граница weights, не измеренный VRAM requirement. Russian/task quality и latency подтверждаются только собственным прогоном. Hardware: 7,73 GiB RAM, 8 logical CPU; WMI GPU запросы отклонены, поэтому GPU/VRAM UNKNOWN. Выбран CPU llama.cpp b11292, four threads, context 4096, one slot. GGUF-конвертация Unsloth является отдельным versioned artifact; модель и runtime hashes сохранены.

## Облачные модели и цена

Цены USD за 1M uncached input / output tokens, стандартная online обработка, короткий контекст; retrieval 30.09.2026. Они не доказывают наличие доступа в конкретном аккаунте.

| Официальный источник | Model | Input / output | Фактический статус |
|---|---|---|---|
| [OpenAI model comparison](https://developers.openai.com/api/docs/models/compare?model=gpt-6-sol) | gpt-6.1-sol; gpt-6-astra | 2 / 10; 10 / 50 | В обзоре; direct API NOT RUN. |
| [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Claude Sonnet 5 | 2 / 10 | В обзоре; direct API NOT RUN. |
| [Gemini latest model](https://ai.google.dev/gemini-api/docs/latest-model) | gemini-3.8-flash | 0,75 / 3,75 introductory до 31.12.2026 | В обзоре; direct API NOT RUN. |
| [Inception models](https://docs.inceptionlabs.ai/get-started/models) | mercury-2 | 0,25 / 0,75 | Доступ уже настроен; выполнен первый пилот. |
| Тот же источник | mercury-2.5 | 0,04 / 0,15, отображаемая 80% акция; regular 0,20 / 0,75 | /models подтвердил ID; dev36 и test90 выполнены. Срок акции и invoice не подтверждены. |

Модель «cloud» в результатах означает указанный Mercury ID, а не произвольную frontier-модель. Общая гипотеза для OpenAI/Claude/Gemini пока не проверена. Usage из каждого raw ответа сохранён; применена консервативная uncached цена. Локальные вызовы имеют нулевой cloud bill, но CPU/RAM/энергия не бесплатны.

## Дополнение 01.10.2026: GPU-эксперимент и научная база

Это дополнение сохраняет исторические сведения 30.09.2026. Упоминания CPU, 7,73 GiB RAM и статуса старых моделей выше относятся к прошлой машине; актуальный домашний ПК описан отдельно в `HOME_PC_ENVIRONMENT_RU.md`. Исторические результаты и старый test90 не пересчитаны. Новый независимый confirmatory holdout пока не запускался; результаты выбора домашней модели являются development/pilot evidence.

Собрана структурированная база **69 уникальных научных кандидатов**: `results/literature_20261001/papers.json`, CSV и `CANDIDATES_RU.md`. У каждой записи проверены существование первичного источника, точное название и дата библиографической записи; для **26** проверена аннотация либо отдельные методы/ограничения. Подтверждённые proceedings/publisher версии указаны для **9** работ. Остальные консервативно обозначены как препринты с непроверенным статусом последующей публикации. Это не означает, что они нигде не рецензировались. Полные тексты всех 69 работ не прочитаны: пул удовлетворяет цели поиска кандидатов, но ещё не составляет окончательные 50+ источников обзорной статьи. Model cards, software, университетская новость и API-документация в эти 69 не входят.

Работы сгруппированы по routing/cascades, uncertainty/abstention, tools/RAG, agriculture и practical local inference. ArXiv и published version одного исследования учитываются один раз. Дата отсечения — 01.10.2026 по первой библиографической записи; перед цитированием утверждений из latest version нужно проверить дату конкретной версии. Часть 2023 работ старше трёх лет на дату отсечения и оставлена только как обоснованный prior art; основу текущего обзора следует составить из 2024–2026.

### Проверенное ядро для экспериментальной статьи

| Работа / первичный источник | Статус, подтверждённый в этой проверке | Практический вывод |
|---|---|---|
| [FrugalGPT](https://arxiv.org/abs/2305.05176), Chen et al., 2023 | Препринт; последующая публикация здесь не проверена | Общая идея каскада известна; считать стоимость всех его ступеней. |
| [RouteLLM](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html), Ong et al., 2025 | ICLR 2025 | Preference routing требует проверки переноса в агрономию и русский язык. |
| [Hybrid LLM](https://arxiv.org/abs/2404.14618), Ding et al., 2024 | Проверен препринт | Гибрид small/large model не доказывает преимущество конкретной домашней конфигурации. |
| [A Unified Approach to Routing and Cascading for LLMs](https://proceedings.mlr.press/v267/dekoninck25a.html), Dekoninck et al., 2025 | ICML 2025, PMLR 267 | Routing до генерации и cascade после ответа различаются; качество estimator критично. |
| [RouterBench](https://arxiv.org/abs/2403.12031), Hu et al., 2024 | Проверен препринт | Сравнивать стратегии на одной paired матрице ответов и показывать диагностический oracle. |
| [Large Language Model Routing with Benchmark Datasets](https://arxiv.org/abs/2309.15789), Shnitzer et al., 2023 | Проверен препринт | Нужна domain transfer проверка, а не выбор по общей таблице benchmarks. |
| [AutoMix](https://arxiv.org/abs/2310.12963), Aggarwal et al., 2023 | Проверен препринт | Self-verification шумна и сама добавляет latency/cost. |
| [GraphRouter](https://openreview.net/forum?id=eU39PDsZtT), Feng et al., 2025 | ICLR 2025 | Смена моделей меняет query/model отношения; прежняя калибровка не автоматически сохраняется. |
| [Universal Model Routing](https://openreview.net/forum?id=ka82fvJ5f1), Jitkrittum et al., 2026 | ICLR 2026 | Отдельная задача — перенос router на ранее не наблюдавшиеся модели. |
| [MixLLM](https://aclanthology.org/2025.naacl-long.545/), Wang et al., 2025 | NAACL 2025 | Рассматривать quality, стоимость и latency одновременно. |
| [Can LLMs Express Their Uncertainty?](https://arxiv.org/abs/2306.13063), Xiong et al., 2023 | Проверен препринт | Verbal confidence часто завышен; JSON confidence не является вероятностью корректности. |
| [Rank-Calibration](https://arxiv.org/abs/2404.03163), Huang et al., 2024 | Проверен препринт | Разделять discrimination/ranking и probability calibration. |
| [Know Your Limits](https://arxiv.org/abs/2407.18418), Wen et al., 2024 | Препринт с отметкой TACL; publisher версия ещё не сверена | Abstention требует измерять answerability и ошибочные отказы. |
| [Semantic Entropy Probes](https://arxiv.org/abs/2406.15927), Kossen et al., 2024 | Проверен препринт | Метод требует hidden states; обычный LM Studio JSON не реализует его. |
| [UCCI](https://arxiv.org/abs/2605.18796), Kotte, 2026 | Препринт | Isotonic calibration на отдельной выборке; H100/NER результат не переносится на нашу задачу. |
| [AgXQA](https://www.sciencedirect.com/science/article/pii/S0168169924007403), Kpodo et al., 2024 | Computers and Electronics in Agriculture, DOI 10.1016/j.compag.2024.109349 | Внешнее extractive irrigation QA; нужен предметный контроль gold/span и free-form scoring. |
| [DEW / FLOW](https://www.sciencedirect.com/science/article/pii/S0168169926001286), Kpodo et al., 2026 | Computers and Electronics in Agriculture, DOI 10.1016/j.compag.2026.111533 | DEW: 419 water-management вопросов в 24 доменах — кандидат для снижения synthetic dependence. |
| [AgriAgent](https://arxiv.org/abs/2601.08308), 2026 | Проверен препринт | Contract-driven agricultural tool orchestration — близкий prior art. |
| [AgroTools](https://arxiv.org/abs/2605.22366), 2026 | Проверен препринт | Agricultural executable tools уже benchmarked; различать process и outcome ошибки. |
| [AgriGPT](https://arxiv.org/abs/2508.08632), Yang et al., 2025 | Проверен препринт и части HTML | Domain tuning, Tri-RAG и curated benchmark не доказывают русский перенос. |
| [AgroGPT](https://openaccess.thecvf.com/content/WACV2025/papers/Awais_AgroGPT_Efficient_Agricultural_Vision-Language_Model_with_Expert_Tuning_WACV_2025_paper.pdf), Awais et al., 2025 | WACV 2025 | Visual QA — отдельная задача; не смешивать с text-only агрометеорологией. |
| [PLLaMa](https://arxiv.org/abs/2401.01600), Yang et al., 2024 | Проверен препринт | Возможный малый domain baseline, но лицензия release и RU/tool capabilities требуют проверки. |

Эта таблица даёт больше 15 содержательных научных источников-кандидатов для статьи; окончательная библиография зависит от допустимости препринтов и проверки полных текстов. Из публикаций нельзя вывести наши пороги success margin или гарантировать гипотезу до нового paired holdout.

### Что следует измерять после выбора домашней модели

Главное сравнение остаётся `tools+cloud` против `tools+local+cloud`: именно оно выделяет добавочную пользу локальной ступени. Отдельно нужны `cloud-only` и `local-only`. Для численных задач correctness должен определять детерминированный инструмент с проверкой единиц и входов. Принятие локального ответа должно опираться на заранее зафиксированные eligibility/validation правила и dev/calibration данные. Валидный JSON проверяет формат, но не смысл. При `CLOUD_AVAILABLE=false` показывать coverage, correct abstention и wrong answers отдельно. Для latency учитывать local generation, verifier, queue и cloud escalation; высокий decode tok/s сам по себе не означает низкую end-to-end latency.

Обоснованный небольшой вклад — reproducible tools-first ablation, practical GPU/CPU offload на 16 GB и русские missingness/unit/rule задачи. Learned router, conformal guarantees, полноценный Russian agricultural benchmark или новизна самой каскадной идеи в этой работе пока не подтверждены.

### Официальная возможность РГАУ-МСХА в декабре 2026

[Официальная новость от 18.06.2026](https://www.timacad.ru/stati/konkurs-studencheskikh-proektov-po-primeneniiu-iskusstvennogo-intellekta-v-reshenii-problem-selskogo-khoziaistva-2026), [Положение](https://www.timacad.ru/legacy-uploads/files/20260727/1785149423_pologen-k-18.pdf) и [Информационное письмо](https://www.timacad.ru/legacy-uploads/files/20260727/1785149428_info-pismo-18.pdf) проверены 01.10.2026. Даты: заявки до **11.12.2026**, очная конференция **18.12.2026**, статьи до **29.12.2026**. Допуск в положение §1.4: студенты 1–2 курсов **09.03.02 / 09.03.03** программ топ-уровня ИИ. Это бакалаврские направления; **право участия магистрантов не подтверждено**. Требуется индустриальный соруководитель; очный этап доступен отобранным работам. Следующий организационный шаг — уточнить у руководителя/организаторов допуск магистрантов; автоматически подавать заявку нельзя.

По информационному письму сборник планируется бесплатным, с размещением eLIBRARY и рецензированием для включения в РИНЦ; фактическое последующее включение ещё не подтверждено. Формат: **3–5 страниц, не более 10 источников**, русский `.doc/.docx`, основной шрифт Times New Roman 14, интервал 1, поля 2 см; обязательны англоязычные данные об авторах/названии/аннотации/ключевых словах, оригинальность от 70%. Это отличается от задания преподавателя **6–8 страниц / ≥15 источников**; нужны две адаптированные версии, если участие согласуют. Текстовые условия PDF извлечены; screenshot rendering веб-инструмента вернул ошибку, поэтому визуальная проверка страницы не заявляется.

## GitHub и reuse

Снимок API: data/github_snapshot.json. [RouteLLM](https://github.com/lm-sys/RouteLLM): Apache-2.0, 5 561 stars, последнее pushed_at в snapshot — август 2024; доступность в 2026 не означает активную разработку. Из него полезны структура paired evaluation и threshold calibration; тяжёлые routers/старые pretrained пары не импортировались. [llama.cpp](https://github.com/ggml-org/llama.cpp): MIT, активное обновление 30.09.2026; используется официальный CPU runtime. [AgXQA repo](https://github.com/MSU-CECO/agxqa_benchmark_v1): Apache-2.0 repository license, data loader и provenance адаптированы самостоятельно.

Jev/LM Link рассмотрены по предыдущему RGAU исследованию и Jev README: reuse добавил бы внешнюю sidecar-зависимость, но не улучшил бы первое сравнение text-answer качества. Частные логи и старые developer scores не включены. Вымышленный GitHub slug AgriGPT вернул 404, поэтому его license/activity не утверждаются. Список проектов не претендует на полный аудит GitHub.

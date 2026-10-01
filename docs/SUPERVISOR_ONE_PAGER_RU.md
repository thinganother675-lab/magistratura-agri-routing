# Предложение первой исследовательской статьи

**Антоний и Денис**, первый курс магистратуры РГАУ-МСХА имени К.А. Тимирязева. 30.09.2026. Научный руководитель пока не подтверждён.

**Название:** «Маршрутизация моделей и инструментов для аграрных задач».

**Проблема.** При ограниченной связи часть запросов нужно обслуживать на доступном компьютере. Для сравнения нужны конкретные данные и эталоны. Общий выигрыш гибрида может объясняться только численными инструментами, поэтому вклад local reader следует оценивать отдельно.

**Объект:** обработка текстовых сельскохозяйственных запросов. **Предмет:** влияние выбора исполнителя и проверки локального ответа на правильность, задержку, облачные вызовы и стоимость. **Цель:** определить границы полезности домашнего гибридного стенда на открытых данных.

**Гипотеза:** инструменты и локальная модель сокращают облачные вызовы при заранее заданном допуске task-quality. Вклад local LLM должен сохраняться относительно tools+cloud. Допуск пилотный; для подтверждающего исследования нужно предметное согласование.

**Задачи:** определить категории; подготовить grouped benchmark и numerical gold; реализовать baselines/gate/cascade; выполнить paired tests и offline; разложить эффект tools/local/cloud; подготовить статью.

**Данные:** 120 paragraphs AgXQA PartB и 240 controlled RU/EN scenarios, train/dev/test180/90/90. Шесть категорий: extractive QA, расчёты, missing inputs/units, tool selection, заданное risk rule, compound criterion. NASA POWER для Московской области — отдельное demo; crop thresholds не выдумываются.

**Стенд:** Qwen3.5-0.8B/2B Q4_K_M на CPU ноутбука, Mercury2/2.5 API. Local/cloud/rule/cascade/tools+cloud/offline; Python GDD/VPD/FAO-56 ET₀/rain deficit, web UI, raw cache, version hashes. Отдельный PC16GBVRAM пока не использован.

**Метрики:** exact/numeric correctness, QA F1, group bootstrap CI, paired differences, critical wrong-ANSWER proxy, cloud calls, mean/p50/p95 latency, token-based cost, coverage/abstention. Confidence calibration пока нет.

**Уже получено:** test90, Qwen2B/Mercury2.5: local 34.4%, cloud 77.8%, cascade 84.4%, tools+cloud 84.4%. Cloud calls 54/90 против 90/90 и 66/90. Local stage снимает ещё 12 вызовов, но mean reconstructed latency 3.30s против 1.56s cloud. Tests 24 passed; live 13/13. Known cloud cost test $.00435224; один 503 без usage. Offline 37.8% правильных завершений и 54 отказа.

**Вклад:** воспроизводимое разделение эффектов tools/local/cloud на узких задачах. Общая routing идея не объявляется новой. Ограничения: слабая CPU модель, synthetic templates, EN QA, неоднозначность reference granularity, replay latency. Независимого agronomist review нет.

**Для первой статьи:** согласовать предметные границы и QA acceptance, проверить сильную модель на PC, создать новый holdout; затем 6–8 страниц, УДК, аннотация 200–300 знаков и минимум 15 научных ссылок. Возможность РГАУ: 18.12 конференция, 11.12 заявка, 29.12 статья; master eligibility нужно подтвердить.

**Для ВКР:** Антоний — resource/cost-aware routing и calibration; Денис — source-grounded Russian benchmark и экспертная оценка. Общий стенд, разные исследовательские вопросы. Темы и связь с GIS/ML/data coursework согласовать с руководителем.

**Отдельная обзорная публикация:** 15–20 страниц, минимум 50 научных источников; таксономия и систематизация методов. GitHub используется только для ПО, Wikipedia/GitHub не входят в научную библиографию. Учебные форматы и короткий декабрьский сборник — разные требования; планы находятся в REVIEW_ARTICLE_PLAN_RU.md и RESEARCH_ARTICLE_PLAN_RU.md.

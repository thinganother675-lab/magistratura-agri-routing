# Готовность к arXiv — проверка официальных правил 2 октября 2026

**Статус: NOT READY FOR SUBMISSION.** Есть проверяемые эмпирические результаты и английский рабочий draft; человеческий review gold/scorer, новый внешний независимый test, author approval, подтверждение endorsement и выбор необратимой лицензии остаются незавершёнными. Создание аккаунта, поиск/контакт endorser и подача здесь **NOT RUN**. Software tests и готовый PDF сами по себе не подтверждают научную готовность.

## Тип статьи и научный вклад

Рабочая эмпирическая статья: *What Does Local Inference Add After Deterministic Tools? A Reproducible Agricultural Routing Case Study*. Она описывает измеренную абляцию и отрицательный результат quality non-inferiority, а не новый фундаментальный routing algorithm. Потенциальный интерес: отделение вклада tools от local stage, анализ ложного принятия compound ответов, русский/английский paired subset, latency/resource/cost accounting на одной 16-GB домашней GPU и честное offline degradation.

Этот вклад узок и требует человеческой валидации. Добавление сельского хозяйства, LM Studio или Jev к известному cascade не делает метод новым. Переименование review/proposal в empirical paper без собственных содержательных результатов не отвечает scholarly standards. [Официальные moderation правила](https://info.arxiv.org/help/moderation/index.html) требуют самодостаточного научного содержания; [content types](https://info.arxiv.org/help/policies/content-types.html) объясняют ограничения для proposal, class project, abstract-only и неполных работ. Принятие на arXiv не является peer review.

**Особенно важно для отдельного обзора:** с 31 октября 2025 arXiv CS рассматривает review/survey и position papers при наличии принятия в refereed journal/conference и документированного завершённого peer review; неподтверждённые review/position submissions обычно отклоняются. Workshop review обычно не считается достаточным. Потребуются корректные journal reference/DOI и подтверждение acceptance. Исключение для cs.CY impact studies нельзя использовать для обхода типа статьи. [Первичная официальная политика](https://blog.arxiv.org/2025/10/31/attention-authors-updated-practice-for-review-articles-and-position-papers-in-arxiv-cs-category/).

Следствие: нынешний обзор литературы на 15–20 страниц с целью 50 источников можно продолжать как manuscript/journal submission, однако **не обещать прямую непроверенную CS-survey подачу на arXiv**. Наши 17 прочитанных работ — ядро эмпирической статьи, не «50 собранных источников».

## English, AI assistance и ответственность

С **11 февраля 2026** требуется полный English version статьи; если добавляется другой язык, English должен идти первым. Одного английского abstract недостаточно. Faithful machine translation разрешён, качество и смысл проверяют авторы. [Официальное объявление](https://blog.arxiv.org/2025/11/21/upcoming-policy-change-to-non-english-language-paper-submissions/), [текущее help правило](https://info.arxiv.org/help/faq/multilang.html).

AI помощь использовалась существенно: код эксперимента/аудита, организация источников, расчёты, draft/перевод. Её нужно прозрачно раскрыть в manuscript и проверять авторами, включая references, gold, statistical claims и source attribution. AI не автор; ответственность несут люди. Не заявлять, что Antonii/Denis проверили данные, пока review не выполнен. [Moderation](https://info.arxiv.org/help/moderation/index.html), [author metadata](https://info.arxiv.org/help/prep.html).

## Первое размещение и endorsement

С **21 января 2026** institutional email сам по себе не даёт автоматическое первое endorsement. Для автоматического пути необходимы institutional email **и claimed ownership уже принятой статьи в соответствующем endorsement domain**; иначе требуется личное endorsement подходящего established arXiv author. Нельзя обещать, что преподаватель автоматически подходит или что регистрация решает этот вопрос. Статус аккаунтов/previous ownership/endorsement Antonii и Denis **UNKNOWN**. [Обновление](https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/), [правила endorsement](https://info.arxiv.org/help/endorsement.html).

Не запрашивать passwords/tokens в чате. Когда авторы будут готовы, они сами проверят account status и доступный официальный endorsement workflow. Никакие письма или контакты от их имени не отправлены.

## Категория, авторы, metadata

Предварительная primary **cs.CL**: оценка natural language agricultural QA, model routing, uncertainty/structured responses. Возможная cross-list **cs.AI** — только если tool orchestration/decision study действительно центральны. **cs.LG** не выбирать автоматически: обученного нового router и собственного learning algorithm в текущем исследовании нет. Окончательное соответствие [category taxonomy](https://arxiv.org/category_taxonomy) определяют авторы и moderation.

User-provided draft authors: **Antonii Sarychev; Denis Shesternin**. User-provided affiliation: **Russian State Agrarian University – Moscow Timiryazev Agricultural Academy, Moscow, Russia**. AI-related first-year master's program уточнять без выдуманного официального названия. Уточнить латинскую запись имён и официальное English institution name перед отправкой; это подтверждение автора, а не повод молча придумывать другой университет. Anastasia не добавлена в авторы. Email/ORCID/report number/DOI отсутствуют и не генерируются.

Перед подачей оба автора должны одобрить финальный текст и author order. Metadata требует title/authors/abstract; abstract не длиннее **1 920 characters**; author list полная, без et al.; без фальшивого DOI/journal acceptance. English title/abstract/author fields подготовить в ASCII либо разрешённых TeX accents. [Официальный metadata reference](https://info.arxiv.org/help/prep.html).

## Лицензия и будущий журнал

**Лицензия manuscript НЕ выбрана.** После размещения каждая опубликованная версия и её лицензия остаются частью постоянной записи, granted license **необратима**. Новая версия с другой лицензией не отменяет права, уже предоставленные старой. Автоматический выбор CC BY/CC0 без author approval неприемлем; лицензии upstream datasets и article тоже не взаимозаменяемы. [Официальные licenses](https://info.arxiv.org/help/license/index.html).

Нужно до подачи выбрать реальный target journal/conference и проверить его первичную preprint/embargo/license политику, согласие coauthors и права на все excerpts/figures/data. Сейчас журнал **NOT SELECTED**, совместимость **UNKNOWN**. Многие журналы допускают preprint, но это нельзя переносить на неизвестный конкретный журнал. Некоторым funder/journal license constraints может соответствовать CC BY, другим arXiv non-exclusive; здесь решение автора и будущего издателя ещё не принято.

## Новая политика с 1 октября 2026

Проверено свежее официальное объявление: **до двух submissions на submitter за calendar month и до трёх active submissions одновременно**, во всех categories. Rejected submission тоже расходует monthly submission slot; coauthors, не являющиеся submitter, не расходуют свои slots. Удалённая до announcement submission по разъяснению блога не считается. Это не основание делить одну работу на несколько малых papers. [Официальная policy от 1 октября 2026](https://blog.arxiv.org/2026/10/01/updated-rate-limit-policy/). Authors должны проверить её снова непосредственно перед возможной будущей подачей.

## TeX и конкретный checklist

Создан standalone English `.tex` с inline bibliography и inline scientific figure, без необходимых external files, неизвестных plugins и установки terminal TeX. Файл открыт в native Codex editor. Попытка native compilation завершилась `compile-failed`: **`Unable to find standard directories for platform`**. Это блокировка runtime/compiler, а не подтверждение синтаксической ошибки или успешной TeX-сборки. Источник сохранён; TeX compilation **UNVERIFIED**, установка terminal TeX не выполняется. Создан отдельный [8-page ReportLab draft PDF](../manuscript/english_routing_20261002_reportlab_draft.pdf) из того же Markdown; все восемь страниц последней версии визуально проверены; 4 таблицы, 18 references и figure читаемы, включая supplementary observed DEV36. Renderer и native diagnostic явно указаны на первой странице и footer. Это не compiled-from-TeX, human scientific review остаётся false. До upload проверить accepted arXiv compiler/packages/fonts, финальную author-reviewed версию и корректные relative paths. [Submit TeX](https://info.arxiv.org/help/submit_tex.html).

| Пункт | Состояние |
|---|---|
| Собственные измеренные 5-policy historical150 results | VERIFIED, ограничения раскрыты |
| Новый pre-inference routing vs прежний cascade | DEV36×6 COMPLETE, exploratory: Jev30/36 vs rule31/36, total remote56 vs23; не confirmatory доказательство |
| ≥15 scientific references | 17 metadata+PDF проверены, релевантные разделы прочитаны; не все статьи полностью |
| English working manuscript/source | CREATED, author editing required |
| Native TeX compilation | BLOCKED: platform directories unavailable; source preserved |
| ReportLab draft PDF/layout | CREATED, 8 pages; current MD/DEV36; all-page visual check PASS; не TeX compilation |
| Human gold/scorer/compound completeness audit | PENDING, human_review=false |
| Внешняя независимая source-grouped проверка | NOT RUN; официальный AgXQA split сильно пересекается |
| Blinded 40-case pack | CREATED, EXPLORATORY_UNRUN, provisional gold отдельный |
| Author consent/order/affiliation final check | PENDING |
| Account/endorsement | UNKNOWN / NOT RUN |
| Manuscript license / target publisher check | NOT SELECTED / UNKNOWN |
| arXiv submission | NOT RUN |

Следующий практический шаг: Antonii и Denis независимо проверяют 40-case pack и исторические compound errors; после adjudication утверждают более внешний dataset, router/scorer freeze и только затем новый confirmatory run. Parallel task: human revision английского отрицательного case-study manuscript с проверкой references и approval авторов.

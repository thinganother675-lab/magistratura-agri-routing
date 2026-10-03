# Редакторская копия одной RU/EN работы — 04.10.2026

Статус: READY FOR EDITORIAL REVIEW. Это изолированная копия; запуск Claude,
совместная редактура исходного репозитория и внешняя подача не выполнены.
PDF: 8 страниц RU / 7 EN; editable RU DOCX: 8 страниц. Все страницы проверены
визуально AI-агентами. Это не человеческая рецензия и не submission approval.

Задача будущего редактора: улучшать ясность, связность, научный русский и
английский, подписи и вёрстку. Сначала прочитать docs/CURRENT_STUDY_20261004_RU.md,
затем обе рукописи и claim_to_evidence.json. Таблицы и evidence_excerpts.json
авторитетны для чисел; ключи excerpts — точные JSONPointers оригинальных файлов,
оригинальные hashes сохранены. Bibliography: 19 научных источников; FAO-56 —
источник формул. references_19.bib и полный компактный registry приложены.
Ссылки индекса на исторические журналы и Git delivery относятся к исходному
приватному репозиторию. Для автономной редактуры использовать selected excerpts;
полные исторические файлы не нужны и не включены в эту копию.

Разрешённые выводы: описательное сравнение двух практических конфигураций;
отдельное историческое DEV293 качество и собственное native40 качество/ресурсы;
улучшение заданных численных ответов живым исполнением при сохранении ошибок
уточнения Qwen9. 9B — практический фокус, 27B — quality reference. 32 исполнения
не устанавливают agronomic deployment safety. Это один development case study.

Запрещено менять значения, знаменатели, авторов или их порядок; выдумывать
эксперименты/источники; убирать DEV reuse, разные quantization/generation/offload,
больший tool-arm token budget, HTTP-sum latency и наблюдавшиеся отказы;
превращать DEV в TEST, replay в measured saving, AI review в human review,
94% ratio в accuracy/equivalence или optional35 monitoring failure в OOM.
Не добавлять benchmark questions, gold, raw answers, private correspondence,
credentials или полные сторонние model cards. Сравнения cloud/CLI — supplementary
и разнородные; endpoint Claude после прежнего403 не был повторно испытан.

Авторы: Антоний Сарычев / Antoniy Sarychev; Денис Шестернин / Denis Shesternin.
Аффилиация и точные недостающие поля/права — docs/PUBLICATION_METADATA_20261004_RU.md.
Финальное согласие, contributions и manuscript license требуют людей. RU/EN —
версии одной работы; не создавать два overlapping arXiv submissions. Текст и
source archive уже можно редактировать без ответа MERA и optional models.

После редактуры сохранить новую датированную версию, показать полный diff,
проверить цифры по evidence, пересобрать PDF/DOCX и просмотреть каждую страницу.
Самостоятельно не отправлять письма, не подавать статью и не выбирать лицензию.

# Английский manuscript: рабочий пакет 2 октября 2026

- `english_routing_20261002.md` — редактируемый текст и проверенные исторические150 результаты; отдельная supplementary таблица фактического DEV36×6 добавлена после завершения запуска.
- `english_routing_20261002.tex` — standalone LaTeX с inline bibliography и таблицами; external project files не требуются.
- `english_routing_20261002_reportlab_draft.pdf` — **8-page ReportLab rendering** текущего Markdown с историческим frozen150 и отдельной supplementary таблицей фактического DEV36×6. Все восемь страниц визуально проверены после последней сборки: 4 таблицы, 18 scientific references и 1 statistical figure читаемы, обрезаний или наложений нет. PDF собран в разрешённой фазе без timed inference.
- `figures/historical_noninferiority_20261002.{png,svg,pdf}` — научный график из authoritative corrected statistics; exact numeric data и source SHA в отдельном manifest. TeX воспроизводит рисунок inline без зависимости от этих файлов.
- Научный reference ledger: `results/20261002_170443Z_21722066_dataset_literature/verified_references_reading_ledger.json`, 17 primary PDF с selected-section reading; 18-й AgXQA reference проверен по bibliographic metadata/dataset card, publisher full text не прочитан.

**TeX compilation UNVERIFIED.** Native Codex editor открыт, но встроенный compiler вернул `Unable to find standard directories for platform`. Это platform/compiler blockage, не source-validation. Terminal TeX или plugin не установлены. Созданный PDF прямо указывает ReportLab renderer и native error; это не подтверждение компиляции TeX и не arXiv-ready proof. Первое наложение legend на CI label исправлено, figure/page4 перепроверены; scientific gold не проверялся людьми.

**Human review=false**, manuscript license NOT SELECTED, submission NOT RUN. Нужны независимая проверка Antonii/Denis, author approval, rights review, более внешний holdout и корректное disclosure AI assistance. Не придумывать email, ORCID, publisher acceptance или другого соавтора.

Текущий draft описывает отрицательный результат non-inferiority: hybrid133/150 против tools+cloud139/150, 95% paired groupCI [-17,65;+5,83] pp. Он не подтверждает quality preservation, field safety или новый routing algorithm. Первоначальные90/150 data/protocol/raw outputs не изменены.

Отдельный DEV36×6 результат: Jev-first30/36 против rule-first31/36; генеративных cloud calls20 против23, но всех external calls56 против23 из-за36 hosted routing calls. Это наблюдаемый exploratory результат, не новый независимый holdout. Восемь cloud timeouts между arms ограничивают причинную интерпретацию latency. Источник: `results/20261002_180119Z_76283d02_prerouting_dev/analysis_20261002_181438Z_c3905087/summary.json`. SHA источников и visual QA сохранены в `results/20261002_170443Z_21722066_dataset_literature/manuscript_build_status.json` и `delivery_manifest.json`.

Генератор `scripts/render_manuscript_20261002.py` обновляет принадлежащий этому этапу `.tex` из `.md`; не запускать поверх чужих ручных изменений без их переноса в source. Native editor/compiler и дальнейшая визуальная проверка — отдельные steps, source creation их не заменяет.

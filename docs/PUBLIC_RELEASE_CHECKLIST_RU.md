# Публичный программный релиз — подготовка, 03.10.2026

Состояние: **LOCAL CANDIDATE ONLY / publication NOT RUN**. Private repository
не переводится в public. Предлагаемый будущий tag `v0.1.0-research` не создан.
Отдельный публичный репозиторий из разрешённого дерева предпочтительнее смены
видимости private research history: история содержит смешанные корпуса,
raw provider outputs и приватные исследовательские материалы.

## Проверяемый состав

- [x] Apache-2.0 официальная лицензия собственного кода, tests/configs и выбранной software documentation; NOTICE и third-party boundaries.
- [x] CITATION.cff: Antoniy Sarychev, затем Denis Shesternin; ORCID/email/DOI/академические звания не придуманы.
- [x] Explicit allowlist вместо копирования всей private Git history.
- [x] Без `.env`, API keys, account credentials, private Worklog, model weights, vendor environments, private provider logs.
- [x] Без copyrighted full papers, FAO/Extension paragraphs, AgXQA/ERA5/NASA raw corpus и неразрешённых screenshots.
- [x] Отдельные CC0 smoke data и числовая projection historical measurements без source/gold/provider text.
- [x] Создание release manifest с SHA256/provenance и проверка frozen historical artifacts.
- [x] Локальная проверка после final ASK explanation fix: clean editable environment, 190 candidate tests / 1.60 s, smoke 8/8, aggregate replay 750 rows / 65 metrics, `--verify` PASS, две ZIP сборки побайтно идентичны.
- [ ] Перед реальной публикацией повторить проверки на финальном согласованном commit/tree и проверить точный архив SHA.
- [ ] Оба автора просматривают точный архив, порядок авторов/affiliation и дают разрешение публикации.
- [ ] Создать отдельный public repository/release только после явного разрешения; не переносить `.git` private history.
- [ ] Решить отдельную лицензию статьи и права для будущих real datasets/outputs.

Команды и ограничения полного воспроизведения указаны в
`release/public_README.md`. Новый researcher может поставить environment,
запустить тесты и synthetic smoke без API, воспроизвести числовые HOME150
агрегаты из retained measurements, затем самостоятельно получить upstream
данные на законных условиях и отдельно настроить local/cloud endpoint.
Smoke не представлен независимым исследовательским test.

Проверенный локальный кандидат: `.cache/public_release/v0.1.0-research`.
Архив: `.cache/public_release/agro-route-v0.1.0-research.zip`, 122 348 bytes,
47 members (46 payload files + manifest), SHA256
`7346b162e67e47c0c2e93030101ef73e01eb4bcba367cd1dfdb20e854871cb9d`.
QA receipt: `results/20261003_licensing_release/verification.json`.
Первый QA receipt сохранён как `verification_v1.json`; предыдущий candidate
и ZIP сохранены с суффиксом `before-ask`. Final source wheel build повторён
в отдельной copy, без изменения основного candidate tree.
Metadata manifest указывает базовый HEAD и индивидуальные hashes новых working
tree files; кандидат не утверждает, что новые session additions уже входили
в базовый commit. Python wheel build и официальная CFF 1.2.0 schema validation
PASS. Полное live/scientific corpus воспроизведение остаётся PARTIAL по правам
на исходные тексты/outputs и human gold.

## Атрибуция и датировка

| Механизм | Что фиксирует | Чего не доказывает |
|---|---|---|
| Git commit/history | Содержание дерева и заявленные author/committer dates; локальная история работы. | Даты задаются клиентом, сами по себе не независимый timestamp, юридическое право или academic publication. |
| GitHub Release/tag | Конкретную версию программного артефакта и опубликованные release assets. | DOI, scientific peer review и приоритет научного открытия автоматически не возникают. |
| Zenodo software DOI | Устойчивую архивную запись версии, metadata/creators и идентификатор для цитирования. | DOI не peer review и не решение copyright ownership dispute. |
| arXiv identifier/version | Публичный научный preprint с metadata, submission/announcement/version records. | Не peer-reviewed journal acceptance. |
| Journal/conference proceedings | Научную публикацию по правилам venue, с конкретным review/indexing/license. | Нельзя предполагать РИНЦ/eLIBRARY, качество или preprint compatibility без venue evidence. |

[GitHub описывает releases как версии для распространения](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
[Zenodo software metadata поддерживает CITATION.cff](https://help.zenodo.org/docs/github/describe-software/);
при одновременном `.zenodo.json` Zenodo использует его, поэтому сейчас второй
metadata file не создаётся. [Включённая GitHub integration автоматически
архивирует новые releases](https://help.zenodo.org/docs/github/enable-repository/).
Поэтому подключать её до согласованного public tree нельзя.

[Zenodo регистрирует DOI после публикации record](https://help.zenodo.org/docs/deposit/about-records/):
software upload / creators / точная версия / license и README должны совпадать.
Metadata открыты даже при restricted files; restricted deposit не делает
metadata приватными. Архивирование полезно для стабильной цитаты и видимости
обоих авторов, но публикация публичного software DOI здесь **NOT RUN**.
Рекомендуется version-specific DOI для точного экспериментального кода;
новые файлы требуют новой версии record. Нельзя заранее вписать выдуманный DOI.

После разрешения: повторный security/provenance review → новый public repository
из чистого дерева → tag/release `v0.1.0-research` → опциональный software Zenodo
record, с теми же авторами → добавить реальный DOI в следующую metadata version.
Article deposit/license остаётся отдельной human decision.

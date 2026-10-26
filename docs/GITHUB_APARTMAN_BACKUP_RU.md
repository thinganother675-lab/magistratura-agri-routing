# Приватная резервная копия истории: 02.10.2026

**DONE.** Репозиторий [Apartman36/magistratura-agri-routing](https://github.com/Apartman36/magistratura-agri-routing) создан с `private=true` и проверен через аутентифицированный GitHub API. Обычный push сохранённой исследовательской истории завершён; remote `main` на 2026-10-02 17:10:41 UTC:

`add40a8b81a7894915e357fa27623551b23304a1`.

Это начальная резервная копия перед новыми изменениями текущей сессии. Итоговый SHA новых изменений фиксируется отдельно после заключительного commit/push ведущего агента; начальная запись не выдаётся за финальный результат новой архитектуры.

## Авторизация и remotes

GitHub `/user` HTTP200 подтвердил именно `Apartman36`. Использован уже настроенный Git Credential Manager 2.6.1; токен передавался только внутри процесса. `gh` не авторизован и для этой операции не требовался. Значения credentials, их fingerprints и заголовки не сохранены.

| Remote | URL | Назначение |
|---|---|---|
| `origin` | `https://github.com/thinganother675-lab/magistratura-agri-routing.git` | Исходная история, URL сохранён точно |
| `apartman` | `https://github.com/Apartman36/magistratura-agri-routing.git` | Разрешённая пользователем PRIVATE резервная копия |

Upstream `main` намеренно настроен на `apartman/main`. Исходный репозиторий наблюдается PUBLIC; его visibility в этой сессии не менялась. Новый репозиторий перед push был пуст, расходящаяся история отсутствовала. Force push, reset, удаление repositories и изменения глобальных credentials не выполнялись.

## Проверки перед передачей

Скан 2026-10-02 17:05:34 UTC: **PASS**, 549 уникальных reachable blobs, 8 commit messages, 627 текущих tracked/nonignored prospective files, 64 распакованных archive members, **0 найденных credentials**. Exact matching использовало только фактические project-local значения, включая `openrouter_api_key_2`; значения и их hashes в evidence отсутствуют. Паттерны неизвестных opaque credentials и содержимое изображений не гарантируют полную детекцию; новые файлы требуют заключительного скана.

Файлов ≥50 MiB и ≥100 MiB в reachable history — **0**. Крупнейший blob — `raw_decisions.jsonl` reconciled analysis input, 5 514 432 байта. Не обнаружены `.env`, credential filenames, GGUF weights, environments или unrelated private notes в передаваемой истории. Нужные результаты не исключались blanket ignore для `results/`.

После push проверены visibility PRIVATE, remote SHA, 614 remote blobs и равенство Git blob hashes **9 важных артефактов**: benchmark, новый holdout, protocol/recovery annex, оба исходных raw segments, reconciled raw, versioned corrected statistics и итоговая Excel-таблица. Исторический `2a2037df62842b0389dc52c4dfbd38e8a04f3b8b` остаётся ancestor.

Evidence: [security_history_audit.json](../results/20261002_170213Z_daddf688_backup_audit/security_history_audit.json), [создание PRIVATE repo](../results/20261002_170213Z_daddf688_backup_audit/github_create_private.json), [проверка remote](../results/20261002_170213Z_daddf688_backup_audit/remote_verification_20261002_171041Z_69e89934.json).

## Права на данные

Это PRIVATE research backup, а не публичный выпуск смешанного корпуса. Разрешение пользователя на перенос не заменяет права первоначальных источников.

| Материал | Проверенное основание | Статус для публичного выпуска корпуса |
|---|---|---|
| Исторические 240 controlled scenarios в `data/benchmark.jsonl`, версия `agro-route-v0.2` | Только записи `controlled_*`, созданные `scripts/prepare_data.py`, имеют явное поле `license=CC0-1.0 (new controlled scenarios)`; source IDs сохранены | CC0 относится только к этим 240 авторским записям, отдельно от 120 AgXQA. Не распространяется на новый review40, manuscript или смешанный корпус |
| AgXQA Part B | Pinned `8626771b289d48cff113f0c13d0603ac644628c0`, Apache-2.0 LICENSE сохранён рядом с annotations | **HOLD** для embedded Extension paragraphs: repo license не устанавливает права каждого исходного текста |
| FAO QA/formula sources | [Официальные terms](https://www.fao.org/contact-us/terms/en/) допускают attributed private study/research; translation/adaptation rights выделены отдельно | **HOLD** до проверки условий конкретных публикаций и прав адаптации; нельзя объявлять весь корпус CC0 |
| UMN cover-crop source | [Первичная страница](https://blog-crop-news.extension.umn.edu/2022/09/maximize-your-cover-crop-benefits-by.html) указывает CC BY-SA4.0 | Сохранить attribution/license и явно обозначить адаптации; не заменять условия CC0 |
| UMN nitrogen source | Project registry сохраняет источник и short authored paraphrase; отдельное blanket permission не подтверждено | **HOLD** для самостоятельного redistributed release |
| USDA NRCS | Source attribution сохранён; authored paraphrase из government source | Не распространять blanket правовой вывод на все внешние компоненты |
| NASA POWER snapshot | Manifest/provenance сохранены; [официальные data FAQs](https://power.larc.nasa.gov/docs/faqs/data/) подтверждают публичную доступность | Публичная доступность сама по себе не означает универсальную лицензию; citation/source terms сохранять |

Лицензии и атрибуция сохранены, исходные тексты не были удалены из истории для маскировки ограничения. Проверка не является полной правовой экспертизой. Публичный dataset release и arXiv supplementary upload mixed raw corpus требуют отдельного решения о правах; в этой сессии такой выпуск не выполнялся.

## Заключительный push и воспроизводимый workflow

После проверки новых изменений ведущий агент делает обычные commit/push, без изменения frozen record. Existing GCM доступен инструментам из процесса с разрешённым доступом к пользовательскому credential store; в ограниченном sandbox lookup возвращал exit128. Новый login/смена аккаунта не нужны.

```powershell
git remote get-url origin
git remote get-url apartman
git status --short
git push apartman main
git ls-remote apartman refs/heads/main
.venv\Scripts\python.exe results\20261002_170213Z_daddf688_backup_audit\verify_backup.py --sha <ACTUAL_COMMIT_SHA>
```

Перед final commit новый versioned scan можно сохранить без изменения первого аудита:

```powershell
.venv\Scripts\python.exe results\20261002_170213Z_daddf688_backup_audit\scan_history.py --output-name security_history_final_20261002.json
```

Команды не требуют передачи токена в аргументах, `.env` или чат. Если username/visibility/remote SHA не совпадают с разрешёнными, helper останавливается. Порядок переноса на ноутбук: [cross-machine note](CROSS_MACHINE_CONTINUATION_20261002_RU.md).

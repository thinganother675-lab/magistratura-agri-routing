# Аудит лицензий и происхождения — 03.10.2026

**Решение P0: Apache-2.0 для оригинального программного обеспечения.**
Проверен текущий private research repository, базовый HEAD
`a3a33b7cf94fe2ccbca1f344c1e0ae4c27ff4af1`. Наличие чужих данных не
препятствует отдельной лицензии собственного кода; оно препятствует публикации
смешанного корпуса без проверки прав. PUBLICATION / Zenodo / public release
**NOT RUN**. Настоящий аудит не утверждает происхождение чужих текстов от авторов.

Официальный `LICENSE` загружен без изменений с
[Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0.txt):
11 358 bytes, SHA256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
Copyright 2026 Antoniy Sarychev and Denis Shesternin указан в `NOTICE`; пример
copyright в официальном приложении лицензии сохранён без изменения.
Apache-2.0 выбрана по прямому указанию авторов: разрешительная лицензия,
явное патентное разрешение, сохранение уведомлений. MIT fallback не нужен:
конкретного несовместимого унаследованного кода в лицензируемой реализации
не обнаружено. Это вывод проверки repository evidence, а не доказательство
отсутствия любого нераскрытого заимствования вне репозитория.

## Метод и область

Проверены весь tracked inventory, дерево `src`, `tests`, `scripts`, конфигурация,
заголовки copyright/license/SPDX, ссылки и длинные строковые fixture payloads,
места получения данных и сохранённые upstream licenses. Проверены основные
ignored download/runtime areas: `.runtime/bitnet`, `.runtime/jev`,
`.runtime/references`, `.runtime/20261002_170443Z_21722066_dataset_literature`,
`.cache/jev`, `.venv`, локальные model/runtime directories. Это классификация
артефактов, а не повторный аудит каждой строки установленных сторонних библиотек.
Некоторые старые disposable pytest caches недоступны по ACL; они не используются
и целиком исключены из публичного дерева. Секретные значения не выводились,
не хешировались и не записывались в audit metadata.

Подробный перечень tracked files с SHA256, классификацией и rationale:
`docs/licensing_inventory_20261003.json`. Отдельная baseline integrity manifest
`docs/historical_integrity_20261003.json` защищает старые data/results/protocols,
рукописи и шесть frozen core files. Builder проверяет эту baseline до экспорта.
Базовый tracked inventory: **991 files** — 165 PROJECT-OWNED,
6 LICENSE-UNKNOWN, 1 THIRD-PARTY-REDISTRIBUTABLE,
2 THIRD-PARTY-REFERENCE-ONLY, 817 DO-NOT-PUBLISH. Broad archive exclusion
DO-NOT-PUBLISH означает решение не распространять private raw wholesale,
а не утверждение, что каждый числовой факт запрещён правообладателем.
Новые разрешённые session files классифицированы отдельно в individual
`release/allowlist.json` / candidate `RELEASE_MANIFEST.json`. **796 existing
historical files** имеют matching SHA256. Полный environment dependency
metadata inventory охватывает 24 distributions; библиотеки не vendored.

| Основной артефакт | Класс | Основание / решение |
|---|---|---|
| `src/agro_route/*.py`, `static/index.html` | PROJECT-OWNED | Оригинальная проектная реализация; vendored framework, чужих copyright headers и конкретного несовместимого copied code не найдено. Apache-2.0. |
| `tests/*.py` | PROJECT-OWNED | Тестовая логика проекта. Numerical facts/formulas не объявляются авторской прозой; атрибуция FAO-56 сохранена. Тесты, требующие закрытых корпусов/журналов, исключены из candidate. |
| `scripts/*.py`, `*.ps1` — программная логика | PROJECT-OWNED | Собственные orchestration/analysis/recovery/download wrappers; imports/API calls не означают vendoring. Apache-2.0 на оригинальный код. |
| `scripts/build_home_holdout.py: FACTS`, source-derived QA/string payloads | LICENSE-UNKNOWN | Текст по FAO/Extension/USDA, mixed rights. Лицензия собственного генератора не распространяется на source prose. Весь файл и зависимый holdout test исключены из candidate. |
| `.env.example`, `pyproject.toml`, lock/config templates | PROJECT-OWNED | Шаблоны без ключей; Apache-2.0 для оригинальной конфигурации. |
| Выбранные новые software/reproduction/license docs | PROJECT-OWNED | Оригинальные описания программы; whitelist в release manifest. Apache-2.0. |
| Приватные Worklog, машинные пути и account/provider traces | DO-NOT-PUBLISH | Private context; не включать в release, даже если текст написан авторами. |
| `data/raw/agxqa/LICENSE` и upstream code-license text | THIRD-PARTY-REDISTRIBUTABLE | Проверенная официальная Apache declaration сохранена. Сам текст лицензии не делает все underlying paragraphs разрешёнными. |
| `data/raw/agxqa/annotations.json`, AgXQA rows в benchmark/версии | LICENSE-UNKNOWN | Есть repository Apache declaration; embedded Extension rights не очищены. Исключены из public candidate. |
| `data/home_holdout*`, bilingual DEV, source-derived generators | LICENSE-UNKNOWN | Mixed FAO/Extension/USDA provenance; переводы/парафразы сохраняют одну source group и не получают автоматически Apache. |
| Controlled synthetic records старого mixed corpus | PROJECT-OWNED | Existing DATA_LICENSES: CC0-1.0; не извлекались массово в candidate, чтобы не переносить старый test. |
| Новый `data/public_sample/benchmark.jsonl` | PROJECT-OWNED | Авторские формальные smoke примеры, отдельный CC0-1.0; не confirmatory benchmark. |
| NASA POWER raw snapshot | THIRD-PARTY-REFERENCE-ONLY | Сохранён upstream manifest; public redistribution на этой сессии не готовится. Apache не применяется. |
| ERA5/Open-Meteo snapshot | THIRD-PARTY-REDISTRIBUTABLE | CC BY 4.0 data with attribution по текущим официальным условиям; API service terms отдельно. Snapshot не включён в candidate. |
| review40: вопросы, provisional gold, forms | LICENSE-UNKNOWN | Смешанный authored/ERA5 материал, human_review=false; отдельная data-license/review decision. Не candidate. |
| `results/*` raw/pairs/decisions/metadata | DO-NOT-PUBLISH | Могут содержать source text, ответы моделей, account metadata, machine paths. Private preservation не public разрешение. |
| Новый `data/public_sample/home150_measurements.jsonl` | PROJECT-OWNED | Только числовые/булевы измерения, pseudonymous IDs/groups, method/category/language/status. Без input/context/gold/output/error prose; CC0-1.0 separate dedication. |
| `outputs/*` workbooks/charts/screenshots | DO-NOT-PUBLISH | Spreadsheet/screenshots требуют собственного содержательного и privacy review. Не включены wholesale. |
| `manuscript/*` MD/TeX/PDF/figures | PROJECT-OWNED | Рукопись и авторские scientific figures; лицензия **НЕ ВЫБРАНА**, Apache-2.0 исключена. Публичная подача NOT RUN. |
| `.runtime/.../*.pdf`, extracted paper pages | THIRD-PARTY-REFERENCE-ONLY | Чтение/библиография; per-paper rights. Full texts и extracts исключены из release. |
| Kaggle/AgriEval/AgXQA discovery downloads | LICENSE-UNKNOWN | Meta/license отличаются между источниками; не встроены в source-only candidate. |
| BitNet vendor checkout | THIRD-PARTY-REDISTRIBUTABLE | Top-level MIT найден; nested dependencies с собственными лицензиями. Весь checkout не распространяется. |
| Laya vendor checkout | THIRD-PARTY-REDISTRIBUTABLE | Top-level Apache найден; benchmark/SDK terms могут отличаться. Весь checkout не распространяется. |
| LLVM-MinGW/toolchain/llama.cpp binaries | THIRD-PARTY-REFERENCE-ONLY | Смешанные LICENSE/COPYING, отдельные compiled components; не входит в код проекта и release. |
| Model weights/tokenizers/quantizations | THIRD-PARTY-REFERENCE-ONLY | Upstream per-model/revision rights, не Apache собственных авторов; полностью исключены. |
| Отдельный Jev repo | LICENSE-UNKNOWN | Сохранён reference checkout, код в текущий release не копирован; общий автор не достаточен для нового license grant. |
| `.env`, keys/auth/browser state, `.git`, environment/cache | DO-NOT-PUBLISH | Полное исключение allowlist; fingerprint/value не сохраняются. |

FAO-56 title page имеет [all-rights-reserved declaration](https://www.fao.org/4/x0490e/x0490e00.htm).
Новая реализация уравнений и небольшие числовые facts в тестах не копируют
публикационную прозу/таблицы. Это не разрешение публиковать исходную книгу.
`evaluation.py` использует общие EM/F1 идеи, собственный компактный алгоритм;
копии vendored SQuAD evaluator/copyright block не найдено.

## Практический результат

Собственное программное обеспечение лицензировано. Публичный кандидат собирается
только explicit allowlist через `scripts/build_public_release.py`; manifest
содержит индивидуальные hashes/provenance/license/scope. Unclassified additions
не попадут автоматически. Сборка запрещает symlink/path traversal, secrets,
private paths, weights, papers, private logs и изменение historical artifacts.
Manifest/скан не являются гарантией отсутствия любого неизвестного секрета;
финальный просмотр и явное разрешение авторов на публикацию всё ещё нужны.

Независимая оценка научного вывода не воспроизводится из числовой projection:
она воспроизводит **сохранённые агрегаты**, но не перепроверяет gold/ответы.
Для полной проверки потребуется отдельное законное получение upstream data,
human gold adjudication и разрешённый выпуск sanitized outputs. Ограничение
раскрыто в candidate README; private raw остаются сохранены byte-for-byte.

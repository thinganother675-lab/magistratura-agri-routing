# Продолжение на ноутбуке: 02.10.2026

Рабочая резервная копия: [PRIVATE Apartman36/magistratura-agri-routing](https://github.com/Apartman36/magistratura-agri-routing). Первый проверенный remote commit: `add40a8b81a7894915e357fa27623551b23304a1`; актуальный SHA новой сессии сверять с её финальным отчётом и `git ls-remote`. Исходный `origin` сохранён; сведения об audit/push: [Git backup](GITHUB_APARTMAN_BACKUP_RU.md).

## Существующий checkout ноутбука

Сначала прочитать local state. Не копировать домашнюю папку поверх проекта, не выполнять reset/clean, не удалять незакоммиченные результаты.

```powershell
git status --short
git branch --show-current
git remote -v
git log -5 --oneline
```

Если `apartman` ещё отсутствует, добавить отдельный remote; если он уже есть, сначала сверить URL и не менять его автоматически:

```powershell
git remote add apartman https://github.com/Apartman36/magistratura-agri-routing.git
git fetch apartman main
git ls-remote apartman refs/heads/main
git log --left-right --graph --oneline HEAD...apartman/main
git diff --stat HEAD apartman/main
git merge-base --is-ancestor HEAD apartman/main
```

Только при чистом working tree, нужной ветке и успешной ancestor-проверке допустим `git merge --ff-only apartman/main`. Если есть местные изменения либо divergence, оставить их на месте и открыть полученную историю в отдельном review worktree:

```powershell
git worktree add --detach ..\magistratura-home-review apartman/main
```

Путь review должен быть новым; это независимый checkout для сравнения, а не автоматическое слияние. После просмотра выбрать способ интеграции, сохраняя обе истории. Для нового ноутбучного checkout без существующего проекта можно обычным `git clone` создать PRIVATE копию в новой пустой папке.

## Окружение и офлайн-проверка

Домашний Python: 3.12.12; исходный ноутбучный snapshot: 3.12.14. Проект требует Python≥3.12; для продолжения использовать documented 3.12 и `requirements-lock.txt`. Не копировать `.venv` между машинами.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts\check_reproducibility.py
```

Перед новыми изменениями нынешней сессии на домашнем ПК прошли **241 tests**. Это baseline программной проверки, не human/agronomist validation. Windows temporary-directory ACL может требовать уникальный workspace-local `--basetemp .cache\pytest_laptop_<run-id>`; результаты тестов фиксировать фактически, не переносить число PASS с другого компьютера.

Секреты через Git не передаются. Если `.env` уже существует, не перезаписывать его копированием `.env.example`; восстановить только необходимые локальные настройки безопасным способом. На ноутбуке endpoint/LM Studio/model inventory/hardware должны быть измерены заново. HOME latency нельзя приписывать ноутбуку.

## Что продолжать, а что сохранять

- Сентябрьская история, HOME DEV и 150-task experiment сохраняются byte-for-byte. Новый confirmatory запуск после подбора маршрутизатора требует нового versioned external holdout и freeze.
- HOME150 уже наблюдался: пригоден для exploratory replay/error analysis, не является свежим confirmatory test. Архивные raw files содержат 750 уникальных решений; Windows interruption и continuation указаны явно.
- Offline regression/statistics replay не требует облачных ключей. Повторный запрос генератора к тем же заданиям будет новым измерением и должен иметь отдельный protocol/run, а не заменять старые ответы.
- `.gitattributes * -text` сохраняет experimental bytes и hashes. Конвертацию line endings научных artifacts не включать.
- GGUF, native BitNet weights, `.runtime`, локальные Laya dependencies и caches исключены из Git. При необходимости использовать точные model manifests/revisions/checksums новой сессии; не скачивать дубликаты по одному display name.
- Private Obsidian worklog не переносится через repo; ключи, browser profiles и полный LM Studio log с посторонними диалогами не добавлять.
- Review pack сохраняет `human reviewed=false` до действительного просмотра Antonii/Denis. Новый subagent review этот статус не заменяет.

Исходный общий setup остаётся в [CROSS_MACHINE_SETUP_RU.md](CROSS_MACHINE_SETUP_RU.md). Финальные новые команды/router results/model manifests следует брать из coherent session index; эта заметка не запускает платный inference и не предлагает повторять уже завершённые эксперименты.

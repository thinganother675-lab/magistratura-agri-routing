# Перенос проекта на домашний ПК

Git содержит код, тесты, планы статей, исходные аннотации AgXQA с лицензией,
нормализованные версии данных, frozen protocol, все сохранённые результаты,
raw ответы в results/*/pairs.jsonl и рисунки. Старые результаты не пересоздавать.
В .gitattributes отключена конвертация строк: это сохраняет экспериментальные SHA-256.

Проверенное окружение ноутбука: Python 3.12.14; зависимости зафиксированы в requirements-lock.txt.
После клонирования из корня проекта:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts\check_reproducibility.py
```

Последняя команда проверяет данные, протокол, core code и воспроизводит статистику
из сохранённых ответов в новой временной папке. API не вызывается, результаты в results/ не изменяются.

Для запуска прежнего локального endpoint (CPU llama.cpp, не LM Studio):

```powershell
.venv\Scripts\python.exe scripts\prepare_assets.py --size 2B
.\scripts\start_local.ps1 -Size 2B
```

В другом терминале:

```powershell
Copy-Item .env.example .env
# Заполнить CLOUD_API_KEY локально, если требуется облако; значения не публиковать.
.\scripts\load_env.ps1
.venv\Scripts\python.exe -m agro_route.cli serve --port 8090
```

Интерфейс: http://127.0.0.1:8090. CLOUD_AVAILABLE=false сохраняет облако выключенным;
включать его осознанно перед запуском, реальные вызовы платные.
Новый benchmark: `.venv\Scripts\python.exe -m agro_route.cli run --split test`.
Это новый запуск на прежней выборке, не независимый новый эксперимент.
Для другой модели/LM Studio нужен отдельный протокол: не менять frozen test задним числом.

## Что не переносится через Git

- Секреты .env и ключи из окружения: восстановить вручную безопасным способом.
  На ноутбуке отдельного project-local .env нет; .env.example не содержит ключа.
- .venv, .cache, .runtime: локальные зависимости, скачанный llama.cpp,
  PID/логи и повторные копии статистики; пересоздаются командами выше.
- Два GGUF-файла Qwen3.5-0.8B и Qwen3.5-2B исключены из Git.
  Точные байты, закреплённые URL, версии и SHA-256 находятся в
  data/model_assets.json и data/model_assets_2B.json.
  Их можно скачать prepare_assets.py (--size 0.8B / --size 2B) или скопировать
  models/ напрямую на ПК и сверить SHA-256. LFS для весов не используется.
- Неиспользованный discovery checkout data/raw/agrillm исключён.
  Для измеренных экспериментов он не нужен.
- Приватный журнал Obsidian находится вне проекта и не входит в репозиторий.

Исследовательские артефакты не требуют отдельного переноса.
Права на вложенные исходные тексты AgXQA требуют отдельной проверки перед публичным
выпуском корпуса; текущий перенос в приватный репозиторий не является публичным релизом данных.

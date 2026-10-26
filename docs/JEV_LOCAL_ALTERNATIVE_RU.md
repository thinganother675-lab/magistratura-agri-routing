# Локальный открытый аналог слоя решений Jev: Laya multilingual

Проверка первичных источников: 01.10.2026. Дополнительный CPU эксперимент хранится отдельно от основного сравнения генеративных моделей и его final holdout.

## Что проверено у Jev

Официальные первичные источники — [анонс TypeSafe от 15.09.2026](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [введение](https://docs.typesafe.ai/introduction), [Quick start](https://docs.typesafe.ai/introduction/quickstart) и [описание моделей](https://docs.typesafe.ai/models). Jev получает состояние и ограниченные вопросы, возвращает выбор из заданных вариантов (`choice`), оценку по шкале (`score`) или значение да/нет (`noul`). В документации показан размещённый API `POST https://api.typesafe.ai/v1/systemone`; официальный SDK является клиентом этого API.

**Локальные веса Jev в проверенных официальных источниках не опубликованы.** Jev рассматривается как закрытый hosted model. Наличие открытого SDK или совместимого интерфейса у стороннего проекта не означает наличие весов Jev. Это вывод по опубликованным способам доступа, а не подтверждение договорных условий закрытого внедрения.

Производитель прямо описывает [ошибки Jev 1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13): неточную арифметику, буквальное чтение, чувствительность к лишнему контексту и противоречиям. Поэтому bounded output гарантирует форму ответа, а правильность решения проверяется отдельно. Численные агрометеорологические расчёты остаются в обычном коде; decision model только выбирает вычислитель или необходимость уточнения.

## Почему выбран Laya

[Laya source](https://github.com/NandhaKishorM/laya/tree/4aa6761be8173de4ce6d92c31b3e40b6eaf59a7c) и [pinned model card](https://huggingface.co/convaiinnovations/laya-multilingual/blob/e4e9ddf21a7b1903b7acffd8814ad4307bf63a67/README.md) описывают негенеративный encoder и обученную голову решений. За один проход модель оценивает варианты объявленных вопросов. Веса доступны локально; опубликован Apache-2.0 для кода и модели. Это функциональный аналог слоя `choice/score/noul`, а не chat-модель, облачный провайдер или воспроизведение Jev.

| Свойство | Проверенные данные |
|---|---|
| Model ID | `convaiinnovations/laya-multilingual` |
| Model revision | `e4e9ddf21a7b1903b7acffd8814ad4307bf63a67` |
| Source revision / package | `4aa6761be8173de4ce6d92c31b3e40b6eaf59a7c` / `laya==0.3.23` |
| Архитектура | mmBERT-base, 22 encoder layers / hidden 768; обученная decision head с 2 transformer layers |
| Параметры | 321,908,998 по safetensors metadata; encoder примерно 307M |
| Языки | 51 language tags, включая `ru`; утверждение авторов о 100+ языках отдельно от нашей RU проверки |
| Контекст | Поставляемый лимит 1,024 токена на вопрос, head budget 256; card допускает `max_len=8192` |
| Лицензия | Apache-2.0, model card + source LICENSE проверены |
| Устройство данного запуска | CPU; GPU оптимизации/compile выключены |
| Генерация текста / decode tok/s | Не используется / N/A |
| Jev API / платные обращения | Не использовались |

Малый multilingual checkpoint выбран для проверяемой русскоязычной маршрутизации с разумными затратами: selected artifacts 678,212,540 bytes; перед загрузкой было 81,045,471,232 bytes свободного места. FP32 веса требуют минимум 1,287,635,992 bytes RAM без учёта токенизатора, активаций и runtime. Источники и окружение изолированы в `.runtime/jev`; веса исключены из Git.

## Закрепление артефактов и установка

Pinned metadata: [metadata.json](../results/jev_local_20261001/metadata.json). Итоговая проверка загрузки: [download_verification.json](../results/jev_local_20261001/download_verification.json). Для LFS файлов размер и SHA256 сверяются с первичным Hub API перед загрузкой модели:

| Файл | Bytes | SHA256 |
|---|---:|---|
| `model.safetensors` | 643,835,514 | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| `tokenizer/tokenizer.json` | 34,363,188 | `609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f` |

Источник клонирован и установлен из точного commit. Runtime использует Python 3.11.9, CPU-only `torch==2.8.0+cpu`, `transformers==4.57.6`, `huggingface_hub==0.36.2`, `safetensors==0.8.0`, `psutil==7.2.2`. Это окружение отдельно от LM Studio и системных model-serving компонентов.

Основная загрузка выполнена через [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli) (`hf download`, pinned revision, отдельный `HF_HOME`, implicit token отключён). CLI получил конфигурацию и tokenizer, но большой файл повторял read timeout. Для него применён [download_pinned.py](../results/jev_local_20261001/download_pinned.py): обычный HTTPS с проверкой `206`, точного `Content-Range`, размера и окончательного SHA256; `.part` сохраняется для продолжения. Redirect URL используется только в памяти процесса, его signed query не сохраняется. TLS проверка включена, ключи не передаются, inference через Hub не вызывается.

На новой Windows машине установка может быть воспроизведена из корня репозитория:

```powershell
py -3.11 -m venv .runtime\jev\.venv
git clone https://github.com/NandhaKishorM/laya.git .runtime\jev\laya-src
git -C .runtime\jev\laya-src checkout 4aa6761be8173de4ce6d92c31b3e40b6eaf59a7c
.runtime\jev\.venv\Scripts\python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.runtime\jev\.venv\Scripts\python.exe -m pip install .runtime\jev\laya-src transformers==4.57.6 huggingface_hub==0.36.2 safetensors==0.8.0 psutil==7.2.2
$env:HF_HOME = Join-Path (Get-Location) '.cache\jev\hf-home'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:HF_HUB_DISABLE_XET = '1'
.runtime\jev\.venv\Scripts\hf.exe download convaiinnovations/laya-multilingual --revision e4e9ddf21a7b1903b7acffd8814ad4307bf63a67 --local-dir .runtime\jev\models\laya-multilingual --max-workers 2
# При повторяющемся read timeout: остановить только свой downloader,
# затем продолжить transport fallback без второго writer к тем же файлам.
.runtime\jev\.venv\Scripts\python.exe results\jev_local_20261001\download_pinned.py --chunk-mib 4 --workers 8
```

## CPU smoke и повторный запуск

[cpu_smoke.py](../results/jev_local_20261001/cpu_smoke.py) читает только локальные веса, проверяет SHA256, ставит CPU устройство и offline Hub/Transformers. Он выполняет 12 синтетических dev сценариев: шесть вручную составленных EN/RU пар для GDD, VPD, ET0, осадков, недостающих входных данных и концептуального QA. Это проверка работоспособности и типизированного выбора, не независимый final holdout. Вопросы, сырые ответы и probabilities сохраняются рядом с summary. Вероятности не калибруются на этих примерах; `noul >= 0.5` — фиксированный диагностический порог.

Команда из корня репозитория:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.runtime\jev\.venv\Scripts\python.exe results\jev_local_20261001\cpu_smoke.py --threads 4
```

Результат каждого запуска получает новую папку `results/jev_local_20261001/cpu_smoke/<UTC timestamp>_<UUID>/`. Если `--output` указывает на существующую папку, скрипт отказывает в запуске и не перезаписывает прежние ответы. Для произвольного собственного текста:

```powershell
.runtime\jev\.venv\Scripts\python.exe results\jev_local_20261001\cpu_smoke.py --threads 4 --state 'Рассчитайте дефицит давления водяного пара: температура 25 C, относительная влажность 60 процентов.'
```

## Измеренный результат

**Статус: загружено, SHA256 подтверждён, локальный CPU inference выполнен.** Прогон [20261001T191143Z_562a73b3](../results/jev_local_20261001/cpu_smoke/20261001T191143Z_562a73b3/summary.json) содержит [сырые ответы](../results/jev_local_20261001/cpu_smoke/20261001T191143Z_562a73b3/raw.jsonl) и [вопросы](../results/jev_local_20261001/cpu_smoke/20261001T191143Z_562a73b3/questions.json).

| Метрика | Результат |
|---|---:|
| Корректный `choice` route | 9/12 = 75.0% |
| EN / RU route | 5/6 = 83.3% / 4/6 = 66.7% |
| Корректный missing-data `noul` при пороге 0.5 | 6/12 = 50.0% |
| Runtime errors | 0 |
| p50 / p95 latency на запрос | 424.06 / 619.86 ms |
| Mean latency | 452.90 ms |
| Загрузка / отдельный warmup | 5,505.88 / 351.10 ms |
| Peak process RSS | 2,320,134,144 bytes ≈ 2.16 GiB |
| Device / dtype / CPU threads | CPU / float32 / 4 |
| Температуры | `[1.0, 1.0, 1.0]`, без калибровки |
| Усечение state / options | Нет в этих 12 примерах |

Две typed questions (`route` и `missing_data`) вычислялись на каждый вход. Latency включает токенизацию, forward и декодирование структуры; excludes загрузку и предварительный warmup. Peak RSS включает загрузку модели, но не является VRAM метрикой. Процесс завершён и модель не оставлена резидентной.

Ошибки дают существенные ограничения для практического применения. RU запрос ET0 выбран как VPD с `answer_confidence=0.8902`. Оба запроса VPD без относительной влажности тоже выбрали VPD вместо `abstain`, с `answer_confidence=0.8615` (EN) и `0.8459` (RU). Отдельный `noul` указал недостающие данные у обоих, но также дал ложные положительные ответы на части полностью заданных численных случаев. Поэтому ни argmax маршрута, ни произвольный высокий confidence threshold не заменяют детерминированную проверку обязательных входов.

Во время загрузки upstream Laya нормализовал локальный `tokenizer/tokenizer_config.json` для совместимости с Transformers; before/after hashes записаны в summary. Проверенные `model.safetensors` и `tokenizer/tokenizer.json` сохранили pinned hashes. Размеры и SHA малых конфигураций в download report относятся к оригинальным загруженным файлам до этой нормализации.

## Границы выводов

Авторы [model card](https://huggingface.co/convaiinnovations/laya-multilingual/blob/e4e9ddf21a7b1903b7acffd8814ad4307bf63a67/README.md) сообщают, что checkpoint поставляется без fitted temperatures (`[1,1,1]`), переоценивает уверенность, слабо работает zero-shot на части typed-decision workflows, имеет position bias у `score` и может занижать положительный `noul`. Эти авторские benchmark цифры не выдаются за измерения нашего оборудования или сельскохозяйственного корпуса.

Laya пригоден как воспроизводимый дополнительный baseline для router/reranker/abstention. Перед использованием probabilities для автономного отказа нужна отдельная аграрная train/dev calibration и новый нетронутый test. Arithmetic, проверка входов и окончательная логика выполняются кодом; в текущем исследовании нет доказательства эквивалентности Laya и Jev, превосходства над генеративными LLM или улучшения конечного качества ответа.

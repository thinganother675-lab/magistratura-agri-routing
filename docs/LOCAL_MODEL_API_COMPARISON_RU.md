# LM Studio: контролируемая проверка через API на домашнем компьютере

Дата измерений: 1 октября 2026 года. Статус: **development / проверка практической работоспособности**, без final holdout. Старые CLI-измерения и основной научный benchmark сохранены отдельно.

## Что измерено и как читать результаты

Новый `scripts/home_lm_api_benchmark.py` отправляет запросы в современный OpenAI-совместимый `POST /v1/chat/completions`. Для каждого запроса задана строгая JSON Schema с пятью полями (`action`, `answer`, `numeric`, `unit`, `tool`), `temperature=0`, `top_p=1`, `seed=42`, `max_tokens=512`, `stream=true`, `stream_options.include_usage=true`. Schema ограничивает форму ответа; правильность содержания проверяет существующий scorer. Модели получают только публичную часть задания, без эталонного ответа.

Это новый протокол, а не прямое повторение старого CLI-теста: ограничения schema, бюджет токенов, transport и режим reasoning изменяют поведение. Данные DEV12 — начало того же сбалансированного DEV36. Их нельзя считать независимыми повторениями или складывать в один знаменатель. Серии с разными reasoning profiles, partial N и bilingual QA представлены отдельно.

Модель загружается через `lms load` последовательно, с context 4096, parallel 1 и явно заданной долей GPU. Native `GET /api/v1/models` подтверждает instance и фактические context/parallel; полный `loaded_instances[].config` сохранён в manifest. Поле GPU offloaded layers в этом ответе отсутствует, поэтому фактическое число слоёв имеет статус **UNKNOWN**, а requested GPU ratio не выдаётся за измеренное распределение. Eval batch, physical batch, flash attention, KV offload, context checkpoints и остальные возвращённые параметры записаны как наблюдаемые настройки.

Подключение к loopback API аутентифицировано. Resolver читает разрешённые имена ключа из окружения/project `.env`; в публикацию попадает только имя источника. Значение ключа, Authorization header и response headers не сохраняются. Серии пишутся в новые UTC/UUID-каталоги; snapshot исполняемого harness и SHA256 данных/prompt/core позволяют проверить происхождение каждого результата. Автоматических повторов запросов и скрытых inference warmups нет. Load wall time измерен отдельно: это продолжительность вызова загрузки после отсутствия загруженного instance, а не гарантия холодного файлового кэша ОС.

## Reasoning и сопоставимость бюджета

В документированном native `POST /api/v1/chat` есть явный reasoning control и backend stats, но в его опубликованной схеме нет seed/JSON Schema. Документированная JSON Schema находится в OpenAI chat API. Публичный перечень параметров chat API не перечисляет `reasoning_effort`; поэтому профиль `off-or-low` здесь **экспериментальный**. Он отправляет `reasoning_effort=none`, когда native capabilities разрешают `off`, и `low` для GPT-OSS. Открытый mapper Hermes использует такое соответствие, однако это не обещание API-контракта LM Studio. Реальное поведение проверено по reasoning deltas и возвращённому `completion_tokens_details.reasoning_tokens`.

У Gemma26 pilot без явного управления reasoning вернул четыре `finish_reason=length` и остановился на 6 случаях. После experimental `none` новая отдельная серия DEV12 завершилась без ошибок, с нулевыми reasoning tokens. Полный DEV36 с этим профилем также вернул reasoning=0 на всех 36 запросах. У GPT-OSS experimental `low` сохранил рассуждение: 4181 reasoning tokens из 4515 completion tokens на первых 13 случаях. Четыре ответа исчерпали 512 токенов и считаются незавершёнными, даже если частичный текст похож на JSON. Эта серия остановлена по заранее заданному правилу четырёх ошибок. Она показывает ограничение данного бюджета/профиля, а не общую неспособность модели.

Primary sources: [LM Studio structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output), [chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions), [native chat](https://lmstudio.ai/docs/developer/rest/chat), [native model listing](https://lmstudio.ai/docs/developer/rest/list), [API changelog](https://lmstudio.ai/docs/developer/api-changelog), [Hermes experimental reasoning mapper](https://github.com/NousResearch/hermes-agent/blob/main/agent/lmstudio_reasoning.py).

## Время, токены и память

`client_first_delta` — время от начала HTTP-вызова до первой непустой answer/reasoning delta. Оно включает обработку входа, transport и клиентское наблюдение. `client_first_answer_delta` отдельно измеряет начало ответа: для reasoning-модели оно может быть значительно позже. Это **client timing**, не backend TTFT. Нативные backend stats в наших OpenAI streams не возвращены и остаются UNKNOWN; скорости из другой генерации не подставляются.

Приближённый client TPS = возвращённое сервером число completion tokens / интервал между первой и последней непустой delta. Первая межтокенная задержка исключена; SSE chunking влияет на оценку; reasoning входит в числитель, если сервер включает его в completion count. TPS GPT-OSS нельзя читать как скорость полезного финального ответа. Exact token totals взяты из usage того же completion; рядом указывается coverage. Отсутствующие counts не заменяются нулём.

VRAM — использование **всего GPU**, RAM — использование **всей системы**, с семплированием примерно каждые 0,5 s и overhead subprocess. Local GPU inference выполняется последовательно. Параллельно могут работать отдельные CPU-процессы облачных HTTP-экспериментов; компьютер не изолирован, другие приложения входят в измерения. Пиковая sampled VRAM/RAM не является точным объёмом памяти конкретной модели и может пропустить короткий пик.

Перед загрузкой требуются RAM headroom ≥3 GiB и GPU free ≥1024 MiB; во время guarded load и перед inference действуют пороги RAM ≥2 GiB / GPU free ≥512 MiB. При guard stop raw сохраняется, собственный instance выгружается, следующая загрузка в той же серии запрещается до проверки состояния. Qwen35 успел ответить на 13 случаев без transport/JSON ошибок; перед 14-м доступная RAM стала 1,863 GiB при GPU free 2032 MiB. Это **inference-time resource guard после успешной загрузки**. В исходном manifest общий state назван `stopped_after_uncertain_load`; `load_success=true` и `resource_guard_stop` уточняют фактическую фазу. Причина роста RAM отдельно не доказана. Повторная загрузка с той же конфигурацией не выполнялась.

## Первые результаты

Полные сопоставимые DEV36 с experimental profile:

| Модель / requested GPU | Верных | Ошибок | Latency p50, s | Client first delta p50, s | Approx. client TPS | Input / completion tokens | Sampled GPU peak, MiB | Sampled system RAM peak, GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.8 27B / 0,75 | 25/36 (69,4%) | 0 | 3,030 | 0,834 | 14,36 | 16486 / 1109 | 15189 | 27,80 |
| Gemma4 26B A4B / 0,70 | 22/36 (61,1%) | 0 | 1,532 | 0,649 | 42,98 | 17016 / 1307 | 14042 | 26,88 |

Все usage counts покрывают 36/36 запросов; reasoning tokens = 0 с coverage 36/36 у обеих моделей. На DEV36 Qwen27 точнее, Gemma26 быстрее. У обеих остаются содержательные ошибки; строгая JSON Schema не решает агрономические вычисления. Категория numeric: Qwen27 2/6, Gemma26 0/6; tool selection и rule interpretation: 6/6 у обеих. Это основание сохранить явные вычислительные инструменты, а не делегировать арифметику свободной генерации.

Partial/diagnostic серии сохраняются отдельно:

| Серия | Верных / фактический N | Причина окончания | Latency p50, s | Input / completion tokens | Reasoning tokens |
|---|---:|---|---:|---:|---:|
| Gemma26, default reasoning, requested DEV12 | 2/6 | 4 незавершённых `length/512` | 16,248 | 2903 / 2539 | 2452, coverage6/6 |
| Gemma26, experimental none, DEV12 | 9/12 | Полная серия | 1,467 | 5764 / 408 | 0/12 |
| Qwen35, GPU 0,55, requested DEV36 | 7/13 | RAM guard перед случаем 14 | 1,734 | 6124 / 411 | 0/13 |
| GPT-OSS20, experimental low, requested DEV36 | 8/13 | 4 незавершённых `length/512` | 3,157 | 6437 / 4515 | 4181, coverage13/13 |

У GPT-OSS client first delta p50 0,182 s, first answer delta p50 2,748 s с coverage9/13; approximate TPS 109,71 включает reasoning. Qwen35/GPT partial13 нельзя ранжировать по accuracy рядом с полным DEV36 без явного ограничения выборки.

Raw provenance:

- `results/20261001T194301Z_47eaacd5_lm_api/`: diagnostic Gemma default.
- `results/20261001T194606Z_8e662ec9_lm_api/`: Gemma experimental DEV12.
- `results/20261001T194807Z_f5edc9b3_lm_api/`: Qwen27 DEV36 + Qwen35 partial13/guard.
- `results/20261001T195351Z_61a2f68c_lm_api/`: GPT partial13 + Gemma DEV36.

## Остальные установленные text models: DEV12 smoke

Все эти кандидаты получили те же первые 12 DEV-случаев и тот же протокол. DR Venus остановлен после четвёртого незавершённого ответа; остальные завершили 12/12. Exact usage coverage равна фактическому N для всех строк. Нули reasoning здесь подтверждены возвращёнными counts, а не выведены из отсутствия поля. Native capabilities не дали explicit off для Granite, QwenVL, Omni и DR Venus: для них `reasoning_effort` не отправлялся; у DR Venus reasoning фактически наблюдался.

| Модель | Верных / N | Ошибок | Latency p50, s | Client first delta p50, s | Approx. TPS | Input / completion tokens | Reasoning tokens | GPU peak, MiB | System RAM peak, GiB | Load wall, s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5 9B | 5/12 | 0 | 0,930 | 0,120 | 46,18 | 5588 / 425 | 0 | 11478 | 20,29 | 30,19 |
| Gemma4 12B | 8/12 | 0 | 0,990 | 0,299 | 59,94 | 5764 / 481 | 0 | 8660 | 17,53 | 8,27 |
| MiniCPM5 1B | 1/12 | 0 | 0,241 | 0,022 | 251,66 | 5289 / 711 | 0 | 2196 | 11,80 | 2,24 |
| Webworld 8B I1 | 6/12 | 0 | 0,548 | 0,071 | 63,29 | 5493 / 371 | 0 | 7770 | 16,88 | 6,63 |
| Granite4.1 8B | 6/12 | 0 | 0,800 | 0,090 | 74,82 | 5254 / 555 | 0 | 6796 | 16,44 | 5,53 |
| DR Venus4B RL | 1/6 | 4 | 4,859 | 0,075 | 105,69 | 2782 / 2523 | 2450 | 4200 | 14,20 | 3,86 |
| Qwen3 VL8B | 5/12 | 0 | 0,585 | 0,055 | 50,44 | 5445 / 313 | 0 | 11024 | 19,50 | 15,89 |
| Qwen3 8B Speciale-distill | 8/12 | 0 | 0,419 | 0,057 | 68,77 | 5493 / 281 | 0 | 6304 | 15,47 | 12,95 |
| Qwen3 Omni30B A3B | 6/12 | 0 | 1,337 | 0,554 | 42,53 | 5493 / 407 | 0 | 14908 | 29,03 | 33,54 |

Raw и фактические config: `results/20261001T195754Z_57e25698_lm_api/`. Qwen3 Coder Next и Qwen35 Uncensored присутствуют в том же manifest со статусом `NOT_RUN_PRIOR_RESOURCE_GUARD`, без inference и без token totals. Omni завершил серию при requested GPU ratio 0,60; sampled RAM peak 29,03 GiB показывает небольшую RAM headroom. Это ограничивает запас для параллельных приложений и дальнейшего увеличения контекста.

До просмотра сводок остальных моделей зафиксировано правило расширения: additional general model получает один отдельный DEV36, только если DEV12 завершён 12/12, correct ≥9/12, errors=0 и загрузка/inference не нарушили resource guards. См. `dev36_expansion_rule.json` в том же каталоге; на момент записи уже были наблюдены Qwen9 5/12 и DR Venus partial1/6. Ни один кандидат из remaining series не прошёл порог. Поэтому smoke-лидеры Gemma12 и Speciale-distill 8/12 не объявляются победителями над Qwen27/Gemma26, измеренными на полном DEV36.

Большое approximate TPS у MiniCPM сопровождается accuracy 1/12. У DR Venus 2450 из 2523 completion tokens — reasoning. Скорость генерации, качество и начало финального ответа оцениваются вместе. Schema привела многие модели к корректной структуре, но не гарантировала правильную маршрутизацию и численные значения.

## Парная QA-проверка EN/RU у лидеров

Новый каталог `results/20261001T200228Z_379d1493_lm_api/` содержит 6 контекстов × 2 языка, counterbalanced порядок, все 24 ответа двух моделей и фактические native configs. Это дополнительный DEV diagnostic. Английские задания повторяются из DEV36; переводы AI-assisted, независимая человеческая проверка PENDING.

| Модель | EN | RU | Всего | Ошибок | Latency p50, s | Client first delta p50, s | Approx. TPS | Input / completion tokens | GPU peak, MiB | System RAM peak, GiB | Load wall, s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen27 | 4/6 | 5/6 | 9/12 | 0 | 3,016 | 0,753 | 16,27 | 5927 / 413 | 15266 | 27,30 | 25,82 |
| Gemma26 | 4/6 | 5/6 | 9/12 | 0 | 1,707 | 0,619 | 42,36 | 6074 / 490 | 14065 | 24,74 | 21,40 |

Token usage и reasoning counts покрывают 12/12 каждой модели; reasoning=0. Равенство 9/12 на этом малом наборе не доказывает равенство языковой способности. На полном DEV36 Qwen27 имеет более высокую общую точность (25/36 против22/36); на QA-поднаборе полного DEV36 обе модели 4/6. В парном QA Gemma26 отвечает примерно в 1,77 раза быстрее по p50 при тех же наблюдаемых языковых counts.

**Практическое распределение ролей:** Gemma26 — предварительный кандидат на быстрый reader/summarizer после выполнения явных инструментов и для контекстной QA. Qwen27 — более точный general local baseline по текущему полному DEV36, с большей latency и device VRAM. Проверка reader после реально исполненного tool в этом API-эксперименте отдельно не выполнена; такая роль основана на QA-скорости и на необходимости выносить ошибочные численные задачи в инструменты. Окончательный выбор для статьи требует заранее замороженного протокола и нового final holdout; текущая таблица не даёт финального `best model` claim.

Всего выполнено **242 HTTP inference requests** в 6 новых сериях: 13 из15 установленных text candidates имеют реальные API-ответы, две unsafe модели имеют явный NOT_RUN. Exact workload totals: 113332 input tokens, 17259 completion tokens, 130591 total tokens; completion включает 9083 reasoning tokens. Coverage всех четырёх counts 242/242. Diagnostic/partial/repeated DEV-случаи входят в этот workload count, но не образуют одну независимую выборку accuracy. Собственные instances после последней серии отсутствуют и в native listing, и в CLI `ps`; доступная RAM восстановлена до20,77 GiB, GPU free до14909 MiB (снимок завершения, другие приложения продолжают работать).

## Воспроизведение

Из корня проекта, с уже настроенным local API и свободным от чужих instances LM Studio:

```powershell
.\.venv\Scripts\python.exe scripts\home_lm_api_benchmark.py --n 12 --models gemma-4-26b-a4b-it --reasoning-profile off-or-low
.\.venv\Scripts\python.exe scripts\home_lm_api_benchmark.py --n 36 --models qwen3.8-27b gemma-4-26b-a4b-it --reasoning-profile off-or-low
.\.venv\Scripts\python.exe scripts\home_lm_api_benchmark.py --n 12 --models qwen3.8-27b gpt-oss-20b gemma-4-26b-a4b-it --reasoning-profile off-or-low --samples-path data\home_dev_bilingual_20261001.jsonl
```

Каждый запуск создаёт новый каталог; начальное наличие загруженного instance приводит к отказу без его изменения. Bilingual набор — существующие пары EN/RU для 6 QA-контекстов; английские случаи повторяют ранее использованный DEV. Порядок EN/RU counterbalanced. Переводы **AI-assisted by Codex**, а не проверенные человеческие переводы. Независимая проверка переводов человеком **PENDING**, поэтому вывод о языках предварительный. В исходном manifest этой API-серии `translation_note` ошибочно содержит `human-authored`; исходный manifest/snapshot сохранён, а отдельный `translation_provenance_correction.json` фиксирует исправление по `probe` исходного dataset. Будущая версия runner использует верную формулировку.

CLI load logs могут содержать имя домашнего каталога в автоматически напечатанной подсказке команды. Оригинальные `*_load.txt` сохраняются локально, не публикуются и не меняются. Публичные `*_load_public.txt` заменяют только путь домашнего каталога на `[USER_HOME]`; SHA256 оригинала и публичной копии, а также описание преобразования записаны в `results/20261001T200228Z_379d1493_lm_api/load_log_publication.json`. Prediction raw не изменён. Проверка точного значения локального API-ключа по всем 6 новым каталогам дала 0 совпадений; значение не выводилось.

Две модели имеют явный `NOT_RUN_PRIOR_RESOURCE_GUARD`: Qwen3 Coder Next (два прежних guarded load failures) и Qwen35 Uncensored (прежний resource guard). Повтор без обоснованной новой конфигурации не выполняется. Embeddings, TTS и специализированные audio-only модели не считаются кандидатами того же text-generation benchmark.

Mock-only tests проверяют корректный SSE usage, разделение reasoning/answer timing, strict schema и отсутствие gold в payload, остановку на length, сохранение ошибок stream, redaction secret echo, неизвестную token coverage и запрет final holdout в custom data. **10 passed**. Эти тесты не запускают модель и не заменяют live evidence.

# Демонстрация HOME-маршрутизации в существующем MVP

Новый `scripts/serve_home_demo.py` использует существующую HTML-страницу без изменения frontend. На странице показываются запрос, route/reason, latency, оценка cloudcost, число cloudcalls и ответ. Это демонстратор; его запросы не добавляются в frozen benchmark и не служат новыми независимыми наблюдениями.

Launcher читает только разрешённые LOCAL_API_KEY и Mercury aliases из project.env/окружения. Значения не печатаются. Основные HOME policies используют неизменённую decision функцию финального драйвера; simple rule остаётся отдельным историческим baseline. В режиме cloud-off hybrid/cloud/tool_cloud демонстрируют offline degradation. Облако включается только явным CLOUD_AVAILABLE=true перед запуском; consumer подписки не используются.

Для локального reader заранее загрузить один instance с выбранной конфигурацией. **Не выполнять одновременно с исследовательским benchmark.** Launcher сам не скачивает/не загружает модели и не выгружает чужие instances. Если требуемого instance нет либо его quant/context/parallel отличаются, локальная стадия возвращает явную недоступность; cloud-enabled hybrid может эскалировать, offline — ABSTAIN.

До загрузки проверить доступную RAM не менее 3 GiB и свободную GPU memory не менее 1024 MiB; во время загрузки применять существующий `home_pc_benchmark.guarded_load`, который останавливает собственную загрузку при RAM <2 GiB либо GPU free <512 MiB. Эти пороги относятся к свободной памяти всей системы/устройства. Demo launcher проверяет те же пороги 2 GiB /512 MiB перед каждым локальным запросом и блокирует inference при нехватке памяти или недоступном измерении. Пример CLI ниже задаёт параметры модели; для контролируемого smoke загрузка выполняется через guard, а не прямой командой.

PowerShell из корня проекта:

```powershell
& C:\Users\hustlePC\.lmstudio\bin\lms.exe server start --port 1234 --bind 127.0.0.1
& C:\Users\hustlePC\.lmstudio\bin\lms.exe load gemma-4-26b-a4b-it --context-length 4096 --parallel 1 --gpu 0.70 --identifier home-demo-gemma26 --yes
$env:CLOUD_AVAILABLE='false'
.venv\Scripts\python.exe scripts\serve_home_demo.py --port 8090 --model-instance home-demo-gemma26
```

Открыть `http://127.0.0.1:8090`. Исходные NASA/GDD и missing-input кнопки демонстрируют deterministic gate без model/API расходов. Для reader задать вопрос с suppliedcontext. Body.offline выключает cloud на конкретном запросе. Если облако необходимо, осознанно перезапустить приложение с CLOUD_AVAILABLE=true; Mercury requestedtemperature0 фактически clampsto1 согласно сохранённому warning, цена — tokenestimate, invoice неизвестен.

Остановить webserver Ctrl+C. Затем выгрузить только созданный demo-instance:

```powershell
& C:\Users\hustlePC\.lmstudio\bin\lms.exe unload home-demo-gemma26
```

Неизменённые historical models/routing/scorer и protocol hashes сохраняются; основной CPU launcher остаётся доступным. Demo smoke/health/tool validation записываются отдельно после финального эксперимента, без повторения holdout и без оплачиваемых вызовов ради проверки UI.

## Фактическая проверка 02.10.2026

Отдельный smoke: `results/20261002_053324Z_09f41a06_home_demo_smoke/metadata.json`, phase `DEMO_SMOKE_NOT_EXPERIMENT`. Health HTTP200, GDD = 22 и missing-input ASK_FOR_DATA прошли. Для этих двух задач model calls = 0. Ровно один запрос из старого DEV (`agxqa_486`) прошёл через LOCAL_MODEL: HTTP200, 1 local / 0 cloud calls, wall latency 2.035 с, cost estimate 0. Полученный numeric = 13 совпал с gold; текст `about 13` не прошёл неизменённый строгий span scorer против `13`. Поэтому общий smoke state сохранён как `failed`: транспорт и маршрутизация работают, formal QA score — FAIL. Это не ошибка подключения и не повод изменять протокол или повторять holdout.

Пять mocked tests демонстратора PASS. В полном post-run suite: 241 PASS. Model load 8.792 с; sampled total GPU peak 13 596 MiB, system RAM peak 22.905 GiB. После smoke собственный hidden web process остановлен, порт 8090 не слушает, собственный `home-demo-gemma26` выгружен, `lms ps --json` вернул `[]`. Frozen science, старые web.py и HTML hashes остались прежними. Для повторной пользовательской демонстрации приложение следует запустить приведённой выше командой; исследовательские результаты при этом не меняются.

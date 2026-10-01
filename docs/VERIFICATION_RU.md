# Проверка готовности первого этапа

30.09.2026. Исследовательский MVP и foundation статьи готовы; submission и работа на отдельном PC не выполнялись.

- Tests: 24 passed, включая analytic formula limits, диапазоны, единицы, missing inputs, отсутствие gold в публичном запросе, timeout, malformed JSON, offline и verifier limitation.
- Live API: 13/13 checks, отдельный `results/live_20260930T184104Z`. Реальные local/cloud вызовы, расчёты и отказы; invalid root JSON/inputs/empty question → HTTP400.
- Browser: form→API→tools/model→render проверен. GDD22 и NASA9.52; missingET0 ASK; русский запрос → LOCAL_TO_CLOUD, ответ «Пшеница». Console warnings/errors0; docs/assets/mvp_cloud.jpg.
- Paired experiments: три completed manifests, 36+36dev и90test; исходные pairs и normalized сохранены. Final protocol frozen до test.
- Reproducibility: dataset/protocol SHA соответствуют manifest; core model/policy/scoring source hashes неизменны после test. Статистика из cached pairs/normalized воспроизведена без API и совпадает с сохранённым JSON отчётом.
- После начала test изменялись только дополнительные report metrics/visual export и web validation/stages. Model prompt, core score, routing и frozen threshold не менялись. Это раскрыто в `.runtime/reproducibility_report.json`.
- Dependency versions записаны в requirements-lock.txt; Python3.12.14. GGUF и официальный runtime hashes сохранены; модель сверена с LFS источника.
- Git repository создан локально, файлы показаны через intent-to-add diff. Коммит, push и публичная публикация не выполнялись. .env, models, runtime/cache, private worklogs исключены.

Повторить read-only проверку: `.venv\Scripts\python.exe scripts\check_reproducibility.py`. Она создаёт отдельную ignored reproduction folder и новые plots, не перезаписывает completed analysis. `scripts/report_russian.py` обновляет текущие документы по неизменяемому основному report; это документы, не новый эксперимент.

Известные границы: малый controlled holdout, source-document overlap не исключён, strict QA granularity, слабый CPU local, Mercury вместо frontier, replay latency, promotional prices и один503безusage. Нет expert validation, trained/calibrated router, retrieval performance или field evidence. Подробнее RESULTS_RU.md.

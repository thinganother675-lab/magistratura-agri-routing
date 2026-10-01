# Магистратура: HOME PC, 01.10.2026

Продолжен существующий репозиторий `thinganother675-lab/magistratura-agri-routing`, исходный commit `2a2037df62842b0389dc52c4dfbd38e8a04f3b8b`. Старые benchmark, frozen protocol и результаты не изменены; cached статистика воспроизведена точно. Тесты: 24 PASS перед экспериментами, 110 PASS после изменений.

Измерено: Ryzen7 8700F, RTX5060Ti 16311MiB, RAM31.62GiB, LM Studio0.4.25. Рабочий локальный путь — CLI; HTTP endpoint `127.0.0.1:1234` требует локального токена.

Загрузка проверена для15 текстовых моделей;14 дали inference,4 прошли одинаковый DEV36. GPT-OSS20B28/36, Qwen27B25/36, Gemma26B21/36, Qwen35B19/36. В малом парном QA Gemma26/Qwen27: EN4/6, RU5/6; Gemma быстрее. Это DEV с непроверенными человеком переводами, не новый независимый test. Предварительный contextual reader — Gemma26, окончательная модель ещё не выбрана.

Сохранены339 исследовательских local requests; известно135133 input/39087 output tokens для286 запросов. Excel с итоговыми моделями и всеми сериями: `outputs/home_pc_20261001/home_pc_models_20261001.xlsx`. Отдельный HF shortlist содержит9 кандидатов: первым проверить Qwen3.5-4B Q8 и Phi4-mini Q8; BitNet1.58 — отдельный CPU baseline.

Новых cloud calls0, новый API расход$0. Offline DEV cached replay Gemma16/36; проекция calls24→18 не является live облачным результатом. Новый holdout n0, final NOT RUN, protocol NOT FROZEN. Старый Mercury использовал проектный credential; владелец ключа и invoice неизвестны, Jev в старых runs не использован.

Следующий этап: controlled local HTTP DEV и небольшой Mercury pilot, ручная проверка gold/переводов, независимый holdout150 и окончательный freeze до единственного final run. Материала старого CPU study достаточно для узкой первой статьи; сильная HOME-PC гипотеза пока не подтверждена.

Открытый typed baseline Laya multilingual скачан локально и SHA256 verified. CPU smoke12: routes9/12, EN5/6,RU4/6; p50/p95 .424/.620s, RSS2.16GiB. Missing-data6/12 — модель не заменяет deterministic gate. Это отдельный encoder эксперимент, не Jev API и не QA ответчик.

Это несекретная итоговая заметка для отдельного Obsidian worklog. SHA итогового commit и push status добавляются в локальную копию после коммита.

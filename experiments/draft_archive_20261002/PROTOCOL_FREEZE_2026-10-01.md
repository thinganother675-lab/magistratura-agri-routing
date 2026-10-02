# HOME-PC development status — 1 October 2026

**STATUS: NOT FROZEN. FINAL HOLDOUT: NOT RUN. Selected IDs: NOT ASSIGNED; n = 0.**

Этот файл честно фиксирует незавершённый этап. Он не является confirmatory protocol и не заменяет неизменённый `data/protocol_frozen.json` от 30.09.2026.

Выполнены clone/проверка commit 2a2037d, восстановление среды, сверка исторических hashes/statistics, hardware/model inventory, локальные CLI DEV-прогоны, отдельная валидация инструментов и новая статистика. Пользователь разрешил smoke всех 15 текстовых моделей и скачивание открытого аналога Jev для отдельного сравнения.

Окончательная локальная модель не выбрана. GPT-OSS 20B и Qwen3.8 27B — кандидаты; первый показал нестабильность и языковой разрыв на малом paired QA probe. Cloud baseline планируется Mercury 2.5. Prompt — исходный SYSTEM_PROMPT; context 4096, parallel 1; routing draft — context-aware home_policy v2.

Обновление после всех установленных text candidates: Gemma4 26B-A4B — предварительный быстрый bilingual context reader (EN4/6, RU5/6, p501.810 s); общий DEV36 score21/36. Это development selection, не final freeze.

Temperature/output budget/reasoning/schema и пороги должны быть окончательно проверены на controlled DEV. CLI temperature/max_tokens UNKNOWN; requested reasoning off не гарантирует отсутствие reasoning. Новый authenticated HTTP pilot и cloud pilot NOT RUN.

Primary contrast draft: hybrid минус tools+cloud. Planning criteria: quality margin −5 п.п., cloud reduction ≥10 п.п., отсутствие дополнительного critical error, p95 ≤10 s. Эти критерии **не frozen**.

До freeze нужны authenticated LM Studio HTTP access, cloud credential/access, controlled DEV validation и окончательные holdout IDs/hashes. Новый final run не выполнялся. Финальный протокол фиксируется до использования его результатов.

Подробный draft: `docs/FINAL_EXPERIMENT_PROTOCOL_RU.md`. Сырые DEV-результаты: `results/20261001_*_cli/`. Итоговый документ явно отделяет DEV, replay, плановые значения и NOT RUN.

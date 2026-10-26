# Методологические исправления до финального test

Первый пилот: results/20260930T174937Z_6bd7b353, 36 dev-примеров, Qwen3.5-0.8B Q4_K_M и Mercury 2. Он сохранён без перезаписи. Его dataset v0.1 сохраняется в data/versions.

Проверка обнаружила две проблемы:

1. Tool-selection запрос содержал название правильного инструмента. Это проверяло следование формату, а не выбор операции. В v0.2 название удалено из вопроса; дано предметное описание. Исправление сделано до test-прогонов.
2. Tools+cloud и cascade дали одинаковое качество в первом пилоте, причём локальная модель почти не принималась проверкой. Поэтому выигрыш над cloud-only нельзя приписывать локальному LLM: он может полностью объясняться численными инструментами и проверкой входов. Обязательна отдельная абляция tool_cloud; вклад локального маршрута оценивается отдельно.

Модели 2B и Mercury 2.5 проверяются на том же development split; подбор не использует test labels. После пилота v0.2 протокол замораживается в data/protocol_frozen.json. Публикационные noninferiority margins должны быть согласованы с научным руководителем; в этой сессии используются только явно отмеченные exploratory utility criteria.
# Итог последующих проверок

Qwen3.5-2B Q4_K_M и Mercury2.5: dev36 завершён, final test90 выполнен после freeze. До test исправлено ошибочное отнесение отсутствующего output к critical ANSWER; refusal/error остаётся incorrect по quality. Frozen rule threshold400 выбран на dev из400/900/1600. Допуск quality5п.п., reduction target16.7% из половины observed dev reduction, critical margin0; exploratory, не универсальный agronomic standard.

Оба pilots показали нулевой дополнительный вклад local-stage против tools+cloud. Final test показал12 дополнительных снятых cloud calls при совпадающем correctness vector; latency проигрыш сохранился. После test исходные prompts/gold/threshold не менялись. Выявлена reference granularity проблема AgXQA: shortest-span prompt и verbose gold; описана в RESULTS, улучшать только в новой benchmark version.

# Проблемы и ограничения HOME-PC — 01.10.2026

Реестр ведётся отдельно по просьбе Антона. Секретные значения не сохраняются. Последнее обновление: 20:15 UTC.

| Проблема | Проверенное состояние | Что сделано / следующий шаг |
|---|---|---|
| OpenRouter authentication | Каталог HTTP200; key endpoint и первый запрос к бесплатной модели HTTP401. Успешных inference responses 0. | По указанию пользователя OpenRouter пропущен. Paid fallback и retries отсутствуют. В будущем нужен действующий ключ в локальной .env; ключ не присылать в чат. |
| GitHub push | Ранее обычный push получил HTTP403: текущая Git credential относится к Apartman36, repository — thinganother675-lab/magistratura-agri-routing. | Локальные commits сохраняются. Для push нужна запись аккаунту Apartman36 или локальная авторизация аккаунтом с правами. Публичность репозитория предоставляет чтение, но сама по себе не предоставляет запись. После итогового commit доступ будет проверен ещё раз. |
| Qwen35-A3B RAM | API-серия остановлена после 13 ответов: available RAM 1.86 GiB, ниже guard 2 GiB, requested GPU ratio 0.55. | Точные outputs и resource samples сохранены. Instance выгружен. Полный API DEV36 NOT RUN; этот профиль нельзя считать устойчивым для длинных серий. |
| Qwen35 Uncensored / Coder Next | Предыдущие загрузки/запросы нарушили memory guard; повторная API inference не выполнялась. | Статус NOT RUN в таблице. Повтор возможен только с отдельно обоснованной и проверенной конфигурацией памяти. |
| GPT-OSS / DR Venus output budget | В API-профиле max512 у каждой серии по 4 length errors; GPT 4181/4515 и DR Venus 2450/2523 output tokens заняты reasoning. | Partial N и errors включены в результаты. Новые лимиты по holdout не подбираются. Старый CLI score остаётся отдельным измерением с неизвестными ограничениями. |
| Mercury reliability | DEV36: 2 ReadTimeout, 1 answer:null, 1 truncated JSON. 4/36 ошибок; usage известен для 34/36. | Повторы отсутствуют. Unknown usage/cost не приравнивается к нулю. Invoice не получен. json_object не гарантирует нашу строгую schema. |
| Native backend metrics | OpenAI SSE предоставляет usage, но не native backend decode TPS и actual offloaded layers. | В таблицах client first delta / approximate TPS и requested offload названы явно. Backend metrics UNKNOWN. Whole-device VRAM / whole-system RAM не являются private allocation модели. |
| Языковая проверка | Paired QA содержит 6 source groups, переводы AI-assisted. Независимая проверка человеком PENDING. | EN4/6 RU5/6 у Qwen27/Gemma26 — preliminary observation; это не доказательство общей эквивалентности языков. |
| Gold/scoring и репрезентативность | Строгий span EM может отвергать смысловой парафраз. Synthetic numerical/rule cases — контролируемые задачи. | Scoring зафиксирован отдельно; QA token F1 и таблица ручного аудита сопровождают accuracy. Результаты не выдаются за полевую проверку агрономических рекомендаций. |
| Pytest Windows ACL | В обычном sandbox pytest temporary fixture mkdir(mode=0700) может получать WinError5. | Root запускает нужные mocked checks с обычными Windows ACL и уникальной workspace basetemp. 25 checks cloud/report прошли. Это среда исполнения тестов, не provider failure. |
| Новая независимая проверка | На время этого обновления holdout150 и final driver готовятся после прекращения tuning. | Final ещё NOT RUN. При завершении сюда добавляется ссылка на окончательный статус; незавершённость не подменяется результатом. |

Historical test90, raw, benchmark snapshot и frozen core сохранены неизменными; повторная сверка hashes и cached statistics прошла.

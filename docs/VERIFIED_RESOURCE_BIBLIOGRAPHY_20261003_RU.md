# Проверенные дополнительные источники: ресурсы и product baseline

Проверено 3 октября 2026. Это дополнение к исторической библиографии, а не
замена ссылок HOME150. Версии и HTTP/source SHA квитанции записаны в
`results/20261003_resource_session/model_author_metadata.json`,
`results/20261003_backup_benchmark/source_receipts.json` и CLI analysis.
Model cards / документация являются первичными техническими источниками,
но не рецензируемыми исследованиями сравнительной эффективности.

| Источник | Что он подтверждает | Граница |
|---|---|---|
| [Qwen3.5-9B, авторская model card](https://huggingface.co/Qwen/Qwen3.5-9B) | Название, языковой параметрический размер, нативный контекст | Не измерения этой машины; GGUF стороннего конвертера |
| [Qwen3.8-27B, авторская model card](https://huggingface.co/Qwen/Qwen3.8-27B) | Название, языковой размер, контекст | Не гарантия конкретного API/runtime |
| [Google Gemma core](https://ai.google.dev/gemma/docs/core) | Gemma26 MoE, активные параметры | Новая телеметрия Gemma не запускалась |
| [LM Studio native chat](https://lmstudio.ai/docs/developer/rest/chat) | SSE, настройки, серверные токены и TTFT | Finish reason/seed/actual GPU layers не появились в использованном ответе |
| [LM Studio SDK schema](https://github.com/lmstudio-ai/lmstudio-js/blob/main/packages/lms-kv-config/src/schema.ts) | Семантика context checkpoints | Конкретные значения проверены также load echo локального сервера |
| [Claude CLI reference](https://code.claude.com/docs/en/cli-reference), [headless](https://code.claude.com/docs/en/headless), [model config](https://code.claude.com/docs/en/model-config) | Print, выбор модели/effort, инструменты и JSON | Локальная Sonnet попытка остановлена authentication 403 |
| [Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli), [authentication](https://learn.chatgpt.com/docs/auth), [config](https://learn.chatgpt.com/docs/config-file/config-reference) | Noninteractive exec, ChatGPT login, режимы ограничений | Флаги сверены с установленным --help; model cache даёт допустимые усилия |
| [FAO-56, глава 2](https://www.fao.org/4/x0490e/x0490e06.htm), [глава 3](https://www.fao.org/4/x0490e/x0490e07.htm), [пример 18](https://www.fao.org/4/x0490e/x0490e08.htm) | Формулы ET0/VPD и единицы, контрольные примеры | Эталонная ET0 не ETc и не норма полива; исходные FAO числа округлены |
| [BhashaBench paper v1](https://arxiv.org/html/2510.25409v1), [BhashaBench-Krishi авторская card](https://huggingface.co/datasets/bharatgenai/BhashaBench-Krishi) | Экспертная проверка, английская аграрная MCQ часть, декларированная CC BY 4.0 | Dataset gated, файлы/схема не получены, licensing/access state NOT_READY |

Основной исторический список формул GDD и публикаций сохранён в
`docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md` и спецификации Study C.
Экспериментальная rain gap имеет собственное определение; ссылка FAO не
используется как обоснование агрономической нормы для неё.

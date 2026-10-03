# Ограничения и решения до независимого исследования

Дата: 3 октября 2026. Текущая работа Antoniy Sarychev + Denis Shesternin.

1. MERA DEV использован для сравнения и выбора моделей. Разница −3,11 п.п.
   Qwen9−Qwen27 и описательные интервалы не являются non-inferiority proof.
   Строгие set EM/F1 локальные; production scorer остаётся UNKNOWN.
2. Четыре неоднозначных эталона DEV293 и один DEV60 исключены из основного
   знаменателя с сохранением полной coverage. Никакого семантического ремонта.
3. Телеметрия40 — systems characterization тех же DEV, не новый независимый
   тест качества. На одной машине и в один день; ABBA не исключает весь drift.
4. Разные GGUF-квантизации, native/OpenAI-compatible транспорт, GPU placement
   и checkpoint profile не позволяют изолировать эффект количества параметров.
   Qwen27 V1 resource-censored; его отказы сохранены. V2 не стирает этот риск.
5. GPU/RAM whole-device/system; RSS named-process-group. Sampled peaks могут
   пропустить короткий пик. Энергия не оценена; seed, actual GPU layers,
   per-model runtime и finish reason не экспонированы. Две загрузки не дают
   распределение холодного старта. p99 при n=40 имеет слабую опору и подавлена
   в исправленном агрегате, первичная сводка сохранена.
6. Study C — 27 конструированных связанных DEV случаев, task дан заранее.
   Tool declaration и simulated replay отличаются от живого вызова. Инференс
   отключил reasoning; результат не характеризует все возможные режимы.
   Строгие численные допуски сохранены, вторичная rounding диагностика отделена.
7. CLI — CLAUDE_CODE_PRODUCT_BASELINE / CODEX_CLI_PRODUCT_BASELINE. Встроенные
   системные инструкции и harness остаются; токены включают overhead, latency
   включает startup/transport. Text-only ограничения и tools audit помогают
   сравнимости, но не превращают CLI в raw API. Sonnet аутентификация не прошла.
   Разные effort проверяются только на заранее выбранных десяти DEV задачах.
   Подписка оплачена: SUBSCRIPTION_INCLUDED, не «бесплатный inference».
8. Mercury2.5 direct — существующий предварительный scientific cloud reference:
   DEV60, 59 scored, 4 length completions, 31/59 EM. Нет сравнимого полного
   DEV293, независимой проверки или одинаковых режимов всех сервисов.
9. Lexical token probability не калибрована в вероятность корректности.
   Qwen9 AUC≈0,702 описательная; confidence cascade на Mercury DEV60 не дал
   выигрыша над local-only. Learned router не обучается.
10. Единственный backup BhashaBench-Krishi English/test пока NOT_READY: gate
    требует передачи контактов; авторы ещё не приняли terms. Файлы, точный split,
    пересечение и frozen scorer не проверены. Источник экспертный, но экзамены
    могли присутствовать в pretraining; contamination-free не заявляется.
11. MERA_SERVER_SCORER=WAITING_FOR_MAINTAINER по сообщению Антония; новый ответ
    не наблюдался. Private TEST NOT_RUN и не разрешён. Ничего не опубликовано,
    не отправлено на оценку и не куплено через API.
12. Следующий протокол требует заранее согласованных допустимой потери качества,
    ресурсных бюджетов, независимого benchmark/evaluator и совместного согласия
    авторов. Место публикации и любые отправки требуют финального решения Дениса.

Редактору запрещено менять числа, статусы, единицы, знаменатели или снимать
ограничения. Текущие RU/EN manuscript относятся к историческому HOME150;
новые таблицы и claim provenance приложены для отдельной последующей редакции.

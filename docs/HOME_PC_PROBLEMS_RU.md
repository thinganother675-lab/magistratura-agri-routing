# Проблемы и ограничения HOME-PC

Актуальное состояние: 02.10.2026, после финального сбора. Значения секретов не сохраняются. [Финальные результаты](FINAL_EXPERIMENT_RESULTS_RU.md) и исходные журналы сохраняются отдельно.

| Проблема | Проверенное состояние | Решение / ограничение |
|---|---|---|
| OpenRouter | Key check и первый free inference HTTP401; успешных responses 0. | SKIPPED по пользователю. Paid fallback и повторов нет. |
| GitHub push | Remote `thinganother675-lab/magistratura-agri-routing`; ранее push HTTP403 с Git credential Apartman36. gh не авторизован. | Локальные commits сохранены; окончательный normal push проверяется после проверки файлов. Публичный read не предоставляет write. Без прав публикация заблокирована. |
| Qwen 35B-A3B | API partial13/36, available RAM 1.86 GiB ниже guard 2 GiB при requested GPU0.55. | Полный API DEV36 NOT RUN; own instance выгружен. Этот профиль не признан устойчивым для длинного прогона. |
| Две тяжёлые конфигурации | Qwen 35 Uncensored и Coder Next раньше нарушили memory guard. | API inference NOT RUN; запросы не повторяли в небезопасном состоянии. |
| GPT-OSS / DR Venus | По 4 length errors на max512; большая часть output занята reasoning. | Ошибки и partial N включены в DEV. Лимиты не подбирались по final answers. |
| Mercury reliability | DEV36: 4 errors; final270 calls: 12 ReadTimeout, 6 JSONDecodeError, 2 ValueError, 1 IncompleteCompletion. | Ошибки входят в качество/latency. Повторов нет. У 12 final calls неизвестны usage/cost; известная стоимость не считается полной. |
| Mercury temperature | 258/258 полученных final raw responses предупреждают: requested0 → effective1. | Requested protocol не изменён. Server override раскрыт. Case bootstrap не охватывает междузапусковую вариативность модели. |
| Windows file sharing | Manifest replace получил WinError5 после 6 cases; HTTP sample7 не начался. | Оригинальные files/claim сохранены. Отдельный заранее зафиксированный технический adapter выполнил только оставшиеся144; 750 уникальных решений без повторов. Два loads и перерыв раскрыты. |
| CRLF protocol copy | Оригинальная run copy имеет другой byte hash вследствие CRLF. | В derived analysis допускается только доказанная точная CRLF→LF эквивалентность frozen source. Оригинал не редактировали. |
| ASK reporting | Frozen analyzer использовал имя ASK вместо ASK_FOR_DATA для summary coverage. | Отдельный nonfrozen overlay исправил только 5 display fields; scoring, results, criteria и исходная statistics.json не изменены. |
| GPU/timing attribution | Actual offloaded layers и backend TTFT UNKNOWN. | Requested ratio и whole-device VRAM не выдают за private/model layers. Backend DEV decode TPS извлечена из logs242/242; FINAL backend metrics UNKNOWN. |
| Router validity | Literal grounding пропускает неверную ветку compound; у hybrid 12/20 неверных compound decisions. | Гипотеза сохранения качества не подтверждена. По этой выборке router больше не настраивали. Narrow critical-error metric не отражает все последствия rule errors. |
| Sampling / human audit | 110/150 synthetic; QA40 из 5 source documents; AI-assisted gold/translation, human audit PENDING. | Выводы относятся к контролируемой выборке. 30 manual examples подготовлены; field agronomy safety не доказана. |
| Offline abstention | 20 ABSTAIN; в gold нет ABSTAIN. | Correct-abstention UNKNOWN. Coverage ответов/уточнений и отказы показаны раздельно. |
| Pytest ACL | Sandbox fixture mkdir(mode0700) даёт WinError5. | Проверки запускались root с уникальным workspace basetemp и обычными Windows ACL. Это ограничение test execution, не inference. |
| Literature readiness | 69 scientific candidates, shortlist16 для research article. | Полное чтение ≥15 и обзор ≥50 источников ещё предстоит; abstracts не называются fulltext-reviewed. |

Historical test90, benchmark/protocol snapshots, frozen scientific code и старые raw сохранены. SHA-проверки и exact cached statistics reproduction прошли. Потребительские подписки не использовались как API credits.

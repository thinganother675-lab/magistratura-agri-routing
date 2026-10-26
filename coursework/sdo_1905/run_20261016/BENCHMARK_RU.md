# Протокол текущего агентного прогона

Начало: 2026-10-16 10:16:31 +03:00. Завершение: 2026-10-16 10:39:34 +03:00.
Полное время: 23.06 минуты (1383.68 секунды).
Это wall clock текущего этапа выполнения, включая чтение, инструменты, исправления и проверку. Предыдущий сбор курса и подготовительные саммари сюда не входят. Это не скорость чистой генерации модели.

## Согласованные условия

Один учебный кейс К01–К10, все лекции/инструкции/образцы доступны, инструменты разрешены. Вариант B выбрал агент. d=3 выбран пользователем. ПЗ-12 явно агентное. Исправления внутри одного непрерывного прогона разрешены задачей; вмешательства пользователя после старта не требовалось. Подагенты не использовались. Внешняя оценка преподавателя не получена.

Название модели из сообщения пользователя — метка сравнения, а не независимо считанный идентификатор конфигурации. Температура, seed, аппаратные параметры модели и число токенов этим протоколом не измерялись. Контекст этого чата содержит предшествующий подготовительный разбор, поэтому для сопоставимого опыта локальной LLM нужен тот же контекст либо одинаковый новый запуск обеих систем.

## Что измерено

- Готовые работы: 14/14, 15 файлов сдачи.
- Фактические проверки Excel: 12/12 соответствуют ожиданиям; расхождений 0.
- Время внутри 12 тестов, включая запись входов и пересчёт через COM: 1.108 с. Не включает запуск Excel, авторинг книги и подготовку.
- Независимые проверки тех же случаев: 12/12; расхождений 0.
- Изменённых исходных формул: 0. Непреднамеренных изменений входов/исходных листов: 0.
- Исходные вложения курса: 77/77 без изменения SHA256.
- Финальная визуальная проверка: 38 страниц документов и 4 листа рабочей книги.

## Обнаруженные проблемы и исправления

| Код | Категория | Наблюдение | Исправление |
|---|---|---|---|
| E01 | environment | Word/Excel COM denied in sandbox | Authorized host execution; Word/Excel 16.0 worked |
| E02 | environment | Dependency junction denied in sandbox | Authorized creation of local junction to bundled dependencies, no install |
| E03 | environment | Packaged DOCX renderer lacked soffice; temporary-profile cleanup also denied | Native hidden Word export and bundled PDFium rendering used |
| E04 | lookup | Two optional skill reference paths and Office registry probe did not resolve | Read available skill files and probed actual Office COM successfully |
| A01 | authoring | First diagram patch did not match source context | No file changed by failed patch; read exact lines and reapplied |
| C01 | content | First PZ08 draft included only TO-BE diagram | Added separate AS-IS flow diagram |
| C02 | content | First PZ10 map emphasized repeat only | Added confirmation channel, unresolved cases and requirement-domain matrix |
| C03 | content | PZ12 limits paragraph repeated | Removed duplicate; retained one explicit limit statement and actual test protocol |
| C04 | source_inconsistency | Author sample JSON omitted separate unit field required by its contract | Our payload explicitly includes unit=kg; disclosed in PZ08/PZ14 |
| L01 | layout | Sources isolated on near-empty ending pages; some diagrams had excess canvas whitespace | Cropped diagram canvases, reflowed citations and grouped new-condition sections |
| L02 | layout | PZ14 diagram dimensions needed original aspect ratio after canvas crop | Derived PDF image height from PNG dimensions |

Итого зафиксировано 11 записей: 4 проблемы окружения/поиска, 1 неуспешная попытка патча без изменения файла, 3 содержательных недочёта черновика, 1 несогласованность исходного примера и 2 группы проблем вёрстки. Нельзя трактовать это как 11 математических ошибок или как независимую оценку качества LLM. Необнаруженные ошибки этим журналом не исключаются. Блокирующих известных проблем в готовом комплекте нет.

## Проверяемые результаты и пределы

B: 22 ч./мес. высвобождаемого ресурса, 13 200 руб./мес. условного эквивалента, 32 400 руб. первого года после поддержки и разовых затрат. При 40 мин. на отчёт — минус 20 400 руб. Это сценарий К07–К09, без утверждения денежной экономии.

Преподаватель может оценить каждое ПЗ по четырём критериям 3+3+2+2. В комплекте присутствуют таблицы/схемы, основания, диагностика и ответы на новые условия. Самооценка «140 из 140» не выставлялась. ПЗ-14 содержит самопроверку одного агента; независимая человеческая экспертиза не заявляется.


## Отдельный аудит 16 октября

Первичный прогон и его время сохранены без изменения. Интервал записи аудита: 595.5 с от 07:49:22 UTC до 2026-10-16T07:59:17.502768+00:00. Исправления перечислены в README и audit_log.json; повторно пройдено 12 тестов Excel. Одна ошибка применения патча исправлена до сборки; расхождений расчётов нет. В СДО ничего не отправлено.

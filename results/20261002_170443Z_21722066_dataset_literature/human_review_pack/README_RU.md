# Слепая проверка 40 примеров: EXPLORATORY, NOT RUN

human_review=false. Записи не использовать для настройки DEV и не считать независимым финальным holdout.

1. Антон и Денис независимо заполняют blinded_questions.csv: действие ANSWER/ASK/ABSTAIN, ответ, уверенность, замечания. До этого не открывать provisional_gold_separate.csv. TOOL — возможный маршрут, а не action ответа; route eligibility не проверена inference.
2. Затем сопоставить с предварительным машинным gold; записать расхождения и согласованный gold в новую версию, не перезаписывая этот пакет.
3. Проверить единицы, допущения, качество RU/EN, неоднозначность и обоснованность отказа. Экспериментальные пороги не являются рекомендациями конкретной культуре.
4. Для будущего confirmatory набора нужны новые независимые источники/погодные блоки, человеческий gold и protocol freeze до inference.

20 двуязычных сценариев = 40 строк, но общий источник ERA5 один. Это данные реанализа сетки; запрос longitude=37.62 вернул longitude=37.5.
В существующем hard gate есть только GDD/VPD/ET0/rain_deficit. Условные пороги, суммирование ET0/осадков и compound не объявляются реализованными tools; ожидаемый маршрут оставлен для review, кроме GDD с явными typed inputs.
Атрибуция данных: Open-Meteo, ECMWF/Copernicus ERA5, CC BY 4.0. Условия API: https://open-meteo.com/en/terms ; методика: https://open-meteo.com/en/docs/historical-weather-api .

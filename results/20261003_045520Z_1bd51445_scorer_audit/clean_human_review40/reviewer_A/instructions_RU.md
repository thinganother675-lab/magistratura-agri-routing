# Независимая слепая проверка задач и опорных данных

Рецензент A: Antoniy Sarychev. human_review=false до реального возврата заполненной формы.

Это 40 НЕЗАПУЩЕННЫХ задач (20 RU/EN пар), а не ответы моделей. Judgment оценивает корректность и проверяемость постановки по источнику; CORRECT не означает измеренную точность модели. Для CORRECT самостоятельно заполните expected_action (ANSWER / ASK_FOR_DATA / ABSTAIN) и reference_answer, при численном ответе также numeric и unit. Сначала работайте независимо от второго рецензента и не открывайте старый provisional gold.

Judgment для каждой строки: CORRECT; INCORRECT; AMBIGUOUS; INSUFFICIENT_REFERENCE; TRANSLATION_PROBLEM; DOMAIN_EXPERT_NEEDED. Последний используйте для агрономического факта вне вашей компетенции; не изображайте экспертизу агронома. Note необязателен. Не меняйте review_id, reviewer, language, question, reference_file. Все 40 judgments обязательны; проблемный gold не нужно угадывать.

ASK_FOR_DATA означает, что конечный расчёт может стать определённым после конкретных измерений; ABSTAIN — материал не поддерживает запрошенный фактический вывод. Объясните недостающую опору в reference_answer. ANSWER относится к полностью заданной авторской экспериментальной формуле или правилу, а не к агрономической рекомендации.

Сохраните заполненную форму в новом файле, не поверх шаблона. Создайте отдельный attestation JSON: reviewer — ваше полное имя выше; completed_by_human=true; completed_utc — фактическое время ISO 8601 с часовым поясом; form_sha256 — SHA256 заполненного CSV. Передайте оба файла исследователю для нового запуска adjudication. Никаких учётных данных не требуется.

Источник: Open-Meteo archive API, ECMWF/Copernicus ERA5, CC BY 4.0; сеточный реанализ, не измерения на ферме. URL источника: https://archive-api.open-meteo.com/v1/archive?latitude=55.75&longitude=37.62&start_date=2025-05-01&end_date=2025-05-20&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration&timezone=Europe%2FMoscow&models=era5

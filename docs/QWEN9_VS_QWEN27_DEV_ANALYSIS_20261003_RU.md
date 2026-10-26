# Qwen9 и Qwen27: парный анализ существующего DEV293

3 октября 2026. **DEV / HISTORICAL / SIMULATED**. Новых model/API calls нет; private TEST не читался и не выполнялся. Для качества использованы те же 293 задания, 289 исходных разбираемых references и 4 unresolved references. `STRICT_SET_EM/F1` — локальные метрики, не официальный MERA production scorer. DEV293 включает прежний DEV60 и использовался для выбора моделей; независимым holdout он не является.

Гипотеза H1: Qwen9 сохраняет большую часть наблюдаемого качества Qwen27, существенно снижая задержку и спрос на память. Анализ не задаёт порог победителя и не пытается доказать превосходство Qwen9. Сравниваются установленные конфигурации с разными квантами и offload, а не изолированное влияние числа параметров.

| Конфигурация | EM | F1 | mean/p50/p90/p95/p99, с | TTFT p50, с | client tok/s p50 | whole GPU peak, MiB | whole RAM peak, GiB | exact GGUF, GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3.5-9b / Q8_0 | 141/289 = 48.79% | 0.628621 | 0.309/0.295/0.366/0.402/0.452 | 0.153 | 57.968 | 11151 | 19.957 | 8.873 |
| qwen3.8-27b / Q4_K_M | 150/289 = 51.90% | 0.646779 | 1.443/1.374/1.638/1.753/1.994 | 0.803 | 13.772 | 13963 | 28.992 | 15.334 |
| gemma-4-26b-a4b-it / IQ4_NL_XL | 147/289 = 50.87% | 0.667112 | 0.824/0.807/0.910/0.948/1.087 | 0.589 | 97.929 | 13917 | 25.012 | 13.557 |

EM9−EM27 = **-3.114 п.п.**; F1 difference -0.018158. Quality retention EM9/EM27 = **94.00%**, F1 retention 97.19%. Median latency27/9 = **4.662×**, p95 ratio 4.359×. Наблюдаемая разница whole-device peak27−9 = 2812 MiB; whole-system RAM peak27−9 = 9.036 GiB. Это не доказанный per-model allocation.

Парные ответы: обе верны **113**, только Qwen9 **28**, только Qwen27 **37**, обе неверны **111**. Qwen27 имеет на 9 strict-correct больше; расхождения гораздо шире, чем итоговая разница. Domain-stratified paired bootstrap (10 000, seed 20261003): descriptive95% EM difference [-8.304; 2.422] п.п.; F1 [-0.061477; 0.025524]. Интервал отражает чувствительность имеющегося DEV к resampling; не является confirmatory significance, equivalence или noninferiority доказательством.

Qwen9 занимает благоприятную область качества и ресурсов в этих измеренных конфигурациях; Qwen27 сохраняет наибольший EM из трёх. Gemma26 даёт наибольший F1 и промежуточную задержку, поэтому универсального победителя нет. Предпочтение зависит от допустимого времени и памяти; бюджеты должны быть зафиксированы авторами до независимого теста.

## Дисциплины и кратность ответа

| Дисциплина | N | EM9 | EM27 | difference9−27, п.п. | F1 difference |
|---|---:|---:|---:|---:|---:|
| Ботаника | 25 | 11/25 | 18/25 | -28.00 | -0.168000 |
| Кормопроизводство и луговодство | 30 | 9/30 | 11/30 | -6.67 | 0.009048 |
| Мелиоративное земледелие | 30 | 17/30 | 20/30 | -10.00 | -0.098889 |
| Общая генетика | 28 | 15/28 | 17/28 | -7.14 | -0.052381 |
| Общее земледелие | 30 | 18/30 | 21/30 | -10.00 | -0.077778 |
| Основы селекции | 29 | 22/29 | 22/29 | 0.00 | -0.027586 |
| Растениеводство | 35 | 14/35 | 9/35 | 14.29 | 0.078231 |
| Семеноводство и семеноведение | 24 | 14/24 | 12/24 | 8.33 | 0.029960 |
| Системы земледелия на различных агроландшафтах | 30 | 14/30 | 13/30 | 3.33 | 0.079683 |
| Технологии возделывания сельскохозяйственных культур | 28 | 7/28 | 7/28 | 0.00 | 0.014286 |

| Кратность | N | EM9 | EM27 | F1 9/27 |
|---|---:|---:|---:|---:|
| multiple | 77 | 34/77 | 33/77 | 0.782746/0.771676 |
| single | 212 | 107/212 | 117/212 | 0.572642/0.601415 |

Кратность исходного reference используется только для post-hoc анализа; inference/router не получает gold cardinality. Дисциплины доступны как observable metadata, но их accuracies здесь уже DEV fit. Их неоднородность — основание для будущей простой заранее замороженной проверки, а не готовая policy с доказанной пользой.

## Исторические ресурсы, загрузка и ограничения

Доступны 30 load/warmup событий на модель (reload через 10 заданий), peak и headroom before/after. Полный исторический ряд ресурсных samples не сохранён; поэтому request-level memory distributions, process RSS/VRAM и energy остаются UNKNOWN. Whole-GPU/RAM включают обычные приложения, sampling около0.5с плюс subprocess overhead; p99 из293 запросов опирается лишь на несколько tail observations. Новая отдельная TELEMETRY выборка нужна для контролируемой systems характеристики.

TTFT — измеренный client first nonempty streamed delta; backend TTFT не раскрыт. Client tok/s ≈ reported completion tokens/(last−first nonempty delta), включает counted reasoning и пропускает интервал первого токена; ответы короткие, поэтому это не чистая аппаратная generation speed. Prompt processing tok/s UNKNOWN. Load timing включает CLI overhead; первая загрузка не гарантированно cold, следующие reload могут использовать OS cache.

| Конфигурация | loads | first load / median reload, с | warmup median, с | context / concurrency | requested offload | actual layers | invalid/error/load failure |
|---|---:|---:|---:|---:|---|---|---:|
| qwen3.5-9b | 30 | 19.111/6.684 | 0.271 | 2048/1 | max | UNKNOWN | 0/0/0 |
| qwen3.8-27b | 30 | 19.598/9.397 | 1.594 | 2048/1 | 0.75 | UNKNOWN | 0/0/0 |
| gemma-4-26b-a4b-it | 30 | 26.545/10.004 | 1.147 | 2048/1 | 0.70 | UNKNOWN | 0/0/0 |

Все293 benchmark responses трёх моделей имеют finish_reason stop; crashes/load/transport failures в этой завершённой серии0. Это не оценка долговременной надёжности и не отменяет failures других screen-конфигураций. Exact GGUF SHA256+bytes берутся из checksummed file receipt, не native `size_bytes`, который содержит больше байт; официальное число параметров в этом анализе отдельно не проверялось. Quant label означает mixed GGUF types, не одинаковую битность всех tensor elements.

## Qwen9 confidence и saved-output routing

Lexical confidence — geometric mean вероятностей выпущенных Latin option tokens, не P(верный ответ). Поэтому ECE/Brier не вычисляются; график показывает empirical accuracy по confidence bins без утверждения calibration.

| Модель | N scored confidence | AUC | descriptive95% interval | single AUC | multiple AUC |
|---|---:|---:|---:|---:|---:|
| qwen3.5-9b | 289 | 0.702319 | [0.641922; 0.759881] | 0.731464 | 0.664843 |
| qwen3.8-27b | 289 | 0.769880 | [0.712219; 0.822890] | 0.781466 | 0.820248 |

Это exploratory correctness ranking на том же DEV. Уверенный формат не является уверенным знанием. Fixed-grid replay использует сохранённый Qwen9 **Stage1 DEV60** и Mercury2.5 instant512/.5 на тех же prompt hashes; повторный Qwen9 Stage2 subset не подменяет Stage1. Gold используется только offline scoring, не routing. Все thresholds сохранены, новый router не обучался.

| threshold | cloud calls/60 (simulated) | EM correct/59 | F1 | invalid/error |
|---|---:|---:|---:|---:|
| None | 0 | 37/59 | 0.720743 | 0/0 |
| 0.5 | 14 | 33/59 | 0.682324 | 1/1 |
| 0.7 | 28 | 33/59 | 0.674980 | 3/3 |
| 0.8 | 30 | 34/59 | 0.691929 | 3/3 |
| 0.9 | 34 | 35/59 | 0.708878 | 3/3 |
| 0.95 | 40 | 32/59 | 0.669330 | 4/4 |
| 0.98 | 40 | 32/59 | 0.669330 | 4/4 |
| 0.99 | 45 | 31/59 | 0.660856 | 4/4 |
| 1.0 | 60 | 31/59 | 0.657627 | 4/4 |

**Confidence сигнал существует, но польза делегирования текущему Mercury не установлена**: local-only37/59; ни один ненулевой fixed threshold не улучшает этот EM, лучший даёт35/59. Mercury-only31/59 включает4 length failures. Формат-only fallback вызывает0cloud на этих данных. Live cascade latency/cost не измерялись; actual requests saved0. Нет full293 cloud comparator, и нет независимой проверки threshold/domain routing. Не следует обучать learned router или называть replay экономией платных запросов.

## Связь с уже имеющейся статьёй

HOME150 — искусственный технический holdout от тех же авторов, не внешняя агрономическая expertise. Его composite score нельзя сравнивать с MERA strict EM/F1. Прежний OpenRouter — supplementary provider/harness screen с собственной identity/eligibility/неполным coverage; это не равная raw-local конфигурация. Mercury2.5 — direct provisional scientific cloud reference, operational TEST readiness не установлена из-за4/60 length. Новых cloud API calls и затрат этот анализ не делает. Publication plan и authorship требуют совместного human approval; рукописи здесь не переписаны и ничего не опубликовано.

Машиночитаемые результаты: `results/20261003_resource_analysis/analysis.json`, `models.csv`, `domains.csv`, `cardinality.csv`, `confidence_thresholds.csv`, `cascade_dev60.csv`. Рисунки: Pareto tradeoff, latency ECDF, confidence bins. Reproduction: `.venv/Scripts/python.exe scripts/analyze_resource_efficiency_20261003.py`; hashes всех прочитанных данных и кода входят в analysis.json. DEV evidence status сохраняется.

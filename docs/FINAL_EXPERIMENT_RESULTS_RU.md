# Итоги HOME-PC сессии — 01.10.2026

**Статус: DEVELOPMENT ONLY. Новый независимый final holdout — NOT RUN. Протокол — NOT FROZEN.**

## Репозиторий и проверка

Проект клонирован из `https://github.com/thinganother675-lab/magistratura-agri-routing.git` в `C:\Users\hustlePC\Codex\magistratura`. Исходный HEAD — `2a2037df62842b0389dc52c4dfbd38e8a04f3b8b`, branch main, origin соответствует указанному репозиторию. История laptop, benchmark360, старые три runs и test90 сохранены.

Перед новыми измерениями: 24 исходных теста PASS. После изменений: 110 тестов PASS. В новой среде CPython 3.12.12 установлены 24 locked dependencies. Проверка reproducibility подтвердила hashes dataset/protocol/шести core modules и точное воспроизведение старой статистики. Исходные model/policy/scoring/tool modules не изменены. Итоговая верификация новой реализации фиксируется отдельно в `results/audit_20261001/`.

Исторический test90: local31/90, cloud70/90, tools+cloud76/90, cascade76/90. Cloud calls66→54 между последними двумя политиками; mean latency1.136→3.298 s. Это сентябрьские данные, не новый результат HOME PC.

## Окружение

Ryzen 7 8700F, 8 cores /16 threads; RTX 5060 Ti, 16 311 MiB VRAM; RAM31.62 GiB; Windows11 Pro build26300; NVIDIA617.14. NVIDIA-SMI CUDA compatibility13.4 не означает установленный CUDA Toolkit. На первом snapshot свободно77.74 GiB на C.

LM Studio0.4.25+1, localhost1234. HTTP `/v1/models` без локального токена возвращал401; CLI работает. Использовался sequential `lms load/chat/ps/unload`, context4096/parallel1. Temperature/seed/max_tokens CLI UNKNOWN; requested reasoning-off у GPT-OSS не надёжен. Настройки безопасности сервера не изменены. Все собственные identifiers выгружены после прогонов.

## Все модели и одинаковый DEV36

Inventory21: 15 текстовых LLM, 3 embedding, 1 image и2 TTS. Для всех15 текстовых моделей выполнены loading attempts;14 дали inference,13 получили минимум6 DEV queries. Четыре прошли общий DEV36. Выбранные для аналитики raw серии, полные token/resource totals и остальные smoke приведены в `ALL_LOCAL_MODELS_HOME_PC_RU.md`, `LOCAL_MODEL_TOKEN_RESOURCE_TABLE_RU.md` и CSV.

| Модель / quant | Correct /36 | Quality | p50 / p95 s | Decode tok/s | Peak VRAM MiB total | Peak RAM GiB system | Parser/CLI errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-OSS20B Q8_0 | 28 | 77.8% | 3.604 /8.531 | 106.20 | 12478 | 24.05 | 3 |
| Qwen3.8 27B Q4_K_M | 25 | 69.4% | 3.042 /4.450 | 14.15 | 15095 | 27.76 | 0 |
| Gemma4 26B-A4B IQ4_NL_XL | 21 | 58.3% | 1.472 /2.362 | 36.55 | 13937 | 25.74 | 1 |
| Qwen3.5 35B-A3B Q4_K_L | 19 | 52.8% | 1.992 /2.777 | 28.76 | 14187 | 29.79 | 0 |

Qwen9/Gemma12 —4/12 каждый, четыре format failures; MiniCPM0/7, Webworld2/10, Granite2/6 и distilled Qwen5/9 остановлены после четырёх ошибок. Dr Venus6/12,p50 6.283/p95 23.026 s; Qwen-VL4/12; Omni30B5/12. Эти разные N нельзя объединять в один quality ranking с full36.

Uncensored35B дал только1 запрос, затем RAM guard: available1.764 GiB. Coder Next Q3_K_S file31.03 GiB: попытка offload0.40 остановлена при потере GPU telemetry,0.35 — при RAM available1.939 GiB. Его inference **NOT RUN**, качество неизвестно. После обеих попыток проверены cleanup и восстановленный NVIDIA-SMI. Это предел конкретной конфигурации, не доказательство непригодности весов.

VRAM — sampled whole-device use; RAM — whole-system use, не private allocations. Запрошенные GPU fractions: Qwen27 .75, Qwen35 .55, Gemma26 .70, Omni .60. Actual offloaded layer count UNKNOWN. Tok/s GPT-OSS включает reasoning. Cold load записан отдельно, latency ответа включает CLI process/IPC.

## Выбор reader и русский язык

Лучший aggregate score общего DEV36 — GPT-OSS. Для практического **bilingual context reader после deterministic tools** предварительно предпочтительна Gemma26; окончательная модель **NOT SELECTED** до controlled API DEV.

| Модель | Paired QA EN /6 | RU /6 | Всего /12 | p50 s | Errors |
|---|---:|---:|---:|---:|---:|
| GPT-OSS20B | 4 | 2 | 6 | 2.168 | 2 |
| Qwen27B | 4 | 5 | 9 | 3.268 | 0 |
| Gemma26B | 4 | 5 | 9 | 1.810 | 0 |

Это6 source groups, AI-assisted translation, human validation PENDING. Gemma и Qwen имеют одинаковые strict outcomes по этим12 records; mean QA F1≈0.900/0.915 соответственно. У GPT первый EN QA6/6 затем4/6: instability/CLI settings не позволяют считать первый результат устойчивым. Нельзя заявлять преимущество русского языка, подтверждённую generalization или универсальное аграрное знание по этому probe.

## Tools, routing и offline

Детерминированные GDD/VPD/ET₀/rain deficit/missing-input gates сохранены и протестированы отдельно. ET₀ FAO Example18:3.877117 mm/day против3.88 reference. Ограничения unit flags, numerical tolerance и substring grounding документированы.

Новая policy v2 отдельно от исторического router: hard gate → local reader только при supplied context → planned cloud; без context сразу cloud. Offline без поддержки — ABSTAIN.

На сохранённых ответах Gemma DEV36 tools+cloud планирует24/36 обращений, hybrid18/36: относительное сокращение25%, абсолютное16.67 п.п. **Это routing projection; actual new cloud calls0.** У всех6 QA substring grounding есть, strict correct4/6; два EM failures различаются длиной span и могут быть содержательно правильными. Grounding не является confidence или гарантом factual accuracy.

Offline Gemma v2, **cached replay**:16/36=44.4%,12 ANSWER,6 ASK_FOR_DATA,18 ABSTAIN;6 tool/6 local traces, cloud0. Mean reconstructed0.271 s, p95≈1.611 s; это не live latency каждой политики. Correct abstention rate UNKNOWN: gold ABSTAIN в срезе отсутствует. Старый GPT replay18/36 сохранён отдельно.

Создана таблица manualDEV30 с question/context/inputs/gold/expected eligibility/local output/correctness; human audit PENDING, cloud/hybrid answer columns NOT RUN. Bootstrap CI группируются по source/family; они широкие. Exploratory comparisons не создают независимое подтверждение.

## Независимый эксперимент и цена

| Новый final компонент | Статус |
|---|---|
| Holdout | Selected n0; target150; NOT RUN |
| LOCAL ONLY на новом holdout | NOT RUN |
| CLOUD ONLY | NOT RUN |
| TOOLS+CLOUD | NOT RUN |
| TOOLS→LOCAL→CLOUD | NOT RUN |
| Live offline на новом holdout | NOT RUN |
| Cloud/hybrid latency difference | NOT RUN |
| Actual cloud cost difference | NOT RUN |
| Hypothesis support на новом holdout | Не установлено |

Доступный project CLOUD_API_KEY на HOME PC не найден; LM Studio HTTP token не настроен. Локальные CLI исследования продолжены. Новый расход облачного API **$0**. Для150 requests по6000input+512output tokens при Mercury2.5 $0.04/$0.15 за миллион плановая оценка$0.04752, DEV36≈$0.0114048. Это estimate по [официальным ценам](https://docs.inceptionlabs.ai/get-started/models), не invoice.

`PROTOCOL_FREEZE_2026-10-01.md` имеет явный NOT FROZEN, без holdout IDs. Новый final не выполнялся и не выдаётся за зарегистрированный эксперимент.

## Аутентификация и публикация

Старые Mercury2/2.5 raw использовали project-configured process variable CLOUD_API_KEY по совпадающему provider hash. Владелец ключа/биллинг Антона не доказан; invoice/quota/account attribution отсутствуют. Исторически162 cloud calls,161 raw HTTP response,93518input/23984output tokens, сумма известных оценок$0.01262669 плюс один503 с неизвестным usage. Jev в этих трёх research runs не использован.

Научный registry содержит69 уникальных кандидатов,50 дат2024–2026,26 abstract/partial-method checks; это не69 прочитанных full texts. Материал старого CPU study подходит для подготовки узкой статьи6–8 страниц с честными ограничениями. Для статьи о подтверждённой гипотезе сильного HOME-PC local stage доказательств пока недостаточно.

Отдельная таблица Excel содержит15 итоговых моделей и25 run×model агрегатов: `outputs/home_pc_20261001/home_pc_models_20261001.xlsx`. Из339 сохранённых локальных requests известны token counts для286:135133 input/39087 output. Остальные53 остаются UNKNOWN, а не нулём. Токены reasoning GPT-OSS включены в output. [HF shortlist](HF_MODELS_HOME_PC_SHORTLIST_RU.md) содержит9 кандидатов с точными файлами/лицензиями и оценкой памяти; Qwen4B Q8, Phi4-mini Q8 и native CPU BitNet идут первыми. Новые генеративные и аграрные веса не скачивали.

Открытый аналог слоя решений Jev скачан и протестирован отдельно: [Laya multilingual](JEV_LOCAL_ALTERNATIVE_RU.md),321.9M parameters, Apache2, выбранные model/tokenizer artifacts678212540bytes, SHA256 verified. CPU float32/4threads: routing9/12=75%, EN5/6,RU4/6; p50/p95 .424/.620s, peak process RSS2.16GiB, errors0. Missing-data classification6/12; оба сценария без humidity ошибочно направлены к VPD. Поэтому действующий deterministic missing-input gate обязателен, raw probabilities не калиброваны. Это12 synthetic DEV cases, не сравнение с платным Jev, не генеративное QA и не новый confirmatory result. Его12 requests не прибавляются к339 LM Studio generation requests; decode/output tokens для encoder N/A.

Следующий исследовательский этап: controlled local HTTP DEV с фиксированными schema/budgets; небольшой Mercury DEV pilot; независимая ручная проверка gold/переводов; окончательный protocol и holdout150; один final run без настройки по его ответам.

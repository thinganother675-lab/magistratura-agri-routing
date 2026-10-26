"""Coherent current matrix with per-version failures and explicit missing data."""
from pathlib import Path
from datetime import datetime,timezone
import json
import hashlib

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
META=ROOT/'results/20261002_182916Z_ef105dbe_openrouter21_metadata'
ORIGINAL=ROOT/'results/20261002_181544Z_454d35c7_openrouter21_screen'
CHILD=ROOT/'results/20261002_183356Z_32261f33_openrouter21_screen'
SETUP=ROOT/'results/20261002_182623Z_openrouter_zero_child_setup'
manifest=json.loads((META/'manifest.json').read_text(encoding='utf-8'))
diagnostic=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
zdr=json.loads((OUT/'zdr_catalogue.json').read_text(encoding='utf-8'))
zdr_pairs={(item.get('model_id'),item.get('tag')) for item in (zdr.get('response') or {}).get('data',[])}
records=[]
for version,directory in [('ORIGINAL_MANAGEMENT_KEY_401',ORIGINAL),('ORDINARY_ZERO_KEY_403',CHILD)]:
    for line in (directory/'raw.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        records.append({'version':version,'source':directory.relative_to(ROOT).as_posix()+'/raw.jsonl',
                        'model':row['model_requested'],'endpoint':row['endpoint_pinned'],
                        'http_status':row['http_status'],'latency_seconds':row['latency_seconds'],
                        'successful_generation':False,'input_tokens':None,'output_tokens':None,
                        'reported_cost_usd':None})
records.append({'version':'SEPARATE_FIXED_FREE_CONNECTIVITY_DIAGNOSTIC',
                'source':OUT.relative_to(ROOT).as_posix()+'/summary.json',
                'model':diagnostic['model_requested'],'endpoint':diagnostic['endpoint_pinned'],
                'http_status':diagnostic['http_status'],'latency_seconds':diagnostic['latency_seconds'],
                'successful_generation':False,'input_tokens':None,'output_tokens':None,
                'reported_cost_usd':None,'safe_error':diagnostic.get('safe_error')})
rows=[]
for index,source in enumerate(manifest['rows'],1):
    endpoint=source.get('selected_endpoint') or {}
    tag=endpoint.get('tag') or endpoint.get('provider_slug') or endpoint.get('provider_name')
    attempts=[row for row in records if row['model']==source['resolved_model_id']]
    row={
      'index':index,'requested_display_name':source['requested_display_name'],
      'resolved_model_id':source['resolved_model_id'],'provider_endpoint_pinned':tag,
      'advertised_endpoint_quantization':endpoint.get('quantization'),
      'actual_remote_model_quantization':'UNKNOWN',
      'catalogue_pricing_all_published_components':source.get('pricing'),
      'endpoint_pricing_all_published_components':endpoint.get('pricing'),
      'input_output_modalities':source.get('modalities'),'context_length':source.get('context_length'),
      'scope':source.get('scope'),'identity_stability':source.get('identity_stability'),
      'attempts':attempts,'generation_attempts':len(attempts),'successful_generations':0,
      'input_tokens':None,'output_tokens':None,'token_usage_coverage':{'known_n':0,'attempts_n':len(attempts)},
      'reported_cost_usd':None,'quality_result':None,'p50_generation_latency_seconds':None,
      'p95_generation_latency_seconds':None,'ttft_seconds':None,'tokens_per_second':None,
      'vram_ram_gpu_offload':'UNKNOWN / NOT APPLICABLE TO THIS REMOTE MEASUREMENT',
      'structured_output_failures':'NOT EVALUABLE: no generated response',
      'catalogue_endpoint_listed_zdr':(source['resolved_model_id'],tag) in zdr_pairs if tag else None,
      'status':source['status'],'reason':source['reason'],
      'shared_screen_prerequisite':'BLOCKED: execution stopped after access failure; account policy compatibility is not established for every model',
      'own_http_failure_observed':bool(attempts),
    }
    if attempts:
        if any(attempt['http_status']==404 for attempt in attempts):
            row.update(status='BLOCKED_ACCOUNT_PRIVACY_DIAGNOSTIC_HTTP404',
              reason='One explicit :free diagnostic rejected for both free model training and ZDR account settings. No generated output.')
        else:
            row.update(status='BLOCKED_ACCESS_HTTP401_AND_HTTP403',
              reason='Management-key401 cause verified; ordinary-key403 exact cause UNKNOWN. No generated output.')
    elif source.get('eligible'):
        row.update(status='NOT_RUN',reason='No completion attempted for this candidate; shared access/privacy prerequisite blocked the screen. Own compatibility UNKNOWN.')
    rows.append(row)
assert len(rows)==21 and sum(row['generation_attempts'] for row in rows)==3
assert sum(row['status']=='NOT_RUN' for row in rows)==16
summary={
 'created_utc':datetime.now(timezone.utc).isoformat(),'status':'BLOCKED_CURRENT_21_MODEL_SCREEN',
 'requested_models_n':21,'text_candidates_eligible_by_price_n':18,
 'text_models_with_actual_attempts_n':2,'text_models_never_attempted_n':16,
 'paid_music_models_excluded_n':2,'safety_classifier_excluded_n':1,
 'generation_attempts':3,'successful_generations':0,'full_dev_benchmarked_models_n':0,
 'http_failures':{'401':1,'403':1,'404':1},
 'total_external_requests':111,'metadata_get_requests':107,'credential_setup_post_requests':1,
 'cost_usage_coverage':{'known_cost_n':0,'known_input_tokens_n':0,'known_output_tokens_n':0,'attempts_n':3},
 'total_cost_usd':None,'account_aggregate_usage_usd':diagnostic['quota_after']['usage'],
 'current_global_daily_free_requests':diagnostic['quota_after']['free_model_daily_requests'],
 'paid_spend_cap_usd':0,'actual_successful_paid_generations':0,
 'management_key_source':'project_env:openrouter_api_key_2',
 'ordinary_key_source':'project_env:OPENROUTER_INFERENCE_KEY_ZERO_20261002',
 'same_account_single_child_key_created':True,'management_key_unchanged':True,
 'privacy_preferences_changed':False,'budget_limit_increased':False,
 'quota_account_or_key_rotation':False,'retries_or_provider_model_fallback':False,
 'limit_zero_free_completion_eligibility':'NOT DEMONSTRATED; diagnostic fails on privacy before proving credit-cap compatibility',
 'scope_limit':'These are connectivity/access failures, not quality or model speed measurements.',
 'exact_verified_blocker_for_lfm':diagnostic['safe_error']['message'],
 'ling_ordinary_key_403_cause':'UNKNOWN',
 'zdr_public_catalogue_scope':'Listing indicates endpoint-level ZDR only; it does not prove current account access or free-training opt-in. Ling is listed despite its403.',
 'rows':rows,
 'preserved_run_directories':[directory.relative_to(ROOT).as_posix() for directory in (ORIGINAL,CHILD,OUT)],
 'current_prerequisites':[
   'Review OpenRouter account Privacy settings and access/guardrail restrictions; no automatic loosening is authorized by this protocol.',
   'Decide explicitly whether public/synthetic DEV prompts may be sent to a free provider under its data handling policy. Preserve the $0 spending limit.',
   'For a new trial use a versioned plan/catalogue/claim, keep all three failures, and grant an exclusive measurement window.',
   'Do not buy credits, raise the child key limit, change accounts, rotate keys to evade quota, or substitute paid variants.'
 ],
}
(OUT/'current_21_model_matrix.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
doc='''# OpenRouter: актуальный скрининг 21 моделей — 02.10.2026

## Фактический итог

**Заблокировано на проверке доступа.** Все 21 названия сопоставлены с точными ID официального каталога. По опубликованным ценам разрешены 18 текстовых кандидатов; фактически попытки сделаны для двух, остальные 16 **NOT RUN**. Две Lyria платны за музыкальный результат и исключены; Content Safety — классификатор, исключён из общей генеративной оценки.

**3 completion-попытки, 0 генераций, 0 полных DEV-бенчмарков.** Ошибки всех версий сохранены: Ling/Novita с management-ключом → HTTP 401; Ling/Novita с обычным ключом лимита $0 → HTTP 403; отдельно разрешённый connectivity-only LFM/Liquid → HTTP 404. Нулевых ответов нельзя превращать в оценку качества модели. Задержки 0.260/0.145/0.099 с — время отказа, не время inference.

## Ключи, приватность и установленные причины

Исходный `openrouter_api_key_2` — management/provisioning-ключ. Эти флаги подтверждены `GET /key`; [официальная документация](https://openrouter.ai/docs/guides/overview/auth/management-api-keys) исключает его использование для completion. Это объясняет исходный HTTP 401.

По разрешённой настройке создан **один** обычный inference-ключ в том же аккаунте через официальный `POST /keys` (HTTP 201), только в игнорируемом `.env`: `OPENROUTER_INFERENCE_KEY_ZERO_20261002`. Исходный ключ и его байты сохранены. Подтверждены `is_management_key=false`, `is_provisioning_key=false`, `limit=0`, `limit_remaining=0`, `include_byok_in_limit=true`, отсутствие сброса лимита, срок до 09.10.2026 23:59:59 UTC. Значения, префиксы, fingerprint и creator ID в артефакты не записаны. [API создания ключа](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key).

**Точная причина HTTP 403 для Ling с обычным ключом UNKNOWN**: исходный безопасный runner сохранил код ошибки, но не её тело. Валидный `GET /key` не доказывает разрешение inference. [Документация ошибок](https://openrouter.ai/docs/api/reference/errors-and-debugging) допускает для 403 ограничения прав, guardrail и moderation.

**Причина HTTP 404 отдельного LFM-запроса подтверждена** очищенным ответом сервиса:

> 0 endpoints out of 1 requested are available matching your guardrail restrictions and data policy.
> Free model training violation (account settings): 1 endpoint excluded.
> ZDR violation (account settings): 1 endpoint excluded.

Это доказательство несовместимости данного free endpoint с текущими настройками аккаунта. Другие 16 текстовых моделей не вызывались; им не приписываются измеренные HTTP-ошибки. Публичный `GET /endpoints/zdr` получен отдельно: наличие endpoint в списке ZDR не гарантирует доступ текущего аккаунта и согласие на условия free-моделей. Например, Ling/Novita в списке есть, но фактический запрос получил 403. [ZDR и фильтрация данных](https://openrouter.ai/docs/guides/features/zdr), [ограничения guardrail](https://openrouter.ai/docs/guides/features/guardrails/overview).

Настройки приватности, обучение на данных, ZDR, денежный лимит и аккаунт **не изменены**. Платных fallback, пополнения, ротации ключей ради обхода квоты и повторов нет. Дополнительный ключ исправил тип аутентификации, а не создал новую квоту.

## Актуальная матрица

| Запрошенная модель | Точный ID | Закреплённый endpoint | Актуальный статус | Попытки / ответы |
|---|---|---|---|---:|
'''
for row in rows:
    doc+='| '+row['requested_display_name'].replace('|','/')+' | `'+str(row['resolved_model_id'])+'` | '+str(row['provider_endpoint_pinned'] or '—')+' | '+row['status']+' | '+str(row['generation_attempts'])+' / 0 |\n'
doc+='''

Для `NOT_RUN` общий prerequisite скрининга заблокирован; собственная совместимость модели UNKNOWN. Полные цены, модальности, context length, объявленная квантовка endpoint, список версий попыток и ресурсные поля сохранены в `current_21_model_matrix.json`. Реальная удалённая квантовка/веса/RAM/VRAM/GPU-offload UNKNOWN. Технический паспорт endpoint не является измерением этих ресурсов.

Lyria Pro имеет опубликованную цену **$0.08 за песню**, Lyria Clip — **$0.04 за результат** в описании каталога, даже когда token pricing равно нулю. Ни одного музыкального запроса не было. Анонимная Space Bunny и Dots preview обозначены exploratory; кодовые Laguna/North и медицинская Ling Sante отделены по scope. Ни одна из них не оценивалась по содержанию ответов.

## Квота, токены и внешние запросы

Последний фактический `GET /key`: общая бесплатная дневная квота **50**, использовано **0**, осталось **50**; лимит ключа **$0**, aggregate usage **$0**. [Квоты действуют глобально](https://openrouter.ai/docs/api/reference/limits), а не обновляются с новым ключом.

Итого ветка: **111 внешних запросов** = **107 metadata GET + 1 setup POST + 3 completion POST**. Последний публичный ZDR-каталог добавил один metadata GET к ранее зафиксированным 110. Стоимость, input/output tokens отдельных неуспешных completion-запросов **UNKNOWN**, покрытие **0/3**. Нулевой aggregate usage не подменяет отсутствующую детализацию invoice. TTFT, tok/s, качество, генеративные p50/p95 и структурная надёжность **NOT RUN**.

## Протокол и сохранённые артефакты

Скрининг development-only: общий старый DEV12 selector, первый extractive EN пример и затем RU missing-input, только публичные input/context/inputs; gold, категория и expected route в провайдерный payload не передавались. План: сначала все 18 endpoint по одному примеру, затем 14 общих текстовых по второму, максимум две стабильные модели по 9 различным DEV-примерам. Нормальный максимум — 46 запросов; жёсткий cap49 и один резерв глобальной квоты. До этого этапа фактические запуски не дошли. Новый confirmatory holdout **NOT RUN**.

temperature=0, max_tokens=512, concurrency=1, минимум 3.1 с между стартами, timeout45 с, stream=false. Модель/endpoint закреплены, allow_fallbacks=false, require_parameters=true, опубликованные monetary-компоненты строго равны нулю; max_price prompt/completion/request/image=0. Структурный формат зависит от опубликованной поддержки endpoint и записан в точном payload. HTTP 401/403/402/429 останавливает свою версию после одной ошибки. В отдельно разрешённом диагностическом запуске был ровно один фиксированный LFM POST, без автоматического перехода между моделями.

**24 профильных теста PASS** перед ordinary-key запуском: поиск точных ID и credential sources, запрет paid siblings/unknown prices/media fees, сохранение приватности, исключение gold из payload, схема JSON, остановки на ключевых ошибках. Это проверяет harness, не доказывает успешную генерацию.

- Исходная metadata-фаза: `results/20261002_172052Z_682669ff_openrouter21_metadata`.
- Management-key401: `results/20261002_181544Z_454d35c7_openrouter21_screen`, исходный driver сохранён и SHA256 совпадает с run config.
- Создание ordinary-key и checkpoint: `results/20261002_182623Z_openrouter_zero_child_setup`.
- Свежий каталог ordinary-key: `results/20261002_182916Z_ef105dbe_openrouter21_metadata`.
- Ordinary-key403: `results/20261002_183356Z_32261f33_openrouter21_screen`, driver_executed.py совпадает с run config SHA256.
- Однократный LFM404 diagnostic, safe error, ZDR-каталог и текущая общая матрица: `results/20261002_183639Z_openrouter_zero_diagnostic`.

Старые raw/config/summary и исторические научные результаты неизменны. Текущий документ является сводным статусом; первоначальные интерпретации сохранены в отдельных versioned JSON и не подменяют его.

## Точное условие продолжения

1. Проверить [OpenRouter Privacy](https://openrouter.ai/settings/privacy) и применимые права/guardrail. Для LFM сервис подтвердил блокирующие free-training и ZDR условия; для Ling403 точная причина всё ещё неизвестна.
2. Явно решить, допустима ли передача публичных/синтетических DEV-примеров выбранному бесплатному провайдеру с его политикой обработки данных. Настройки не ослаблять автоматически. Если приватность должна остаться строгой, использовать совместимый endpoint только после подтверждения доступа или продолжать локальные/другие уже доступные провайдеры.
3. Сохранить денежный лимит **$0**; не покупать credits, не повышать cap, не менять аккаунт/ключи для обхода лимитов и не переходить на paid sibling.
4. Перед новым запуском создать отдельный протокол/metadata/claim и получить новое изолированное окно. Уже использованные claims не запускать повторно; все три ошибки остаются в журнале.

Текущая ветка OpenRouter остановлена, окно освобождено для локальных работ. Лучший OpenRouter-кандидат, качество русской подвыборки и Pareto-сравнение **NOT RUN**.
'''
(ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md').write_text(doc,encoding='utf-8')
print(json.dumps({'current_matrix':(OUT/'current_21_model_matrix.json').relative_to(ROOT).as_posix(),
                  'generation_attempts':3,'successes':0,'not_run_text':16,'external_requests':111,
                  'cost_usage_coverage':'0/3','settings_changed':False}))

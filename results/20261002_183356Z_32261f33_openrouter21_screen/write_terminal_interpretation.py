"""Derived evidence; preserve original raw/score/config/summary artifacts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
summary_path=OUT/'summary.json'
summary=json.loads(summary_path.read_text(encoding='utf-8'))
config=json.loads((OUT/'config.json').read_text(encoding='utf-8'))
quota_before=json.loads((OUT/'quota_before.json').read_text(encoding='utf-8'))
quota_after=json.loads((OUT/'quota_after.json').read_text(encoding='utf-8'))
old=ROOT/'results/20261002_181544Z_454d35c7_openrouter21_screen'
assert summary['generation_attempts']==1 and summary['successful_generations']==0
assert quota_before['http_status']==200 and quota_after['http_status']==200
assert quota_after['is_management_key'] is False and quota_after['is_provisioning_key'] is False
assert quota_after['limit']==0
source=ROOT/'scripts/openrouter_screen_20261002.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()==config['code_sha256']
(OUT/'driver_executed.py').write_bytes(source.read_bytes())
rows=[]
for row in summary['rows']:
    derived={k:row.get(k) for k in ('requested_display_name','resolved_model_id','endpoint_pinned','scope','pricing','context_length','modalities','attempts','successful_generations','status','reason')}
    if row['attempts']:
        derived.update(status='FORBIDDEN_HTTP403_NO_GENERATION', model_quality_result=None,
                       failure_latency_seconds=row['mean_latency_seconds'],
                       reason='One HTTP403; global prerequisite stop. The precise permissions/guardrail/moderation reason is UNKNOWN.')
    elif row['status']=='NOT_RUN':
        derived['reason']='NOT RUN after first HTTP403. No claim that this model itself would be rejected.'
    rows.append(derived)
report={
 'written_utc':datetime.now(timezone.utc).isoformat(),
 'status':'BLOCKED_FORBIDDEN_HTTP403_CAUSE_UNKNOWN',
 'original_summary_sha256':hashlib.sha256(summary_path.read_bytes()).hexdigest(),
 'original_raw_config_scores_summary_preserved':True,
 'measurement_window':config['measurement_window'],
 'management_key_source':'project_env:openrouter_api_key_2',
 'inference_key_source':config['credential_source'],
 'inference_type_verified_by_metadata':True,
 'new_trial_generation_attempts':1,'new_trial_successful_generations':0,
 'all_versioned_trials_generation_attempts':2,'all_versioned_trials_successful_generations':0,
 'all_versioned_trials_error_counts':{'HTTP401_management_key':1,'HTTP403_ordinary_key':1},
 'global_free_requests':quota_after['free_model_daily_requests'],
 'account_key_aggregate_usage_usd_before':quota_before['usage'],
 'account_key_aggregate_usage_usd_after':quota_after['usage'],
 'per_attempt_cost_and_input_output_tokens':'UNKNOWN; no provider usage response for either failed attempt',
 'price_filters_all_zero':True,'paid_spend_cap_usd':0,
 'limit_zero_free_completion_eligibility':'NOT DEMONSTRATED; HTTP403 alone does not identify credit policy as the cause',
 'total_external_requests_branch':105,
 'request_classes_branch':{'generative_attempts':2,'setup_post':1,'metadata_get':102},
 'no_completion_retries_model_fallback_provider_fallback_or_key_rotation':True,
 'no_limit_increase_topup_purchase_or_privacy_override':True,
 'quality_latency_generation_speed_benchmark':'NOT RUN; 0.145s is rejection latency, not inference performance',
 'all21_rows':rows,
 'source':'https://openrouter.ai/docs/api/reference/errors-and-debugging',
 'blocker':'The ordinary zero-cap key is valid for GET/key but the first fixed model/provider completion is forbidden.',
 'resume_precondition':'Identify the service rejection reason or receive an explicit new versioned diagnostic plan; do not rerun claims or alter cap/privacy/provider fallback.',
 'window_released':True,
}
(OUT/'terminal_interpretation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
doc=ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md'
header='''

## Итог нового окна OR_ZERO_20261002_1834Z

Обычный ключ с лимитом $0 проверен в новом независимом журнале: `results/20261002_183356Z_32261f33_openrouter21_screen`. На первом закреплённом endpoint `inclusionai/ling-3.1-flash` → `novita` получен **HTTP 403**, задержка отказа **0.145 с**. Немедленная остановка: **1 попытка, 0 генераций, 0 повторов**. Остальные 17 текстовых моделей **NOT RUN**. Две музыкальные Lyria остаются **PAID_NOT_AUTHORIZED**, Content Safety — **SPECIALIZED_NOT_COMPARABLE**.

`GET /key` до и после запроса отвечает HTTP 200: ключ обычный (`is_management_key=false`, `is_provisioning_key=false`), лимит денег 0, общая бесплатная квота 50/50, использовано 0, агрегатный usage=0. **Точная причина HTTP 403 UNKNOWN**: исходный безопасный runner не сохранял тело ошибок. Согласно [официальному описанию ошибок](https://openrouter.ai/docs/api/reference/errors-and-debugging), HTTP 403 может означать недостаточные права, guardrail или moderation; один статус не доказывает запрет бесплатных запросов при лимите $0. Настройки приватности и денежный лимит не изменялись. Корректно утверждать только отказ этой попытки, а не непригодность всех моделей.

Вся версия ветки: **2 попытки генерации, 0 полученных ответов** — одна прежняя HTTP 401 с management-ключом и новая HTTP 403 с обычным. **105 внешних запросов**: 102 metadata GET, 1 setup POST, 2 completion POST. Входные/выходные токены и стоимость каждого неуспешного запроса **UNKNOWN**. Задержку отказа нельзя использовать как скорость модели; качество, TTFT, tok/s и результат DEV9 **NOT RUN**. Удалённые VRAM/RAM/offload UNKNOWN.

Итоговая производная матрица с разграничением фактической попытки и незапущенных моделей сохранена в `terminal_interpretation.json`; первоначальные raw/config/summary и научные результаты не перезаписаны. Исходный код этого окна сохранён как `driver_executed.py`, SHA256 совпадает с run config. Проверки runner перед запуском: **24 PASS**.

Все 21 запрошенные позиции:

| Запрошенная модель | Точный ID | Фактический статус | Попытки / ответы |
|---|---|---|---:|
'''
lines=[]
for row in rows:
    lines.append('| '+row['requested_display_name'].replace('|','/')+' | `'+str(row['resolved_model_id'])+'` | '+row['status']+' | '+str(row['attempts'])+' / '+str(row['successful_generations'])+' |')
tail='''

Окно измерений закрыто, независимые локальные работы могут продолжаться. Для продолжения OpenRouter нужно выяснить причину запрета либо заранее определить отдельный диагностический запуск; текущие claims повторно запускать нельзя. Платный fallback, пополнение, повышение нулевого лимита и ротация ключей для обхода квоты не выполнялись.
'''
with doc.open('a',encoding='utf-8') as handle:
    handle.write(header+'\n'.join(lines)+'\n'+tail)
print(json.dumps({'interpretation':(OUT/'terminal_interpretation.json').relative_to(ROOT).as_posix(),
 'status':report['status'],'new_attempts':1,'branch_external_requests':105,'window_released':True}))

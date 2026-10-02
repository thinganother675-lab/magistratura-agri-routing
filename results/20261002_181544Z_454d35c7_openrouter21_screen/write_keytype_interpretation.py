"""Versioned correction of auth interpretation after the key-type GET."""
from pathlib import Path
from datetime import datetime,timezone
import json
import hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
summary=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
diagnostic=json.loads((HERE/'key_type_diagnostic.json').read_text(encoding='utf-8'))
assert diagnostic['is_management_key'] is True and diagnostic['is_provisioning_key'] is True
rows=[]
for old in summary['rows']:
    row=dict(old)
    row['original_test_status']=row['status']
    row['actual_generation_test_status']='OBSERVED_HTTP401_NO_GENERATION' if row['attempts'] else 'NOT_RUN'
    if row['status'] in ('NOT_RUN','AUTH_BLOCKED'):
        row.update(status='AUTH_BLOCKED',reason='Configured key2 is a management/provisioning key; official policy excludes completion calls. No model-quality claim.')
    rows.append(row)
report={'corrected_utc':datetime.now(timezone.utc).isoformat(),
 'status':'BLOCKED_MANAGEMENT_KEY_USED_FOR_INFERENCE',
 'parent_summary_sha256':hashlib.sha256((HERE/'summary.json').read_bytes()).hexdigest(),
 'key_type_diagnostic_sha256':hashlib.sha256((HERE/'key_type_diagnostic.json').read_bytes()).hexdigest(),
 'generation_attempts':1,'successful_generations':0,
 'original_run_external_requests':50,'separate_key_type_metadata_requests':1,
 'session_branch_external_requests_total':51,
 'cause_supported_by_evidence':'is_management_key=true and is_provisioning_key=true; official management-key policy forbids completion endpoints',
 'new_inference_calls_for_this_reanalysis':0,
 'original_raw_scores_manifest_config_summary_preserved':True,
 'rows':rows,'source':'https://openrouter.ai/docs/guides/overview/auth/management-api-keys',
 'regular_inference_key_created':False,
}
(HERE/'authentication_interpretation_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
doc=ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md'
text=doc.read_text(encoding='utf-8')
latest='''## Установленная причина HTTP401

**BLOCKED: management/provisioning key.** Отдельный metadata GET 2026-10-02 18:20:14 UTC установил `is_management_key=true` и `is_provisioning_key=true` для exact `openrouter_api_key_2`. [Официальная документация](https://openrouter.ai/docs/guides/overview/auth/management-api-keys) запрещает management keys для completion endpoints: они предназначены для административных операций. Поэтому GET metadata работает, а chat POST отклонён; модельный benchmark не состоялся.

Новая версия интерпретации: `results/20261002_181544Z_454d35c7_openrouter21_screen/authentication_interpretation_v2.json`. Для18 text endpoints статус **AUTH_BLOCKED** по общей credential prerequisite; фактически первая модель получила один401, остальные17 **NOT RUN**. Lyria2 остаются PAID_NOT_AUTHORIZED, Content Safety SPECIALIZED_NOT_COMPARABLE. Исходный summary с неопределённой причиной сохранён; новые выводы не переписывают raw evidence. Всего51 внешнее обращение в этой ветви: 1 generation attempt, 49 metadata GETs исходных stages и 1 отдельный key-type GET. Успешных generations0, токены/стоимость отдельного401 UNKNOWN, `/key` usage до/после0 и quota50.

Минимальная prerequisite: обычный inference key того же аккаунта с нулевым paid limit либо безопасно выданный child inference key через management API. Management credential сохранять; не использовать смену аккаунта/ключа для обхода quota. Creation/purchase/account changes этим агентом не выполнялись. После исправления setup нужен **новый metadata/run directory**, отдельное quiet window и сохранение прежней неудачной попытки; повтор старого claimed command недопустим.

'''
if '## Установленная причина HTTP401' not in text:
    text=text.replace('## Команда и возобновление',latest+'## Команда и возобновление')
doc.write_text(text,encoding='utf-8',newline='\n')
print('Management key blocker documented in a new interpretation; original experiment files unchanged.')

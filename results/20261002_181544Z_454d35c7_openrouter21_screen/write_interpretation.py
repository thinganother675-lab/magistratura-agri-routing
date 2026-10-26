from pathlib import Path
from datetime import datetime, timezone
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
report={
 'recorded_utc':datetime.now(timezone.utc).isoformat(),
 'status':'BLOCKED_CHAT_INFERENCE_WITH_WORKING_METADATA_AUTH',
 'observed_chat_attempts':1,'successful_generations':0,
 'first_model':'inclusionai/ling-3.1-flash','pinned_endpoint':'novita',
 'chat_http_status':401,'error_response_latency_seconds':0.2603393999961554,
 'key_preflight_http_status':200,'key_postflight_http_status':200,
 'free_daily_used_before':0,'free_daily_used_after':0,
 'free_daily_remaining_before':50,'free_daily_remaining_after':50,
 'reported_account_usage_before':0,'reported_account_usage_after':0,
 'token_usage_coverage':'0/1; UNKNOWN input/output usage',
 'reported_per_request_cost':'UNKNOWN','provider_invoice_obtained':False,
 'persistent_auth_failure_measured':False,
 'stop_template_contains_persistent_word':True,
 'interpretation':'Only one chat POST401 observed. GET key auth succeeds. Account chat permission versus endpoint/provider auth cause UNKNOWN; remaining models not inferred. Error latency is not generation latency or quality evidence.',
 'retries':0,'paid_fallbacks':0,'original_raw_config_summary_preserved':True,
 'next_option':'A separately versioned exact-free connectivity diagnostic may be useful if root authorizes it; preserve this failed probe and exclude diagnostic timing from ranking.',
}
(HERE/'authentication_interpretation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
doc=ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md'
text=doc.read_text(encoding='utf-8')
insert='''## Причина остановки и границы вывода

На первой попытке `/chat/completions` для `inclusionai/ling-3.1-flash`, pinned `novita`, получен **HTTP401** за **0.260s**. `/key` до и после даёт HTTP200; quota остаётся used0/remaining50, reported account usage0. Новый ключ нельзя объявить полностью невалидным по одному rejected chat request. Причина — account chat permission либо endpoint/provider authentication — **UNKNOWN**.

В stop-template используется слово persistent, но измерен только **один POST401**, без retry. Для остальных17 eligible endpoints inference **NOT RUN**, а не доказанный401. Ноль успешных generations означает отсутствие quality/latency benchmark; error-response latency не является скоростью генерации. Per-request tokens/cost **UNKNOWN** (coverage0/1); нулевой known subtotal не означает известный полный invoice. Evidence: `results/20261002_181544Z_454d35c7_openrouter21_screen/authentication_interpretation.json`.

'''
if '## Причина остановки и границы вывода' not in text:
    text=text.replace('## Команда и возобновление',insert+'## Команда и возобновление')
doc.write_text(text,encoding='utf-8',newline='\n')
print('Separate interpretation saved; original raw/config/summary unchanged; no API calls.')

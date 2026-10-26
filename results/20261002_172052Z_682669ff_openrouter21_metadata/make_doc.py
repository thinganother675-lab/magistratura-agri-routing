"""Generate the concise evidence-backed OpenRouter21 report; no API calls."""
from pathlib import Path
from datetime import datetime,timezone
import json
import sys
import hashlib

ROOT=Path(__file__).resolve().parents[2]
BASE=Path(__file__).resolve().parent
source=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
for row in source['rows']:
    if not row.get('model'):continue
    description=(row['model'].get('description') or '').lower()
    if 'Lyria' in row['requested_display_name']:
        row.update(status='PAID_NOT_AUTHORIZED',eligible=False,selected_endpoint=None,reason='Ancillary music fee despite zero token fields; paid cap $0')
    elif row.get('eligible'):
        row['scope']='CODING_SPECIALIZED_SMOKE' if 'code' in row['requested_display_name'].lower() or 'coding agent model' in description else 'HEALTH_DOMAIN_TRANSFER_SMOKE' if 'health and medicine-focused' in description else 'GENERAL_TEXT_DEV'
source['corrected_utc']=datetime.now(timezone.utc).isoformat()
source['parent_manifest_sha256']=hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest()
source['correction_type']='Pre-inference ancillary-fee and specialized-model eligibility clarification; original snapshot preserved'
corrected_path=BASE/'eligibility_correction_v2.json'
if not corrected_path.exists():corrected_path.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv)>1 else None
byid={r['resolved_model_id']:r for r in result['rows']} if result else {}
lines=['# OpenRouter: 21 запрошенный кандидат, 02.10.2026','',
 '**'+(result['status'] if result else 'PARTIAL: metadata DONE, inference NOT RUN')+'**. Используется только `project_env:openrouter_api_key_2`; старый недействительный ключ не подставляется. `/key` подтвердил HTTP200, free daily quota50/remaining50/used0 в начальном snapshot. Quota принадлежит аккаунту, а не новому ключу. Paid cap этой ветви — **$0**.','',
 'Начальные metadata: `results/20261002_172052Z_682669ff_openrouter21_metadata/`. Все21 copied names разрешены в точные catalog IDs. Первоначальная token-only классификация Lyria сохранена как metadata snapshot, но corrected eligibility до любого inference учитывает ancillary per-song/per-clip charge: модели19/20 не вызываются. Каталог не гарантирует стабильности весов; provider tags/revisions сохраняются там, где API их сообщает.','',
 '## Все запрошенные кандидаты','',
 '| # | Requested display name | Exact ID | Context | Endpoint tag | Status / scope |','|---:|---|---|---:|---|---|']
for i,row in enumerate(source['rows'],1):
    measured=byid.get(row['resolved_model_id'])
    status=measured['status'] if measured else row['status']
    if 'Lyria' in row['requested_display_name']:status='PAID_NOT_AUTHORIZED; music generator'
    ep=row.get('selected_endpoint') or {}
    tag=measured.get('endpoint_pinned') if measured else ep.get('tag') or ep.get('provider_name') or '—'
    scope=(str(measured['attempts'])+' attempts; '+measured.get('test_scope','NOT RUN')) if measured and measured['attempts'] else row.get('scope','')
    if status=='SPECIALIZED_NOT_COMPARABLE':scope='content moderation; general QA NOT RUN'
    lines.append(f"| {i} | {row['requested_display_name']} | `{row['resolved_model_id']}` | {row.get('context_length','UNKNOWN')} | `{tag}` | {status}; {scope} |")
lines+=['', 'Все присутствующие monetary components catalog/endpoint pricing проверяются как finite exact0, включая request/cache/image/audio поля, если они опубликованы. Словарь полных pricing сохранён для каждой строки; отсутствие отдельного поля не трактуется как измеренный нулевой invoice. Для текстовых запросов server-side `max_price` ограничивает prompt/completion/request/image нулём; audio/media/plugins не вызываются. Lyria3Pro сообщает $0.08/song, Clip $0.04/clip при token fields0 — это выявленный ancillary fee, а не бесплатная QA-модель.','',
 'Content Safety не ранжируется как answer generator. Ling Sante — отдельный health-domain agricultural transfer smoke. North Mini Code и обе Poolside Laguna получают отдельный synthetic coding-dispatch smoke, а не agricultural leaderboard score. Alpha/anonymous/preview candidates остаются exploratory и исключены из reproducible shortlist selection.','',
 '## Контроль эксперимента','',
 'Один последовательный worker, concurrency1, timeout45s, ≥3.1s между началами запросов. Сначала каждому из18 подходящих endpoints один connectivity/format probe; general14 затем общий RU missing-input probe. При достаточной quota два стабильных general candidates получают ещё7 одинаковых DEV cases: итого9 distinct cases каждый. Shortlist priority использует два предварительных наблюдения, поэтому не объявляет надёжный рейтинг моделей. Неуспешные попытки/таймауты остаются в знаменателе. Нельзя сопоставлять n1/n2 probes с full DEV9 по итоговому проценту.','',
 'Фиксируются model/provider identities, settings, prompt hashes, tokens/cost coverage, start/end UTC и полный sanitized output. Для nonstream responses TTFT/tok-s — **UNKNOWN**; latency — client end-to-end service measurement вместе с очередью и сетью. VRAM/RAM/GPU offload удалённого провайдера — **NOT APPLICABLE / allocation UNKNOWN**. Старый150-task holdout не вызывается; используются ранее существовавшие DEV tasks.','',
 'Fresh catalogue/key/endpoint snapshots повторно проверяются перед inference. `provider.only` и `order` фиксируют tag, `allow_fallbacks=false`, `require_parameters=true`, cross-model fallback отсутствует. Account/privacy/data-retention settings не меняются. Providers получают только public/synthetic question/context/numeric fields, без gold/category/expected-route. Persistent401/403 останавливает весь screening;429 checkpoint сохраняет Retry-After и quota evidence, без retry/provider/account/key rotation.','',
 '## Результаты','']
if result:
    cost='UNKNOWN' if result.get('known_reported_cost_usd') is None else '$'+format(result['known_reported_cost_usd'],'.8f')
    lines.append(f"{result['generation_attempts']} generative attempts; {result['successful_generations']} successful generations; {result['total_external_requests']} total external requests с учётом metadata. Известный reported cost {cost}; unknown-cost events {result['unknown_cost_events']}. Invoice не получен; нулевая цена — endpoint condition на дату, а не отсутствие экономической стоимости inference.")
    lines+=['','| Model | N | Correct / all attempts | Structured failures / errors | p50 / p95, s | Input / output known tokens (coverage) |','|---|---:|---:|---:|---:|---|']
    for r in result['rows']:
        if not r['attempts']:continue
        def fmt(x):return 'UNKNOWN' if x is None else f'{x:.3f}'
        it=r['known_input_tokens'];ot=r['known_output_tokens']
        lines.append(f"| `{r['resolved_model_id']}` | {r['attempts']} | {r['correct']}/{r['attempts']} | {r['structured_failures']}/{r['errors']} | {fmt(r['p50_latency_seconds'])}/{fmt(r['p95_latency_seconds'])} | {it['known_sum']} ({it['coverage_n']}/{r['attempts']}) / {ot['known_sum']} ({ot['coverage_n']}/{r['attempts']}) |")
    lines+=['',f"Stop reason: `{result['stop_reason']}`. Summary: `{Path(sys.argv[1]).resolve().relative_to(ROOT).as_posix()}`. Unequal N и малые группы не дают confirmatory вывода; request-cost UNKNOWN не заменяется0. Исторический Mercury baseline сохранён."]
else:
    lines+=['**NOT RUN**: ожидается isolated measurement window после model downloads/builds. Metadata GETs не выдаются за smoke-test или benchmark.']
lines+=['','## Команда и возобновление','',
 'До первого запуска и только после завершения прочих downloads/builds/local inference:','',
 '```powershell',
 '.venv\\Scripts\\python.exe scripts\\openrouter_screen_20261002.py --execute --metadata-dir results\\20261002_172052Z_682669ff_openrouter21_metadata --measurement-window <ROOT_CONFIRMED_QUIET_WINDOW>',
 '```','',
 'Exclusive claim исключает случайный повтор командой того же metadata run. После completed/429/timeout не повторять этот run, чтобы улучшить результат: новый trial требует новой versioned записи с сохранением всех прошлых попыток и условия quota reset. Никаких top-up/paid fallback.','',
 'Meaningful unit tests: **21 PASS** до timed calls; exact key2, fee/NaN/null rejection, no paid sibling substitution, provider pin, отсутствие hidden gold, excluded credential labels/hash. Обычный sandbox pytest столкнулся с Windows temp ACL; разрешённый запуск с новым workspace-local basetemp прошёл.','',
 '## Официальные источники','',
 '- [Provider routing: pinning, max_price, parameter support](https://openrouter.ai/docs/guides/routing/provider-selection)',
 '- [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models)',
 '- [Current key metadata](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)',
 '- [Account-wide credit/rate limits](https://openrouter.ai/docs/api_reference/limits)',
 '- [Privacy/data collection](https://openrouter.ai/docs/guides/privacy/data-collection)',
 '',f"Report generated UTC {datetime.now(timezone.utc).isoformat()}; metadata and inference execution timestamps remain in their own artifacts."]
(ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print('OpenRouter21 report updated without API calls.')

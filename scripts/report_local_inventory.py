"""Summarize all installed text-model DEV runs; never calls inference."""
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_runner', ROOT/'scripts/home_pc_benchmark.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def token_totals(data):
    totals={}
    for kind, field in [('input','prompt_tokens'),('output','completion_tokens')]:
        # Parser errors can retain CLI stats while having no normalized usage.
        # Recover only those provider-reported fields; never estimate by text.
        known=[r['local'].get('usage',{}).get(field, r['local'].get('stats',{}).get(field)) for r in data]
        values=[v for v in known if isinstance(v,(int,float)) and not isinstance(v,bool)]
        totals[kind+'_tokens_known_sum']=int(sum(values)) if values else None
        totals[kind+'_usage_coverage_n']=len(values)
        totals[kind+'_tokens_mean_known']=sum(values)/len(values) if values else None
    totals['usage_n']=len(data)
    totals['usage_complete']=all(totals[k+'_usage_coverage_n']==len(data) for k in ['input','output']) and bool(data)
    return totals

def report():
    chosen = {}; attempts = {}; all_runs=[]
    for run in sorted(ROOT.glob('results/20261001_*_cli')):
        manifest = read(run/'manifest.json')
        for key, meta in manifest['models'].items():
            raw_path=run/(key+'_raw.jsonl')
            raw_data=[json.loads(line) for line in raw_path.read_text(encoding='utf-8').splitlines()] if raw_path.exists() else []
            all_runs.append({'run':run.name,'model':key,'split':manifest['dataset_split'],
                'requests':len(raw_data),'load_success':meta['load_success'],
                **token_totals(raw_data),'diagnostic':meta.get('summary',{}),
                'offload_requested':meta['requested_offload'],'phase_error':meta.get('phase_error')})
            if manifest['dataset_split']!='old_dev': continue
            attempts.setdefault(key, []).append({'run':run.name, 'load_success':meta['load_success'],
                'phase_error':meta.get('phase_error'), 'n':(meta.get('summary') or {}).get('n', 0),
                'inventory':meta['inventory'],'offload_requested':meta['requested_offload'],
                'resource_guard_stop':meta.get('resource_guard_stop')})
            summary = meta.get('summary')
            if not summary or summary['decode_tps_median'] is None:
                continue
            # Known GPT channel-adapter diagnostic is preserved but excluded.
            if key == 'gpt-oss-20b' and summary['n'] < 12:
                continue
            old = chosen.get(key)
            if old is None or summary['n'] >= old[1]['summary']['n']:
                chosen[key] = (run, meta)
    directory = ROOT/'results'/('20261001_inventory_summary_'+uuid.uuid4().hex[:8])
    directory.mkdir(exist_ok=False)
    records = []; detail = {}
    for key, gpu in runner.CANDIDATES:
        item = chosen.get(key)
        if item is None:
            detail[key] = {'status':'INFERENCE NOT RUN', 'attempts':attempts.get(key, [])}
            failed_inventory=(attempts.get(key) or [{}])[-1].get('inventory',{})
            failed_quant=failed_inventory.get('quantization',{})
            records.append({'model':key,'n':0,'correct':None,'quality':None,'p50_s':None,'p95_s':None,
                'tok_s':None,'ttft_s':None,'vram_mib_total':None,'ram_gib_system':None,'errors':None,
                'quantization':failed_quant.get('name'),'size_gib':failed_inventory.get('sizeBytes',0)/2**30,
                'offload_requested':gpu,'source_run':None,'status':'INFERENCE NOT RUN'})
            continue
        run, meta = item; summary = meta['summary']; inventory = meta['inventory']
        quant = inventory.get('quantization', {})
        quant = quant.get('name') if isinstance(quant,dict) else str(quant)
        record = {'model':key,'n':summary['n'],'correct':summary['correct'],'quality':summary['quality'],
            'p50_s':summary['latency_p50_s'],'p95_s':summary['latency_p95_s'],
            'tok_s':summary['decode_tps_median'],'ttft_s':summary['ttft_median_s'],
            'vram_mib_total':meta['vram_mib_peak_sampled_total'],
            'ram_gib_system':meta['ram_gib_peak_sampled_system_used'],'errors':summary['errors'],
            'quantization':quant,'size_gib':inventory['sizeBytes']/2**30,
            'offload_requested':meta['requested_offload'],'source_run':run.name,
            'status':'RESOURCE STOP' if meta.get('resource_guard_stop') else 'EARLY STOP' if meta.get('early_stop') else 'COMPLETED DEV'}
        records.append(record)
        data=[json.loads(line) for line in (run/(key+'_raw.jsonl')).read_text(encoding='utf-8').splitlines()]
        record.update(token_totals(data))
        detail[key] = {'status':record['status'],
            'record':record,'summary':summary,'attempts':attempts[key],
            'raw_sha256':hashlib.sha256((run/(key+'_raw.jsonl')).read_bytes()).hexdigest(),
            'load_s':meta.get('load_s'),'resource_guard_stop':meta.get('resource_guard_stop')}
    # Same schema for an unavailable model; no zero token/correctness imputation.
    for r in records:
        if 'usage_n' not in r:
            r.update(token_totals([]))
    with (directory/'all_text_models.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    payload={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'DEVELOPMENT ONLY',
        'model_count':len(records),'models_with_inference':sum(r['n']>0 for r in records),
        'models_with_36_dev':sum(r['n']==36 for r in records),'models':detail,
        'warning':'Different N after predeclared four-error early stop; compare full36 only against full36. CLI generation limits UNKNOWN. No new final holdout/cloud calls.'}
    payload['all_runs']=all_runs
    payload['session_usage']={'requests':sum(r['requests'] for r in all_runs),
        'input_tokens_known_sum':sum(r['input_tokens_known_sum'] or 0 for r in all_runs),
        'output_tokens_known_sum':sum(r['output_tokens_known_sum'] or 0 for r in all_runs),
        'input_usage_coverage_n':sum(r['input_usage_coverage_n'] for r in all_runs),
        'output_usage_coverage_n':sum(r['output_usage_coverage_n'] for r in all_runs),
        'unknown_usage_not_imputed_as_zero':True,'cloud_calls_actual':0}
    (directory/'summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Все текстовые модели LM Studio: HOME-PC DEV','',
        '01.10.2026. Проверяются 15 текстовых LLM из 21 установленного артефакта. Три embeddings, image generation и две TTS не имеют применимой метрики в этом текстовом benchmark.',
        '',f'Сводка: `results/{directory.name}/summary.json`; полные model IDs, quantization, bytes и raw hashes сохранены.','',
        '| Model key | Quant | File GiB | Correct/N | p50 / p95 s | tok/s | VRAM MiB total | RAM GiB system | Errors | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in records:
        if not r['n']:
            lines.append(f"| {r['model']} | {r['quantization']} | {r['size_gib']:.2f} | NOT RUN | — | — | — | — | — | LOAD STOP |")
        else:
            lines.append(f"| {r['model']} | {r['quantization']} | {r['size_gib']:.2f} | {r['correct']}/{r['n']} | {r['p50_s']:.3f} / {r['p95_s']:.3f} | {r['tok_s']:.2f} | {r['vram_mib_total']:.0f} | {r['ram_gib_system']:.2f} | {r['errors']} | {r['status']} |")
    lines += ['', 'Четыре ошибки среди первых запросов прекращают smoke после минимум шести примеров. N поэтому различается. Доли на неполных smoke-срезах не ранжируются против full36; ранняя остановка отражает непригодность текущего adapter/settings, а не доказанную непригодность весов.',
        '', 'Локальный токен HTTP не настроен: использовался CLI с неизвестными temperature и output limits. Structured failures включают parser/transport errors; native function calling не проверялся. Для GPT-OSS tok/s включает reasoning. Latency включает запуск CLI и IPC.',
        '', 'VRAM — sampled total device use, RAM — whole-system use. Значения не равны private allocations модели. Guard контролирует запас памяти во время загрузки и перед inference; он не гарантирует непрерывной отмены запроса. Requested GPU ratio — не измеренное количество offloaded layers.',
        '', 'Эти измерения относятся к старому DEV и новым DEV translations. Новый независимый holdout NOT RUN; вывод о подтверждении основной гипотезы не получен.']
    (ROOT/'docs/ALL_LOCAL_MODELS_HOME_PC_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    tokens=['# Токены и offload: итоговые локальные прогоны','',
        '01.10.2026. Одна репрезентативная серия на модель: расширенный DEV36, где он выполнен, иначе последний smoke. Все серии и общий расход сессии сохранены в summary.json. Повторы языкового probe и диагностические серии не смешаны с основным качеством.',
        '', '| Model key | N | Input tokens known | Output tokens known | Usage coverage | GPU offload requested | Quant | File GiB | VRAM MiB total peak | RAM GiB system peak | TTFT s | Decode tok/s |',
        '|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|']
    for r in records:
        def number(key, digits=2):
            value=r.get(key)
            return 'UNKNOWN' if value is None else f'{value:.{digits}f}'
        coverage=f"{r['input_usage_coverage_n']}/{r['n']} input; {r['output_usage_coverage_n']}/{r['n']} output"
        tokens.append(f"| {r['model']} | {r['n']} | {number('input_tokens_known_sum',0)} | {number('output_tokens_known_sum',0)} | {coverage} | {r['offload_requested']} | {r['quantization']} | {number('size_gib')} | {number('vram_mib_total',0)} | {number('ram_gib_system')} | {number('ttft_s',3)} | {number('tok_s')} |")
    tokens+=['', f"Все сохранённые локальные серии: {payload['session_usage']['requests']} запросов. Известно {payload['session_usage']['input_tokens_known_sum']} input / {payload['session_usage']['output_tokens_known_sum']} output tokens; coverage {payload['session_usage']['input_usage_coverage_n']}/{payload['session_usage']['requests']} input и {payload['session_usage']['output_usage_coverage_n']}/{payload['session_usage']['requests']} output. Это нижняя известная сумма при пропущенных stats, не полный расход и не API billing.",
        '', 'Offload max означает запрос полной GPU загрузки; число фактически перенесённых layers CLI не раскрывает. Значение 0.75/0.55/0.70 означает requested fraction, а не измеренную долю VRAM. Файлы крупных моделей дополнительно используют RAM. Coder не завершил загрузку при 0.40 и 0.35; его inference/tokens NOT RUN.',
        '', 'Prompt/Predicted tokens сообщает LM Studio CLI. Reasoning tokens GPT-OSS входят в output и decode speed; их отдельное количество UNKNOWN. При ошибке без stats число tokens неизвестно. Старый диагностический run без stderr stats сохранён с null, а не пересчитан по символам.',
        '', f'CSV с полными колонками: `results/{directory.name}/all_text_models.csv`. Raw и все attempts связаны через `summary.json`.']
    (ROOT/'docs/LOCAL_MODEL_TOKEN_RESOURCE_TABLE_RU.md').write_text('\n'.join(tokens)+'\n',encoding='utf-8')
    print(directory)

if __name__=='__main__':
    report()

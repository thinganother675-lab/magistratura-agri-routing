"""Analyze saved development answers without inference or cloud calls."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import uuid
import numpy as np
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from agro_route.home_policy import offline, escalation_plan
from agro_route.home_stats import cluster_bootstrap_interval, paired_cluster_bootstrap, wilson_interval
from agro_route.evaluation import score
from agro_route.models import public_request
from agro_route.routing import hard_gate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('home_runner',ROOT/'scripts/home_pc_benchmark.py')
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def csv_write(path,records):
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)

def report(selected='gpt-oss-20b'):
    all_dirs=sorted(ROOT.glob('results/20261001_*_cli'))
    source={}
    for directory in all_dirs:
        manifest=read(directory/'manifest.json')
        if manifest['dataset_split']!='old_dev': continue
        for model,meta in manifest['models'].items():
            if model not in {m[0] for m in runner.CANDIDATES[:5]}|{'gemma-4-26b-a4b-it'}:
                continue
            # Exclude the known missing-stats and GPT reasoning-adapter diagnostics.
            if meta.get('summary') and meta['summary'].get('decode_tps_median') is not None:
                if model=='gpt-oss-20b' and meta['summary']['n']<12: continue
                if model not in source or meta['summary']['n']>=source[model][2]['summary']['n']:
                    source[model]=(directory,manifest,meta,rows(directory/(model+'_raw.jsonl')))
    if len(source)<5: raise RuntimeError('Expected five completed candidate development results')
    directory=ROOT/'results'/('20261001_home_analysis_'+uuid.uuid4().hex[:8]); directory.mkdir(exist_ok=False)
    common=set.intersection(*[{r['sample']['id'] for r in v[3]} for v in source.values()])
    table=[]; comparisons={}
    for model,(run,manifest,meta,data) in source.items():
        full=runner.summarize(data); same=runner.summarize([r for r in data if r['sample']['id'] in common])
        groups=[r['sample']['group'] for r in data]
        comparisons[model]={'source_run':run.name,'full':full,'common':same,
                           'mean_qa_f1':float(np.mean([r['score']['qa_f1'] for r in data if r['score']['qa_f1'] is not None])),
                           'quality_cluster_ci':cluster_bootstrap_interval([r['score']['correct'] for r in data],groups),
                           'quality_wilson_ci_descriptive':wilson_interval(full['correct'],full['n']),
                           'offload_requested':meta['requested_offload'],'resources':{k:meta[k] for k in ['vram_mib_peak_sampled_total','ram_gib_peak_sampled_system_used']},
                           'reasoning_rendered_cases':sum(r['local'].get('reasoning_rendered',False) for r in data),
                           'temperature':'UNKNOWN CLI defaults','max_tokens':'UNKNOWN CLI defaults'}
        table.append({'model':model,'n':full['n'],'correct':full['correct'],'quality':full['quality'],
                      'common_n':same['n'],'common_correct':same['correct'],'common_quality':same['quality'],
                      'p50_s':full['latency_p50_s'],'p95_s':full['latency_p95_s'],'decode_tps_median':full['decode_tps_median'],
                      'ttft_median_s':full['ttft_median_s'],'vram_mib_peak_total':meta['vram_mib_peak_sampled_total'],
                      'ram_gib_peak_system':meta['ram_gib_peak_sampled_system_used'],'errors':full['errors']})
    csv_write(directory/'model_comparison.csv',table)
    selected_rows=source[selected][3]
    offline_rows=[]; planned_cloud=0; tool_cloud=0
    for row in selected_rows:
        request=public_request(row['sample'])
        result=offline(request,lambda _:row['local'])
        traces=result.pop('trace'); result['latency_ms']+=sum(t['latency_ms'] for t in traces)
        result['latency_kind']='reconstructed_cli_trace_plus_gate' if traces else 'measured_tool_or_abstention_gate'
        offline_rows.append({'id':row['sample']['id'],'group':row['sample']['group'],'category':row['sample']['category'],
                             'language':row['sample']['language'],**result,**score(row['sample'],result['output'])})
        planned_cloud+=escalation_plan(request,row['local'])['cloud_calls_planned']
        tool_cloud+=int(hard_gate(request) is None)
    write(directory/'offline_dev.json',offline_rows)
    lat=[r['latency_ms']/1000 for r in offline_rows]
    offline_summary={'phase':'development replay; no final holdout','n':len(offline_rows),'correct':sum(r['correct'] for r in offline_rows),
                     'quality':np.mean([r['correct'] for r in offline_rows]).item(),'cloud_calls_actual':0,
                     'answer_count':sum(r['output']['action']=='ANSWER' for r in offline_rows),
                     'ask_for_data_count':sum(r['output']['action']=='ASK_FOR_DATA' for r in offline_rows),
                     'abstentions':sum(r['route']=='ABSTAIN' for r in offline_rows),
                     'local_calls_replayed':sum(r['local_calls'] for r in offline_rows),
                     'tool_calls':sum(r['tool_calls'] for r in offline_rows),
                     'latency_mean_reconstructed_s':float(np.mean(lat)),'latency_p50_reconstructed_s':float(np.quantile(lat,.5)),
                     'latency_p95_reconstructed_s':float(np.quantile(lat,.95)),
                     'correct_abstention_rate':None,'correct_abstention_note':'No gold ABSTAIN cases in this dev slice; rate not estimable',
                     'policy':'home_policy v2 skips local attempts without context; historical router unchanged'}
    paired={}
    for other in [m for m,v in source.items() if len(v[3])==len(selected_rows) and m!=selected]:
        other_by={r['sample']['id']:r for r in source[other][3]}
        assert {r['sample']['id'] for r in selected_rows}==set(other_by)
        paired[other]=paired_cluster_bootstrap([r['score']['correct'] for r in selected_rows],
                        [other_by[r['sample']['id']]['score']['correct'] for r in selected_rows],
                        [r['sample']['group'] for r in selected_rows])
    manual=[]
    for row in selected_rows[:30]:
        s=row['sample']; route=escalation_plan(public_request(s),row['local'])['route']
        gate=hard_gate(public_request(s))
        expected_route=gate['route'] if gate else 'LOCAL_OR_CLOUD' if s.get('context') else 'CLOUD'
        manual.append({'id':s['id'],'source':s['source'],'language':s['language'],'question':s['input'],
                       'context':s.get('context',''),'gold':json.dumps(s['expected'],ensure_ascii=False),
                       'inputs':json.dumps(s.get('inputs',{}),ensure_ascii=False),
                       'expected_route_under_draft_policy':expected_route,'route_planned':route,
                       'local_answer':json.dumps(row['local']['output'],ensure_ascii=False),
                       'cloud_answer':'NOT RUN','hybrid_answer':'NOT RUN',
                       'local_correct':row['score']['correct'],'hybrid_correct':'NOT RUN',
                       'notes':'DEV only; expected route follows draft eligibility, not a unique gold route; human review PENDING'})
    csv_write(directory/'manual_validation_DEV_30.csv',manual)
    bilingual=None; bilingual_models={}
    for run in all_dirs:
        manifest=read(run/'manifest.json')
        if manifest['dataset_split']=='custom_dev':
            for model in manifest['models']:
                data=rows(run/(model+'_raw.jsonl'))
                if len(data)!=12: continue
                pairs={}
                for r in data:
                    pairs.setdefault(r['sample']['group'],{})[r['sample']['language']]=r['score']['correct']
                bilingual_models[model]={'source_run':run.name,'summary':runner.summarize(data),'groups':len(pairs),
                    'scope':'six paired translated DEV QA cases; AI-assisted translations, independent human validation PENDING',
                    'counterbalanced_language_order':True,
                    'transitions':{'both_correct':sum(p['en'] and p['ru'] for p in pairs.values()),
                        'en_only':sum(p['en'] and not p['ru'] for p in pairs.values()),
                        'ru_only':sum(p['ru'] and not p['en'] for p in pairs.values()),
                        'neither':sum(not p['en'] and not p['ru'] for p in pairs.values())},
                    'language_latency':{lang:runner.summarize([r for r in data if r['sample']['language']==lang]) for lang in ['en','ru']},
                    'language_qa_f1':{lang:float(np.mean([r['score']['qa_f1'] or 0 for r in data if r['sample']['language']==lang])) for lang in ['en','ru']}}
    bilingual=bilingual_models.get(selected)
    analysis={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'DEVELOPMENT_ONLY',
              'selected_context_reader_provisional':selected,'selection_reason':'Provisional context reader from DEV; CLI instability, bilingual QA and generation controls require API revalidation. Final model selection PENDING.',
              'common_candidate_sample_n':len(common),'models':comparisons,'paired_selected_minus_other':paired,
              'offline':offline_summary,'bilingual':bilingual,'bilingual_models':bilingual_models,
              'escalation_plan_dev':{'n':len(selected_rows),'tools_cloud_planned':tool_cloud,'hybrid_cloud_planned':planned_cloud,
                                     'reduction_absolute_pp':100*(tool_cloud-planned_cloud)/len(selected_rows),
                                     'reduction_relative':(tool_cloud-planned_cloud)/tool_cloud,'cloud_calls_actual':0,
                                     'warning':'Routing plan from measured local answers; cloud correctness/cost/latency NOT RUN'},
              'final_holdout':{'status':'NOT RUN','selected_n':0,'target_n':150,'protocol_frozen':False},
              'cloud_cost_actual_new_runs_usd':0.,'cloud_comparison_quality_latency_cost':None,
              'historical_main_test_used_for_tuning':False,'historical_results_unchanged':True}
    write(directory/'analysis.json',analysis)
    fig,ax=plt.subplots(figsize=(7.2,4.5))
    for model,value in comparisons.items():
        if value['full']['n']!=36: continue
        x=value['full']['latency_p50_s']; y=100*value['full']['quality']
        ax.scatter(x,y,s=70); ax.annotate(model,(x,y),xytext=(7,5),textcoords='offset points',fontsize=9)
    ax.set(xlabel='Median CLI end-to-end latency (s)',ylabel='Strict task correctness (%)',
           title='HOME PC development comparison, same 36 cases\nCLI defaults unverified; this is not a final holdout',xlim=(.9,5.1),ylim=(40,90))
    ax.grid(alpha=.25); fig.tight_layout()
    for ext in ['png','svg']: fig.savefig(directory/('dev_quality_latency.'+ext),dpi=180)
    plt.close(fig)
    lines=['# Сравнение локальных моделей HOME PC','',
           '01.10.2026. Только development: старый test90 не использован для выбора модели. Основные generative кандидаты были установлены до сессии. Полный inventory smoke и отдельный typed decision аналог Jev документируются отдельно.',
           '',f'Основной machine-readable анализ: `results/{directory.name}/analysis.json`. Raw и ресурсы сохраняются в отдельных timestamped CLI runs.',
           '', '## Сопоставимый общий smoke-срез', '',
           '| Модель | Common correct/n | Quality | N расширенного dev | Correct в расширенном dev | p50 / p95 s | Decode tok/s | TTFT s | VRAM total MiB | RAM system GiB | Ошибки |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for t in table:
        lines.append(f"| {t['model']} | {t['common_correct']}/{t['common_n']} | {t['common_quality']:.1%} | {t['n']} | {t['correct']}/{t['n']} | {t['p50_s']:.3f} / {t['p95_s']:.3f} | {t['decode_tps_median']:.2f} | {t['ttft_median_s']:.3f} | {t['vram_mib_peak_total']:.0f} | {t['ram_gib_peak_system']:.2f} | {t['errors']} |")
    lines+=['','## Категории на одном DEV36','','| Модель | Compound | QA | Missing | Numeric | Rule | Tool selection | QA mean F1 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for model,value in comparisons.items():
        if value['full']['n']!=36: continue
        counts=[value['full']['by_category'][cat] for cat in ['compound_reasoning','extractive_qa','missing_data','numeric','rule_interpretation','tool_selection']]
        lines.append('| '+model+' | '+' | '.join(f"{c['correct']}/{c['n']}" for c in counts)+f" | {value['mean_qa_f1']:.3f} |")
    lines+=['', 'Расширенное N различается: Qwen9/Gemma12 остановлены после четырёх format failures на 12 примерах. Их нельзя ранжировать против full36 по несопоставимым долям. Common12 одинаков для основных кандидатов; сравнение full36 парное.',
            '', '## Интерпретация', '',
            f'Для отдельного offline/replay анализа выбран предварительный context reader {selected}. Окончательный выбор требует controlled HTTP DEV и парного языкового аудита. GPT-OSS получил 6/6 EN QA в первом full36, но повтор EN дал 4/6. Qwen3.8 27B — стабильный dense comparator с 0 CLI/parser errors на full36 и частичным offload75%. Qwen35-A3B при offload55% быстрее27B, но слабее на full36. Family, quantization, reasoning и offload различаются; причинное преимущество архитектуры не устанавливается.',
            '', 'GPT-OSS визуально возвращает reasoning несмотря на requested off; decode speed включает reasoning tokens. Поэтому106tok/s не означает меньшую end-to-end задержку. Три GPT CLI failures не исчезают из качества/ошибок. Первая попытка6 была остановлена из-за неподдержанной раздельной передачи reasoning/final; raw сохранён, но она исключена из model ranking.',
            '', 'Qwen9/Gemma форматные ошибки могут быть свойством текущего adapter/settings. Нельзя объявлять сами веса непригодными без JSON-schema HTTP pilot. Temperature/max_tokens CLI не проверены. Structured JSON по prompt протестирован; grammar-constrained JSON, native function calls и logprobs через HTTP NOT RUN.',
            '', 'Peak VRAM — sampled total device allocation, RAM — total system use; это не per-model memory. Частота примерно0.5s плюс subprocess overhead, точный максимум мог быть пропущен. GPU layers как фактическое число не доступны: сохранён requested ratio и loaded context4096/parallel1. Prompt-processing speed отдельно не предоставлен CLI.',
            '', '## Вклад локального reader и offline на DEV', '',
            f"Сохранённые ответы дают routing plan tools+cloud {tool_cloud}/36 → tools+local+cloud {planned_cloud}/36: {(tool_cloud-planned_cloud)/tool_cloud:.1%} относительного сокращения, {100*(tool_cloud-planned_cloud)/36:.2f} п.п. от всех запросов. Это ожидаемые эскалации, а не выполненные cloud calls; качество и latency пары с облаком NOT RUN.",
            '', f"Offline v2: {offline_summary['correct']}/36 ({offline_summary['quality']:.1%}), answers {offline_summary['answer_count']}, ASK_FOR_DATA {offline_summary['ask_for_data_count']}, ABSTAIN {offline_summary['abstentions']}; cloud0, local traces{offline_summary['local_calls_replayed']}, tools{offline_summary['tool_calls']}. Mean/p50/p95 reconstructed {np.mean(lat):.3f}/{np.quantile(lat,.5):.3f}/{np.quantile(lat,.95):.3f}s. Это cached trace replay, не live benchmark каждой политики.",
            '', 'Доля правильных abstentions не оценивается: gold ABSTAIN здесь отсутствует. Coverage нужно различать: ответы, уточнения и безопасные отказы. Строгий EM не заменяет агрономическую экспертизу. ManualDEV30.csv содержит только dev и пустые cloud/hybrid NOT RUN.',
            '', '## Русский язык', '',
            'В full36 — RU15 controlled и EN21, включая EN6 QA. Эти неодинаковые составы нельзя интерпретировать как причинный языковой эффект. Отдельный paired QA probe имеет шесть source groups, перевод AI-assisted и human validation PENDING; он также dev.',
            '', '## Ограничение финального вывода', '',
            'Новый независимый holdout NOT RUN. Окончательное подтверждение гипотезы, качество tools+cloud/hybrid, latency difference и реальные API cost differences не получены. Нужны controlled API revalidation, один fixed cloud baseline, новая независимая выборка и реальная фиксация протокола до её запуска.']
    if bilingual:
        b=bilingual['summary']; lines+=['',f"Paired dev QA: EN {b['by_language']['en']['correct']}/6; RU {b['by_language']['ru']['correct']}/6; overall {b['correct']}/12. Вывод только описательный, n_groups6."]
    if bilingual_models:
        lines+=['','| Парный DEV QA | EN correct/6 | RU correct/6 | p50 / p95 s | Errors |','|---|---:|---:|---:|---:|']
        for model,value in bilingual_models.items():
            b=value['summary']; lines.append(f"| {model} | {b['by_language']['en']['correct']}/6 | {b['by_language']['ru']['correct']}/6 | {b['latency_p50_s']:.3f} / {b['latency_p95_s']:.3f} | {b['errors']} |")
        lines+=['','Gemma 26B и Qwen 27B имеют одинаковый aggregate score на этом малом paired probe; Gemma быстрее. Это обосновывает предварительный выбор reader, но не доказывает equivalence или устойчивую русскоязычную generalization.']
    (ROOT/'docs/LOCAL_MODEL_COMPARISON_RU.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(directory)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--selected-model',default='gpt-oss-20b')
    args=parser.parse_args(); report(args.selected_model)

"""Append-only descriptive analysis of fresh pre-routing DEV traces."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,collections,csv,hashlib,json,statistics,uuid
import numpy as np
from agro_route.home_stats import paired_cluster_bootstrap
from agro_route.evaluation import score

METHODS=['tool_cloud','cascade','rule_first','jev_first','laya_first','offline_laya']
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and np.isfinite(x) and x>=0
def distribution(values):
    values=[float(x) for x in values if finite(x)]
    return {'n':len(values),'mean':statistics.mean(values) if values else None,
            'p50':statistics.median(values) if values else None,
            'p95':float(np.quantile(values,.95)) if values else None}
def tokens(traces):
    report={}
    for field in ('prompt_tokens','completion_tokens','total_tokens','input_tokens','output_tokens'):
        values=[t.get('usage',{}).get(field) for t in traces]
        report[field]={'known_total':sum(v for v in values if finite(v)),
                       'coverage':sum(finite(v) for v in values),'attempts':len(values)}
    return report
def summarize(rows,n):
    results=[r['result'] for r in rows]
    correct=sum(r['score']['correct'] for r in rows)
    local=[t for r in results for t in r.get('trace',[]) if t['provider']=='local' and t.get('attempted',True)]
    cloud=[t for r in results for t in r.get('trace',[]) if t['provider']=='cloud' and t.get('attempted',True)]
    router=[r['router_trace'] for r in results if r.get('router_trace')]
    jev=[t.get('raw') or {} for t in router if t.get('router_external_calls')]
    laya=[t['component_metadata'] for t in router if t.get('component_metadata')]
    costs=[r.get('cost_usd') for r in results]
    known=sum(r.get('known_remote_cost_usd',r.get('cost_usd') or 0.) for r in results)
    unknown=sum(r.get('unknown_cost_events',sum(not finite(t.get('cost_usd')) for t in r.get('trace',[]))) for r in results)
    answered=sum((r.get('output') or {}).get('action')=='ANSWER' for r in results)
    unsupported=sum((r.get('output') or {}).get('action')=='ANSWER' and not row['score']['correct'] for row,r in zip(rows,results))
    return {'intended_n':n,'recorded_n':len(rows),'missing_n':n-len(rows),'correct':correct,'quality_intended':correct/n,
            'measured_n':sum(r.get('status')=='MEASURED' for r in results),'not_run_n':sum(r.get('status')=='NOT_RUN' for r in results),
            'errors':sum(bool(r.get('error')) for r in results),'router_errors':sum(bool(t.get('error')) for t in router),
            'routes':dict(collections.Counter(r.get('route') for r in results)),
            'proposed_routes':dict(collections.Counter(r.get('proposed_route') for r in results if r.get('proposed_route'))),
            'guard_overrides':dict(collections.Counter(r.get('guard_override') for r in results if r.get('guard_override'))),
            'local_calls':sum(r.get('local_calls',0) for r in results),'generative_cloud_calls':sum(r.get('cloud_calls',0) for r in results),
            'hosted_router_calls':sum(r.get('router_external_calls',0) for r in results),
            'total_external_requests':sum(r.get('total_external_requests',r.get('cloud_calls',0)) for r in results),
            'tool_calls':sum(r.get('tool_calls',0) for r in results),'verification_external_calls':0,'retries':0,
            'latency_s':distribution([r['latency_ms']/1000 for r in results]),
            'latency_scope':'All journaled pipeline decisions, including blocked and failed results; same operational scope across arms',
            'successful_latency_s':distribution([r['latency_ms']/1000 for r in results if not r.get('error') and r.get('status')=='MEASURED' and isinstance(r.get('output'),dict)]),
            'blocked_before_dispatch_decisions':sum(bool(r.get('blocked_reason')) or any(t.get('attempted') is False for t in r.get('trace',[])) for r in results),
            'router_latency_ms':distribution([r.get('router_latency_ms') for r in results]),
            'known_remote_cost_usd':known,'unknown_cost_events':unknown,'cost_complete':unknown==0 and len(rows)==n,
            'known_cost_per_intended_request_usd':known/n,'known_cost_per_success_usd':known/correct if correct else None,
            'known_cost_per_completed_decision_usd':known/len(rows) if rows else None,
            'completed_decision_definition':'Journaled policy result; provider failures remain in this operational denominator',
            'cloud_provider_errors':sum(bool(t.get('error')) for t in cloud),
            'cloud_provider_failure_rate':sum(bool(t.get('error')) for t in cloud)/len(cloud) if cloud else None,
            'local_provider_errors':sum(bool(t.get('error')) for t in local),
            'answer_coverage':answered/n,'incorrect_answer_rate_intended':unsupported/n,
            'unsupported_answer_proxy_note':'Wrong scored ANSWER, not an independently human-audited hallucination metric',
            'clarifications':sum((r.get('output') or {}).get('action')=='ASK_FOR_DATA' for r in results),
            'abstentions':sum((r.get('output') or {}).get('action')=='ABSTAIN' for r in results),
            'gold_abstention_n':sum(row['sample']['expected']['action']=='ABSTAIN' for row in rows),
            'correct_abstention':'NOT_IDENTIFIABLE' if not any(row['sample']['expected']['action']=='ABSTAIN' for row in rows) else sum(row['sample']['expected']['action']=='ABSTAIN' and row['score']['correct'] for row in rows),
            'local_tokens':tokens(local),'cloud_tokens':tokens(cloud),'hosted_router_tokens':tokens(jev),
            'local_client_ttft_s':distribution([t.get('timing',{}).get('first_nonempty_delta_s_client') for t in local]),
            'local_client_tps_approx':distribution([t.get('timing',{}).get('completion_tokens_per_second_client_approx') for t in local]),
            'local_backend_tps':distribution([t.get('timing',{}).get('backend_tokens_per_second') for t in local]),
            'laya_cpu_rss_peak_bytes':max((t.get('rss_bytes',0) for t in laya),default=None),
            'laya_truncation_records':[t.get('truncation_metadata') for t in laya],
            'by_category':{k:{'n':len(s),'correct':sum(r['score']['correct'] for r in s)} for k in sorted({r['sample']['category'] for r in rows}) if (s:=[r for r in rows if r['sample']['category']==k])},
            'by_language':{k:{'n':len(s),'correct':sum(r['score']['correct'] for r in s)} for k in sorted({r['sample']['language'] for r in rows}) if (s:=[r for r in rows if r['sample']['language']==k])}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];run=args.run.resolve()
    if not run.is_relative_to((root/'results').resolve()):raise ValueError('Run outside results')
    protocol=json.loads((run/'protocol.json').read_text(encoding='utf-8'))
    samples=json.loads((run/'samples_dev.json').read_text(encoding='utf-8'))
    rows=[json.loads(l) for l in (run/'raw_decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    snapshot={s['id']:s for s in samples}
    canonical=json.dumps(samples,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if hashlib.sha256(canonical.encode('utf-8')).hexdigest()!=protocol['samples_canonical_sha256']:raise ValueError('Modified sample snapshot')
    if protocol['ids']!=[s['id'] for s in samples] or protocol['methods']!=METHODS:raise ValueError('Protocol IDs/methods mismatch')
    if hashlib.sha256((root/'src/agro_route/evaluation.py').read_bytes()).hexdigest()!=protocol['scoring_sha256']:raise ValueError('Scorer changed; use versioned reanalysis instead')
    for r in rows:
        if r['method'] not in METHODS or r['sample']['id'] not in snapshot or r['sample']!=snapshot[r['sample']['id']]:raise ValueError('Unexpected method or changed embedded sample')
        if score(r['sample'],r['result']['output'])!=r['score']:raise ValueError('Stored score differs from frozen scorer')
    if len({(r['sample']['id'],r['method']) for r in rows})!=len(rows):raise ValueError('Duplicated pair')
    if any(r['sample']['split']!='dev' for r in rows):raise ValueError('Only DEV permitted')
    out=run/('analysis_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);out.mkdir()
    summaries={m:summarize([r for r in rows if r['method']==m],len(samples)) for m in METHODS}
    pairs={};lookup={(r['sample']['id'],r['method']):r for r in rows}
    for a,b in [('jev_first','rule_first'),('laya_first','rule_first'),('rule_first','cascade'),('jev_first','cascade'),('laya_first','cascade')]:
        if not all((s['id'],a) in lookup and (s['id'],b) in lookup for s in samples):
            pairs[a+'-minus-'+b]={'status':'PARTIAL_NO_PAIRED_INTERVAL'};continue
        av=[lookup[s['id'],a]['score']['correct'] for s in samples];bv=[lookup[s['id'],b]['score']['correct'] for s in samples]
        pairs[a+'-minus-'+b]=paired_cluster_bootstrap(av,bv,[s['group'] for s in samples],seed=20261002)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'phase':'EXPLORATORY_DEV_NOT_CONFIRMATORY',
            'run':str(run.relative_to(root)),'raw_sha256':hashlib.sha256((run/'raw_decisions.jsonl').read_bytes()).hexdigest(),
            'protocol_sha256':hashlib.sha256((run/'protocol.json').read_bytes()).hexdigest(),
            'n':len(samples),'source_groups':len({s['group'] for s in samples}),'human_review':False,
            'methods':summaries,'paired_quality':pairs,
            'interpretation_limits':['Observed DEV; no new confirmatory holdout','Lexical ambiguity guard added only to pre-routing arms: extra factor versus historical cascade',
                                     'Strict extractive scoring may reject semantically equivalent text','Weak literal support verifier retained in historical cascade',
                                     'RU agricultural QA absent from original DEV sample; overall EN/RU is confounded by category mix',
                                     'Laya confidence uncalibrated; inspect actual truncation','Invoice and ownership of cloud billing accounts UNKNOWN']}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    with (out/'policies.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['method','correct','n','quality','mean_s','p50_s','p95_s','local_calls','generative_cloud_calls','hosted_router_calls','total_external_requests','known_cost_usd','unknown_cost_events','errors'])
        for m,s in summaries.items():writer.writerow([m,s['correct'],s['intended_n'],s['quality_intended'],s['latency_s']['mean'],s['latency_s']['p50'],s['latency_s']['p95'],s['local_calls'],s['generative_cloud_calls'],s['hosted_router_calls'],s['total_external_requests'],s['known_remote_cost_usd'],s['unknown_cost_events'],s['errors']])
    (out/'analysis_source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'analysis':str(out.relative_to(root)),'methods':{m:{k:s[k] for k in ['correct','intended_n','generative_cloud_calls','hosted_router_calls','total_external_requests','known_remote_cost_usd','unknown_cost_events','latency_s']} for m,s in summaries.items()}},ensure_ascii=True,indent=2))
if __name__=='__main__':main()

import collections
import csv
import json
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".cache/matplotlib"))
import numpy as np
from scipy.stats import binomtest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .benchmark import write_json
from .evaluation import score

def cluster_interval(rows, values, repeats=2000):
    groups = sorted({r["group"] for r in rows})
    clusters = [np.array([v for r,v in zip(rows,values) if r["group"]==g],dtype=float) for g in groups]
    rng = np.random.default_rng(42)
    stats = [np.concatenate([clusters[i] for i in rng.integers(0,len(groups),len(groups))]).mean() for _ in range(repeats)]
    return [float(x) for x in np.quantile(stats,[.025,.975])]

def analyze(directory):
    directory=Path(directory)
    if (directory/"analysis.json").exists():
        raise RuntimeError("Analysis already exists; preserve completed report")
    rows=[json.loads(l) for l in (directory/"normalized.jsonl").read_text(encoding="utf-8").splitlines()]
    report={"latency_kind":"reconstructed_trace_replay for model methods; measured tools", "summary":[],"category":[],"language":[],"paired":{}}
    methods=list(dict.fromkeys(r["method"] for r in rows))
    for method in methods:
        subset=[r for r in rows if r["method"]==method]
        quality=float(np.mean([r["correct"] for r in subset]))
        costs=[r["cost_usd"] for r in subset]
        latencies=[r["latency_ms"] for r in subset]
        answered=[r for r in subset if r["output"] and r["output"].get("action")=="ANSWER"]
        qa=[r["qa_f1"] for r in subset if r["qa_f1"] is not None]
        summary={"method":method,"n":len(subset),"quality":quality,"quality_ci95":cluster_interval(subset,[r["correct"] for r in subset]),"cloud_call_rate":float(np.mean([r["cloud_calls"] for r in subset])),"local_model_call_rate":float(np.mean([r["local_calls"] for r in subset])),"tool_call_rate":float(np.mean([r["tool_calls"] for r in subset])),"latency_mean_ms":float(np.mean(latencies)),"latency_p50_ms":float(np.quantile(latencies,.5)),"latency_p95_ms":float(np.quantile(latencies,.95)),"cost_total_usd":sum(c for c in costs if c is not None),"unknown_cost_requests":sum(c is None for c in costs),"cost_per_1000_usd":None if any(c is None for c in costs) else sum(costs)/len(costs)*1000,"coverage_answer":len(answered)/len(subset),"selective_error_rate":sum(not r["correct"] for r in answered)/len(answered) if answered else None,"critical_error_rate":float(np.mean([r["critical_error"] for r in subset])),"qa_token_f1":float(np.mean(qa)) if qa else None,"route_counts":dict(collections.Counter(r["route"] for r in subset))}
        report["summary"].append(summary)
        summary['local_resolution_rate']=sum(r['route']=='LOCAL_MODEL' for r in subset)/len(subset)
        summary['non_cloud_completion_rate']=sum(r['cloud_calls']==0 for r in subset)/len(subset)
        summary['correct_local_resolution_rate']=sum(r['route']=='LOCAL_MODEL' and r['correct'] for r in subset)/len(subset)
        summary['numeric_mae_when_present']=float(np.mean([r['numeric_error'] for r in subset if r['numeric_error'] is not None])) if any(r['numeric_error'] is not None for r in subset) else None
        for key in ("category","language"):
            for value in sorted({r[key] for r in subset}):
                group=[r for r in subset if r[key]==value]
                report[key].append({"method":method,key:value,"n":len(group),"quality":sum(r["correct"] for r in group)/len(group),"cloud_call_rate":sum(r["cloud_calls"] for r in group)/len(group),"critical_error_rate":sum(r["critical_error"] for r in group)/len(group)})
    baseline={r["id"]:r for r in rows if r["method"]=="cloud"}
    for method in methods:
        if method=="cloud":continue
        sub=[r for r in rows if r["method"]==method]
        diff=[int(r["correct"])-int(baseline[r["id"]]["correct"]) for r in sub]
        critical=[int(r["critical_error"])-int(baseline[r["id"]]["critical_error"]) for r in sub]
        win=sum(v==1 for v in diff);loss=sum(v==-1 for v in diff)
        report["paired"][method]={"quality_difference":float(np.mean(diff)),"difference_ci95":cluster_interval(sub,diff),"critical_difference_ci95":cluster_interval(sub,critical),"wins":win,"losses":loss,"mcnemar_exact_p":float(binomtest(win,win+loss,.5).pvalue) if win+loss else 1.,"mcnemar_limitation":"descriptive unadjusted; correlated synthetic variants violate independent-pair assumption; cluster-bootstrap primary"}
    root=Path(__file__).resolve().parents[2]
    tool_baseline={r['id']:r for r in rows if r['method']=='tool_cloud'}
    cascade_rows=[r for r in rows if r['method']=='cascade']
    h2_diff=[int(r['correct'])-int(tool_baseline[r['id']]['correct']) for r in cascade_rows]
    h2_calls=[tool_baseline[r['id']]['cloud_calls']-r['cloud_calls'] for r in cascade_rows]
    report['local_contribution_vs_tool_cloud']={'quality_difference':float(np.mean(h2_diff)), 'quality_difference_ci95':cluster_interval(cascade_rows,h2_diff),'additional_cloud_call_reduction':float(np.mean(h2_calls)), 'call_reduction_ci95':cluster_interval(cascade_rows,h2_calls),'supported':bool(np.mean(h2_calls)>0 and cluster_interval(cascade_rows,h2_diff)[0]>=-.05),'note':'Isolates local LLM contribution; tools alone cannot support H2.'}
    frozen=root/"data/protocol_frozen.json"
    if frozen.exists():
        protocol=json.loads(frozen.read_text())
        primary=protocol["primary_method"]
        metric=next(r for r in report["summary"] if r["method"]==primary)
        pair=report["paired"][primary]
        checks={"quality_noninferiority":pair["difference_ci95"][0]>=-protocol["quality_margin_absolute"],"cloud_call_reduction":1-metric["cloud_call_rate"]>=protocol["min_cloud_call_reduction"],"critical_errors":pair["critical_difference_ci95"][1]<=protocol["critical_error_margin_absolute"]}
        report["hypothesis"]={"checks":checks,"supported_on_this_controlled_sample":all(checks.values()),"publication_claim":"exploratory only; no generalization to real agronomists or frontier APIs"}
    pairs=[json.loads(l) for l in (directory/"pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    report['tool_selection_confusion']={method:dict(collections.Counter((next(p['sample']['expected']['answers'][0] for p in pairs if p['sample']['id']==r['id'])+' -> '+(r['output'].get('answer','').strip().lower() if r['output'] else '<no_output>')) for r in rows if r['method']==method and r['category']=='tool_selection')) for method in methods}
    report['model_reliability']={name:{'error_calls':sum(bool(p[name]['error']) for p in pairs),'prompt_tokens':sum(p[name]['usage'].get('prompt_tokens',0) for p in pairs),'completion_tokens':sum(p[name]['usage'].get('completion_tokens',0) for p in pairs)} for name in ('local','cloud')}
    oracle=sum(score(p["sample"],p["local"]["output"])["correct"] or score(p["sample"],p["cloud"]["output"])["correct"] for p in pairs)/len(pairs)
    report["language_pair_oracle_quality"]=oracle
    report["oracle_note"]="Gold-informed local/cloud upper bound without tools; not an executable router and not equal access to tool policies"
    write_json(directory/"analysis.json",report)
    fields=["method","n","quality","cloud_call_rate","tool_call_rate","latency_mean_ms","latency_p50_ms","latency_p95_ms","cost_per_1000_usd","critical_error_rate","qa_token_f1"]
    with (directory/"summary.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(report["summary"])
    fig,axes=plt.subplots(1,2,figsize=(11,4.2))
    for row in report["summary"]:
        if row["cost_per_1000_usd"] is not None:
            axes[0].scatter(row["cost_per_1000_usd"],row["quality"]*100,label=row["method"])
            axes[0].annotate(row["method"],(row["cost_per_1000_usd"],row["quality"]*100),xytext=(4,4),textcoords="offset points",fontsize=8)
    axes[0].set(xlabel="Cloud USD per 1000 requests (token estimate)",ylabel="Exact end-to-end correctness (%)",ylim=(-3,105))
    axes[1].bar([r["method"] for r in report["summary"]],[r["latency_p95_ms"]/1000 for r in report["summary"]],color="#276955")
    axes[1].set(xlabel="Policy (trace replay)",ylabel="Reconstructed p95 latency (seconds)")
    axes[1].tick_params(axis="x",rotation=35)
    fig.suptitle(f"{directory.name}: controlled agricultural routing experiment")
    fig.tight_layout();fig.savefig(directory/"quality_cost_latency.png",dpi=180);fig.savefig(directory/"quality_cost_latency.jpg",dpi=180);fig.savefig(directory/"quality_cost_latency.svg");plt.close(fig)
    return report

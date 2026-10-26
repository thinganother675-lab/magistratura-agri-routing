# SPDX-License-Identifier: Apache-2.0
"""Independent V2 receipt audit and safe append-only final systems tables.

Preserves the failed V1 and original V2 summaries; no new model calls. Study C
Qwen9/deterministic responses are explicitly reused from V1; Qwen27 is V2.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from agro_route.deterministic_study_20261003 import public_request
from agro_route.lm_telemetry_20261003 import safe_record
from agro_route.resource_analysis_20261003 import distribution
from agro_route.study_c_aggregate_20261003 import aggregate

RUN = "20261003_systems_checkpoint0_v2"
KEYS = ("qwen3.5-9b", "qwen3.8-27b")


def read(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def journal(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f: json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")


def csv_write(path, rows):
    with path.open("x",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def archive_sources(plan):
    out=ROOT/"experiments/system_telemetry_v2_code";out.mkdir(exist_ok=False)
    names=list(plan["source_code_sha256"])+["src/agro_route/deterministic_study_20261003.py","src/agro_route/study_c_aggregate_20261003.py",Path(__file__).relative_to(ROOT).as_posix()]
    files={}
    for name in names:
        data=(ROOT/name).read_bytes();sha=hashlib.sha256(data).hexdigest()
        if name in plan["source_code_sha256"] and sha!=plan["source_code_sha256"][name]:raise ValueError("V2 executed source hash differs")
        target=out/(name.replace("/","__")+".txt");target.write_bytes(data)
        files[name]={"snapshot_path":target.relative_to(ROOT).as_posix(),"sha256":sha,"plan_recorded":name in plan["source_code_sha256"]}
    manifest={"status":"IMMUTABLE_EXECUTED_V2_AND_ANALYSIS_SOURCE_ARCHIVE","run_id":RUN,"files":files,
              "protocol_path":f"results/{RUN}/protocol_frozen.json","protocol_sha256":digest(ROOT/f"results/{RUN}/protocol_frozen.json")}
    write(out/"manifest.json",manifest)
    return out/"manifest.json"


def integrity(plan, receipt, records, metrics, loads, cases, scores):
    expected=[]
    for assignment in plan["assignment_order"]:
        model,block=assignment["model_key"],assignment["block"]
        expected.append((model,block,"warmup","synthetic_warmup"))
        expected += [(model,block,"telemetry",i) for i in plan["blocks"][block]]
        if model==KEYS[1]:expected += [(model,block,"study_c",i) for i in plan["study_c_case_blocks"][block]]
    previous=ROOT/"results"/plan["parent_run"]
    prior={ (r["model_key"],r["id"]):r for r in journal(previous/"study_c_scores.jsonl") }
    historical={m:{r["item_id"]:r for r in journal(ROOT/f"results/20261003_local_screen_571682f5/dev293/{m}_metrics.jsonl")} for m in KEYS}
    source_reuse=True
    for row in scores:
        if row["model_key"] in {KEYS[0],"deterministic_tools"}:
            source_reuse &= row.get("source_run")==plan["parent_run"] and {k:v for k,v in row.items() if k!="source_run"}==prior[(row["model_key"],row["id"])]
        else:source_reuse &= row.get("source_run")==RUN
    return {
        "executed_code_hashes_match":all(digest(ROOT/name)==sha for name,sha in plan["source_code_sha256"].items()),
        "raw_hash_matches_completion":digest(ROOT/f".runtime/mera/{RUN}/raw.jsonl")==receipt["raw_sha256"],
        "safe_hash_matches_completion":digest(ROOT/f"results/{RUN}/inference_metrics.jsonl")==receipt["inference_metrics_sha256"],
        "parent_protocol_hash_matches":digest(previous/"protocol_frozen.json")==plan["parent_plan_sha256"],
        "study_pack_hash_matches":digest(ROOT/"data/study_c_technical_20261003.json")==plan["study_c_sha256"],
        "source_reuse_is_exact_and_labelled":bool(source_reuse),
        "safe_projection_matches_raw":metrics==[safe_record(r) for r in records],
        "ordered_attempts_match_plan":[(r["model_key"],r["block"],r["kind"],r["task_id"]) for r in records]==expected,
        "no_duplicate_attempts":len(expected)==len(set(expected)),
        "both_telemetry_models_complete_40":all(sum(r["kind"]=="telemetry" and r["model_key"]==m and r.get("stream_complete") is True and not r["error"] for r in records)==40 for m in KEYS),
        "all_new_study_q27_complete_27":sum(r["kind"]=="study_c" and r["model_key"]==KEYS[1] and r.get("stream_complete") is True and not r["error"] for r in records)==27,
        "no_new_q9_study_calls":not any(r["kind"]=="study_c" and r["model_key"]==KEYS[0] for r in records),
        "no_tools_or_history":all(r["request"]["integrations"]==[] and r["request"]["store"] is False and "previous_response_id" not in r["request"] for r in records),
        "no_tool_response_events":not any(e["data"]["type"].startswith("tool_call.") for r in records for e in r["events"]),
        "reasoning_disabled_unobserved":all(r["request"]["reasoning"]=="off" and not r["reasoning_text"] and not r["stats"]["reasoning_output_tokens"] for r in records),
        "study_gold_not_in_prompts":all(json.loads(r["request"]["input"])==public_request(cases[r["task_id"]]) for r in records if r["kind"]=="study_c"),
        "historical_mera_prompts_match":all(r["prompt_sha256"]==historical[r["model_key"]][r["task_id"]]["prompt_sha256"] for r in records if r["kind"]=="telemetry"),
        "request_hashes_match":all(hashlib.sha256(json.dumps(r["request"],ensure_ascii=False,sort_keys=True).encode()).hexdigest()==r["request_sha256"] for r in records),
        "prompt_bytes_hash_match":all(hashlib.sha256(r["request"]["input"].encode()).hexdigest()==r["prompt_sha256"] and len(r["request"]["input"].encode())==r["prompt_bytes"] for r in records),
        "system_hashes_match":all(hashlib.sha256(r["request"]["system_prompt"].encode()).hexdigest()==plan["prompt_hashes"]["study_c_system" if r["kind"]=="study_c" else "mera_system"] for r in records),
        "returned_instance_matches_request":all(r["result"]["model_instance_id"]==r["request"]["model"] for r in records),
        "checkpoint_zero_parallel_one_mtp_off_confirmed":all(r["config"]["context_checkpoints"]==0 and r["config"]["parallel"]==1 and r["config"]["context_length"]==2048 and r["config"]["speculative_draft_mtp"] is False for r in loads),
        "all_own_models_unloaded":all(r["unload_success"] for r in loads) and receipt["models_unloaded"] is True,
        "timing_nonnegative_http_bounded":all(v is None or 0<=v<=r["latency_s"]+1e-6 for r in records for k,v in r["timing"].items() if k.endswith("_s")),
        "all_samples_above_guards":all(r["resources"]["system_ram_available_gib_min_sampled"]>=2 and r["resources"]["gpu_memory_free_mib_min_sampled"]>=512 and not r["resource_errors"] for r in records),
        "no_energy_allocation_or_eos_inference":all(r["resources"]["energy_j"] is None and "NOT per-model allocation" in r["resources"]["scope"] and r["finish_reason"] is None for r in records),
        "no_private_test_or_paid_api":plan["private_test_run"] is receipt["private_test_run"] is False and plan["paid_api_calls"]==receipt["paid_api_calls"]==0,
    }


def systems_model(model, records, loads, historical):
    own=[r for r in records if r["model_key"]==model and r["kind"]=="telemetry"]
    all_own=[r for r in records if r["model_key"]==model]
    mine=[r for r in loads if r["model_key"]==model]
    resources={}
    for name in ["gpu_memory_used_mib","system_ram_used_gib","lmstudio_process_group_rss_mib"]:
        unit="GiB" if name=="system_ram_used_gib" else "MiB"
        resources[name+"_request_peaks"]=distribution([r["resources"][name+"_peak_sampled"] for r in own],unit=unit)
        resources[name+"_all_requests_max"]=max(r["resources"][name+"_peak_sampled"] for r in all_own)
    return {
        "model_key":model,"systems_run_id":RUN,"systems_status":"SYSTEMS_TELEMETRY","quality_run_id":historical["historical_run_id"],"quality_status":"DEV",
        "quality":historical["models"][model]["quality"], "exact_weight":historical["models"][model]["resources"],
        "n":len(own),"errors":sum(bool(r["error"]) for r in own),"json_parse_invalid":sum(not r["parse_success"] for r in own),
        "latency_s":distribution([r["latency_s"] for r in own],unit="s"),
        "client_ttft_s":distribution([r["timing"]["client_ttft_answer_s"] for r in own],unit="s"),
        "backend_ttft_s":distribution([r["stats"]["time_to_first_token_seconds"] for r in own],unit="s"),
        "backend_tokens_per_second":distribution([r["stats"]["tokens_per_second"] for r in own],unit="tokens/s"),
        "client_prompt_token_equivalent_tps":distribution([r["timing"]["client_prompt_token_equivalent_tps"] for r in own],unit="tokens/s"),
        "resources":resources,
        "load_samples_s":[r["load_latency_s"] for r in mine],"backend_load_samples_s":[r.get("backend_load_time_s") for r in mine],
        "warmup_samples_s":[r["warmup_latency_s"] for r in mine],
        "load_time_s":distribution([r["load_latency_s"] for r in mine],unit="s"),
        "warmup_s":distribution([r["warmup_latency_s"] for r in mine],unit="s"),
        "load_resource_receipts":[{"block":r["block"],"stabilized_idle_before":r["stabilized_idle"][-1],"after_load":r["resource_after_load"],"after_unload":r["resource_after_unload"]} for r in mine],
        "context":2048,"context_checkpoints":0,"concurrency":1,"requested_gpu_offload":None,"actual_gpu_layers":None,
        "gpu_placement":"NATIVE_AUTOMATIC_UNKNOWN; inherited assignment_order.gpu_requested is unused legacy field",
        "finish_reason":None,"finish_reason_status":"UNKNOWN_NATIVE_API","energy_j":None,
    }


def figures(path, final, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    colors={KEYS[0]:"#1976a3",KEYS[1]:"#c54a35"};labels={KEYS[0]:"Qwen9 Q8_0",KEYS[1]:"Qwen27 UD-Q4_K_M"}
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout="constrained")
    for model in KEYS:
        m=final["models"][model]
        axes[0].scatter(m["latency_s"]["p50"],m["quality"]["strict_set_em"]*100,s=80,color=colors[model],label=labels[model])
        axes[0].annotate(labels[model],(m["latency_s"]["p50"],m["quality"]["strict_set_em"]*100),xytext=(-5,7) if model==KEYS[1] else (5,7),ha="right" if model==KEYS[1] else "left",textcoords="offset points",fontsize=8)
        values=np.sort([r["latency_s"] for r in rows if r["kind"]=="telemetry" and r["model_key"]==model]);axes[1].step(values,np.arange(1,len(values)+1)/len(values),where="post",color=colors[model],label=labels[model])
    axes[0].set(xlabel="V2 TELEMETRY40 median latency (s)",ylabel="Historical DEV EM (%; 289 valid)",ylim=(45,55));axes[1].set(xlabel="V2 TELEMETRY40 request latency (s)",ylabel="Empirical cumulative fraction")
    for ax in axes:ax.grid(alpha=.25)
    axes[1].legend(fontsize=8)
    fig.suptitle("Distinct datasets: historical DEV quality + systems characterization; no confirmatory winner")
    fig.savefig(path/"systems_v2_quality_latency.png",dpi=200);fig.savefig(path/"systems_v2_quality_latency.svg");plt.close(fig)


def main():
    safe=ROOT/"results"/RUN;raw=ROOT/".runtime/mera"/RUN
    plan,receipt=read(safe/"protocol_frozen.json"),read(safe/"completion_receipt.json")
    records,metrics,loads,scores=journal(raw/"raw.jsonl"),journal(safe/"inference_metrics.jsonl"),read(safe/"load_receipts.json"),journal(safe/"study_c_scores.jsonl")
    pack=read(ROOT/"data/study_c_technical_20261003.json");cases={c["id"]:c for c in pack["cases"]}
    checks=integrity(plan,receipt,records,metrics,loads,cases,scores)
    if not all(checks.values()):raise ValueError("V2 integrity failure: "+",".join(k for k,v in checks.items() if not v))
    archived=archive_sources(plan)
    metadata=[{"id":c["id"],"expected_action":c["expected"]["action"],"tool_eligible":c["expected"].get("tool") is not None,"unit_conversion_case":c["expected"].get("reason_code")=="EXPLICIT_CONVERSION_REQUIRED"} for c in cases.values()]
    corrected=aggregate(scores,metadata)
    corrected.update(run_id=RUN,created_utc=datetime.now(timezone.utc).isoformat(),original_summary_path=(safe/"study_c_summary.json").relative_to(ROOT).as_posix(),
        original_summary_sha256=digest(safe/"study_c_summary.json"),scores_sha256=digest(safe/"study_c_scores.jsonl"),study_pack_sha256=digest(ROOT/"data/study_c_technical_20261003.json"),
        limitations=["Qwen9 and deterministic outputs from V1; Qwen27 from V2 operational recovery. Inference configurations differ; not controlled causal model-size arithmetic comparison.","Typed task supplied; authoritative formula/contracts supplied, no free-language tool recognition measured.","SIMULATED executor replay is independent of arithmetic output and is not live model tool use.","27 constructed DEV cases; external published numerical controls coexist with experiment-defined cases; no agronomic recommendation quality tested."])
    write(safe/"study_c_corrected_aggregate.json",corrected)
    study_csv=[]
    for model,m in corrected["models"].items():
        study_csv.append({"model_key":model,"status":"DEV","source_runs":";".join(m["source_runs"]),"n":m["n"],"complete_correct":m["correct"],"action_correct":m["action_correct"],"real_tool_n":m["declared_real_tool_n"],"real_tool_correct":m["declared_real_tool_correct"],"numeric_n":m["numeric_n"],"numeric_correct":m["numeric_correct"],"rounding_1e4_correct":m["numeric_rounding_1e4_correct"],"missing_or_invalid_n":m["missing_input_or_invalid_input_n"],"missing_or_invalid_correct":m["missing_input_or_invalid_input_correct"],"unit_conversion_n":m["unit_conversion_n"],"unit_conversion_correct":m["unit_conversion_correct"],"errors":m["errors"],"parse_invalid":m["parse_invalid"],"latency_p50_s":m["latency_s"]["p50"],"latency_p95_s":m["latency_s"]["p95"],"simulated_executor_replay_correct":m["declared_tool_executor_replay"]["correct"],"simulated_executor_replay_n":m["declared_tool_executor_replay"]["n_tool_eligible"],"live_model_tool_calls":0})
    csv_write(safe/"study_c_corrected_table.csv",study_csv)
    table=["| Study C configuration | source_run | complete/27 | action/27 | real declared tool/26 | numeric/16 | missing or invalid/10 | units/3 | p50/p95 s | SIMULATED tool replay/26 |","|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for model,m in corrected["models"].items():table.append(f"| {model} | {'; '.join(m['source_runs'])} | {m['correct']}/27 | {m['action_correct']}/27 | {m['declared_real_tool_correct']}/26 | {m['numeric_correct']}/16 | {m['missing_input_or_invalid_input_correct']}/10 | {m['unit_conversion_correct']}/3 | {m['latency_s']['p50']:.6f}/{m['latency_s']['p95']:.6f} | {m['declared_tool_executor_replay']['correct']}/26 |")
    with (safe/"study_c_corrected_table.md").open("x",encoding="utf-8") as f:f.write("\n".join(table)+"\n\nTyped tasks/formulas supplied; Qwen9 V1 versus Qwen27 V2 config differs. SIMULATED replay is not a live tool call.\n")
    historical=read(ROOT/"results/20261003_resource_analysis/analysis.json")
    final={"status":"SYSTEMS_TELEMETRY","run_id":RUN,"historical_quality_status":"DEV","models":{m:systems_model(m,records,loads,historical) for m in KEYS},
           "host_idle_before":read(safe/"host_before.json"),"host_idle_after":read(safe/"host_after.json"),"quality_remeasured":False,"private_test_run":False}
    q9,q27=(final["models"][m] for m in KEYS)
    final["ratios"]={"median_latency_27_over_9":q27["latency_s"]["p50"]/q9["latency_s"]["p50"],"p95_latency_27_over_9":q27["latency_s"]["p95"]/q9["latency_s"]["p95"],"whole_gpu_telemetry_peak_27_minus_9_mib":q27["resources"]["gpu_memory_used_mib_request_peaks"]["max"]-q9["resources"]["gpu_memory_used_mib_request_peaks"]["max"],"whole_ram_telemetry_peak_27_minus_9_gib":q27["resources"]["system_ram_used_gib_request_peaks"]["max"]-q9["resources"]["system_ram_used_gib_request_peaks"]["max"]}
    write(safe/"systems_corrected_aggregate.json",final)
    out=ROOT/"results/20261003_resource_analysis";rows=[]
    for model in [*KEYS,"gemma-4-26b-a4b-it"]:
        h=historical["models"][model];q=h["quality"];r=h["resources"];v=final["models"].get(model)
        rows.append({"model_key":model,"quality_status":"DEV","quality_run_id":historical["historical_run_id"],"quality_n":q["n_scored"],"strict_em_count":q["strict_em_count"],"strict_set_em":q["strict_set_em"],"strict_set_f1":q["strict_set_f1"],"exact_gguf_bytes":r["exact_gguf_bytes"],"exact_gguf_gib":r["exact_gguf_gib"],"quantization":r["quantization"],"systems_status":"SYSTEMS_TELEMETRY" if v else "HISTORICAL_REFERENCE","systems_run_id":RUN if v else historical["historical_run_id"],"systems_n":40 if v else 293,"latency_mean_s":v["latency_s"]["mean"] if v else h["latency"]["mean"],"latency_p50_s":v["latency_s"]["p50"] if v else h["latency"]["p50"],"latency_p95_s":v["latency_s"]["p95"] if v else h["latency"]["p95"],"backend_tps_p50":v["backend_tokens_per_second"]["p50"] if v else None,"client_approx_tps_p50":None if v else h["client_tps"]["p50"],"client_ttft_p50_s":v["client_ttft_s"]["p50"] if v else h["ttft"]["p50"],"backend_ttft_p50_s":v["backend_ttft_s"]["p50"] if v else None,"whole_gpu_peak_mib":v["resources"]["gpu_memory_used_mib_request_peaks"]["max"] if v else r["whole_gpu_peak_mib"],"whole_ram_peak_gib":v["resources"]["system_ram_used_gib_request_peaks"]["max"] if v else r["whole_system_ram_peak_gib"],"named_process_rss_peak_mib":v["resources"]["lmstudio_process_group_rss_mib_request_peaks"]["max"] if v else None,"load_samples_s":json.dumps(v["load_samples_s"]) if v else json.dumps([r["first_load_s"],r["load_time"]["p50"]]),"load_samples_description":"2 exact samples" if v else "first and median of30; not2samples","warmup_samples_s":json.dumps(v["warmup_samples_s"]) if v else json.dumps([r["warmup_time"]["p50"]]),"context":2048,"context_checkpoints":0 if v else 32,"gpu_placement":"NATIVE_AUTOMATIC_UNKNOWN" if v else "CLI_requested_0.70_actual_layers_UNKNOWN","transport_errors":v["errors"] if v else q["errors"],"json_parse_invalid_systems":v["json_parse_invalid"] if v else None,"invalid_outputs_dev":q["invalid_output"]})
    csv_write(out/"final_model_table.csv",rows)
    figures(out,final,records)
    qa={"status":"INDEPENDENT_QA_APPEND_ONLY","run_id":RUN,"created_utc":datetime.now(timezone.utc).isoformat(),"checks":checks,"all_integrity_checks_pass":all(checks.values()),
        "source_archive_manifest_path":archived.relative_to(ROOT).as_posix(),"source_archive_manifest_sha256":digest(archived),
        "corrected_study_c_path":(safe/"study_c_corrected_aggregate.json").relative_to(ROOT).as_posix(),"corrected_systems_path":(safe/"systems_corrected_aggregate.json").relative_to(ROOT).as_posix(),
        "limitations":["Historical DEV quality and V2 telemetry are distinct protocols/datasets; no refreshed quality claim.","V2 automatic GPU placement unknown, inherited max/.75 assignment fields stale and unused.","Q9 StudyC reusedV1; Q27V2 arithmetic comparison has configuration difference.","RSS is basename allowlisted working-set sum, without lineage or physical-memory allocation proof.","N40p99 suppressed in corrected aggregate; two load/warmup values reported individually.","Native EOS reason unexposed; chat.end transport completion is not proof of stop EOS.","Prompt equivalent throughput uses reported full input tokens/client processing span; cache reuse not exposed, not guaranteed processed-token throughput."],
        "source_hashes":{p.relative_to(ROOT).as_posix():digest(p) for p in [safe/"protocol_frozen.json",safe/"completion_receipt.json",safe/"inference_metrics.jsonl",raw/"raw.jsonl",safe/"study_c_scores.jsonl",safe/"load_receipts.json",safe/"study_c_corrected_aggregate.json",safe/"systems_corrected_aggregate.json",out/"final_model_table.csv",out/"systems_v2_quality_latency.png",out/"systems_v2_quality_latency.svg",archived]},
        "new_inference_calls":0,"original_files_modified":False,"private_test_run":False}
    write(ROOT/"results/20261003_resource_session/independent_systems_v2_qa.json",qa)
    print(json.dumps({"integrity_pass":qa["all_integrity_checks_pass"],"checks_n":len(checks),"study":corrected["models"],"ratios":final["ratios"],"final_csv":str(out/"final_model_table.csv")},ensure_ascii=False))


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    main()

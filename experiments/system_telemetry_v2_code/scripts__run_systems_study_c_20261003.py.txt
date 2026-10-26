"""Frozen, counterbalanced TELEMETRY40 + separate Study C development run.

No private TEST input, paid API, downloads or automatic retries. Raw benchmark
content stays in ignored .runtime. The native transport has no seed/schema
control; this difference from historical DEV293 is disclosed and never used to
replace historical quality. Strictly sequential one controller and concurrency1.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import home_pc_benchmark as guards
import home_lm_api_benchmark as native
import mera_local_screen_20261003 as screen
from mera_dev_20261003 import select_balanced
from agro_route.home_config import resolve_api_key
from agro_route.lm_telemetry_20261003 import (VERSION, ResourceSampler, device_snapshot, native_payload,
    parse_native_sse, parse_json_presentation, redact, safe_record, summarize_resources, utc_now)
from agro_route.deterministic_study_20261003 import (TASK_TO_TOOL, REQUIRED, UNITS, OUTPUT_UNITS,
    public_request, execute_request, score_case)
from agro_route.study_c_run_20261003 import score_text

RUN = "20261003_systems_study_c_v1"
SAFE = ROOT / "results" / RUN
RAW = ROOT / ".runtime" / "mera" / RUN
STUDY = ROOT / "data/study_c_technical_20261003.json"
MODELS = [("qwen3.5-9b", "max"), ("qwen3.8-27b", "0.75")]
FORMULAS = """Все вычисления выполняй сам, без инструментов. Никаких агрономических советов.
Верни ровно JSON object без пояснений. Для ANSWER: action,tool,numeric,unit.
Для ASK_FOR_DATA: action,tool,reason_code,requested_fields; не добавляй numeric даже null.
Для ABSTAIN: action,reason_code; без numeric. Неизвестный task: ABSTAIN,UNSUPPORTED_TASK.
task заранее дан: это НЕ проверка распознавания свободного языка. tool — декларация выбора; вызова кода нет.
Если не хватает inputs или units: ASK_FOR_DATA,MISSING_INPUTS, все отсутствующие поля.
Поля units обозначай units.<name>. При лишних полях: UNSUPPORTED_FIELDS.
При неверных units: EXPLICIT_CONVERSION_REQUIRED, перечисли неверные units.<name>.
Только после проверки полноты/лишних полей/единиц проверь диапазоны и считай.
При неправильных числах: INVALID_INPUTS, перечисли поля. Не угадывай значения.
e(T)=0.6108*exp(17.27*T/(T+237.3)), давление кПа.
gdd: sum(max(0,(tmin[i]+tmax[i])/2-base)); degC day; нет верхнего caps.
tmin/tmax непустые списки равной длины, tmin<=tmax, -60..60C; base -20..40.
Неверная длина/порядок/температуры: INVALID_INPUTS, поля tmin,tmax.
vpd_single: e(temperature)*(1-rh/100); kPa; temperature -40..60, rh 0..100.
vpd_daily: (e(tmin)+e(tmax))/2-(e(tmin)*rhmax+e(tmax)*rhmin)/200.
tmin/tmax -40..60, rhmin/rhmax 0..100. При неверном порядке: поля tmin,tmax,rhmin,rhmax.
et0: [0.408*delta*(rn-g)+gamma*900/(temperature+273)*u2*(es-ea)]/[delta+gamma*(1+0.34*u2)]; mm/day.
temperature -40..60,u2 0..30,es/ea 0..15,delta 1e-12..2,gamma 1e-12..1.
rn,g конечны, знаки сохраняются. ea>es: INVALID_INPUTS, ea,es.
wind_height!=2: EXPLICIT_CONVERSION_REQUIRED, u2,wind_height. Нет default G=0.
rain gap: max(0,target-sum(rain)), mm. target/rain 0..1000000; rain непустой список.
Выводи достаточное число десятичных знаков, цель абсолютная вычислительная погрешность 1e-8.
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def append(path, value):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def study_system():
    contracts = {task: {"tool": tool, "required_inputs": REQUIRED[tool], "units": UNITS[tool],
                        "output_unit": OUTPUT_UNITS[tool]} for task, tool in TASK_TO_TOOL.items()}
    return FORMULAS + "\nКонтракты:\n" + json.dumps(contracts, ensure_ascii=False)


def prepare():
    original = json.loads((ROOT / "results/20261003_local_screen_571682f5/protocol_frozen.json").read_text(encoding="utf-8"))
    items, _, _ = screen.validate_source(screen.DEFAULT_SOURCE, original["source_sha256"])
    selected = select_balanced(items, per_domain=4)
    cases = json.loads(STUDY.read_text(encoding="utf-8"))["cases"]
    # Alternating within domain gives each temporal block two of every discipline.
    blocks = [selected[::2], selected[1::2]]
    assignments = [(0, MODELS[0]), (0, MODELS[1]), (1, MODELS[1]), (1, MODELS[0])]
    identities = json.loads((ROOT / "results/20261003_local_screen_571682f5/installed_weight_checksums.json").read_text(encoding="utf-8"))["models"]
    system = study_system()
    plan = {"run_id": RUN, "status": "SYSTEMS_TELEMETRY", "created_utc": utc_now(),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
            "source_sha256": original["source_sha256"], "study_c_sha256": sha(STUDY.read_bytes()),
            "study_c_status": "DEV", "telemetry_n_each": 40, "study_c_n_each": 27,
            "selection": "4 per discipline by floor(i*N/4) of sorted DEV IDs; no labels or predictions; even/odd split into two all-discipline blocks",
            "telemetry_item_ids": [i.item_id for i in selected],
            "blocks": [[i.item_id for i in block] for block in blocks],
            "assignment_order": [{"block": block, "model_key": model, "gpu_requested": ratio} for block, (model, ratio) in assignments],
            "study_c_case_blocks": [[case["id"] for case in cases[::2]], [case["id"] for case in cases[1::2]]],
            "prompt_hashes": {"mera_system": sha(screen.SYSTEM.encode()), "study_c_system": sha(system.encode())},
            "requested": native_payload("placeholder", "", ""), "seed": None,
            "seed_note": "Native v1 official API does not document seed or response_format; omitted. Different transport from historical DEV293, systems characterization only.",
            "concurrency": 1, "context": 2048, "warmup": "one synthetic MCQ per load; not measured task", "models": MODELS,
            "memory_stabilization": "min 3 snapshots after unload >=2s apart; stop at 5; consecutive GPU free delta<=128MiB and RAM available delta<=.35GiB; stop if not achieved",
            "resources": "whole GPU/system RAM plus named LMStudio process-group RSS; start/end snapshots plus sampled interval .15s+acquisition overhead",
            "energy": "NOT_ESTIMATED", "finish_reason": "UNKNOWN unless native stats exposes a stop reason; successful chat.end is transport completion, not EOS proof",
            "private_test_run": False, "paid_api_calls": 0,
            "source_code_sha256": {str(path.relative_to(ROOT)).replace('\\','/'): sha(path.read_bytes()) for path in [Path(__file__), ROOT / 'src/agro_route/lm_telemetry_20261003.py', ROOT / 'src/agro_route/study_c_run_20261003.py']},
            "identities": [i for i in identities if i["model_key"] in {m for m, _ in MODELS}],
            "secondary_numeric_diagnostic": "absolute tolerance max(frozen_abs_tolerance,1e-4); descriptive rounding only; strict score unchanged"}
    SAFE.mkdir(exist_ok=False)
    RAW.mkdir(parents=True, exist_ok=False)
    write(SAFE / "protocol_frozen.json", plan)
    (SAFE / "study_c_system_prompt.txt").write_text(system, encoding="utf-8")
    return plan, blocks, cases, assignments


def stabilized():
    rows = []
    for attempt in range(5):
        rows.append(device_snapshot())
        if len(rows) >= 3 and abs(rows[-1]["gpu_memory_free_mib"]-rows[-2]["gpu_memory_free_mib"]) <= 128 and abs(rows[-1]["system_ram_available_gib"]-rows[-2]["system_ram_available_gib"]) <= .35:
            return rows
        time.sleep(2)
    raise RuntimeError("Idle memory did not stabilize")


def call(client, key, identifier, system, prompt, item_id, model_key, block, kind, domain):
    payload = native_payload(identifier, system, prompt)
    record = {"task_id": item_id, "model_key": model_key, "block": block, "kind": kind, "domain": domain,
              "request_utc": utc_now(), "prompt_sha256": sha(prompt.encode()), "prompt_bytes": len(prompt.encode()),
              "request_sha256": sha(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()),
              "request": payload, "error": None, "parse_success": False, "finish_reason": None,
              "finish_reason_source": "UNKNOWN_NATIVE_API_DOES_NOT_EXPOSE_STOP_REASON", "response_text": ""}
    before = device_snapshot()
    with ResourceSampler() as monitor:
        started = time.perf_counter()
        try:
            with client.stream("POST", "http://127.0.0.1:1234/api/v1/chat", json=payload,
                               headers={"Authorization": "Bearer " + key}) as response:
                response.raise_for_status()
                def lines():
                    for line in response.iter_lines():
                        if monitor.tripped.is_set() or time.perf_counter() - started > 60:
                            raise RuntimeError("Resource or wall deadline guard")
                        yield line
                record.update(parse_native_sse(lines(), started))
            if (record.get("stats") or {}).get("total_output_tokens", 0) is not None and record["stats"]["total_output_tokens"] >= payload["max_output_tokens"]:
                record["error"] = record["error"] or "OutputBudgetReached"
            try:
                obj = parse_json_presentation(record["response_text"])
                record["parse_success"] = bool(obj)
            except (ValueError, TypeError):
                pass
        except (httpx.HTTPError, ValueError, RuntimeError, OSError) as exc:
            record["error"] = type(exc).__name__
        record["latency_s"] = time.perf_counter() - started
        record["end_utc"] = utc_now()
    after = device_snapshot()
    record.update(resource_before=before, resource_after=after,
                  resources=summarize_resources([before, *monitor.rows, after]), resource_samples=[before, *monitor.rows, after],
                  resource_errors=monitor.errors)
    return redact(record, key)


def distribution(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)]
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            **{f"p{int(q*100)}": float(np.quantile(values, q)) if values else None for q in [.5, .9, .95, .99]}}


def analyze():
    records = [json.loads(line) for line in (SAFE / "inference_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
    loads = json.loads((SAFE / "load_receipts.json").read_text(encoding="utf-8"))
    study_rows = [json.loads(line) for line in (SAFE / "study_c_scores.jsonl").read_text(encoding="utf-8").splitlines()]
    result = {"run_id": RUN, "classification": "SYSTEMS_TELEMETRY", "private_test_run": False, "models": {}}
    for model, _ in MODELS:
        own = [r for r in records if r["model_key"] == model and r["kind"] == "telemetry"]
        mine_load = [r for r in loads if r["model_key"] == model]
        fields = {"latency_s": distribution([r["latency_s"] for r in own])}
        for group, names in [("timing", ["client_ttft_any_s", "client_ttft_answer_s", "client_generation_span_s", "client_prompt_processing_span_s", "client_prompt_token_equivalent_tps"]),
                             ("stats", ["tokens_per_second", "time_to_first_token_seconds", "input_tokens", "total_output_tokens"])]:
            for name in names:
                fields[name] = distribution([(r.get(group) or {}).get(name) for r in own])
        resources = [r["resources"] for r in own]
        for name in ["gpu_memory_used_mib", "system_ram_used_gib", "lmstudio_process_group_rss_mib", "gpu_temperature_c"]:
            fields[name + "_request_sampled_peak"] = distribution([r[name + "_peak_sampled"] for r in resources])
        fields.update(n=len(own), errors=sum(bool(r["error"]) for r in own), parse_invalid=sum(not r["parse_success"] for r in own),
                      stream_completed=sum(bool(r["stream_complete"]) for r in own),
                      load_time_s=distribution([r["load_latency_s"] for r in mine_load]),
                      warmup_s=distribution([r["warmup_latency_s"] for r in mine_load]),
                      block_latencies={str(block): distribution([r["latency_s"] for r in own if r["block"] == block]) for block in [0,1]},
                      energy_j=None, actual_gpu_layers=None, seed=None)
        result["models"][model] = fields
    result["latency_ratio_q27_over_q9_p50"] = result["models"][MODELS[1][0]]["latency_s"]["p50"] / result["models"][MODELS[0][0]]["latency_s"]["p50"]
    write(SAFE / "systems_summary.json", result)
    summary = {"run_id": RUN, "classification": "DEV", "study": "C", "models": {}}
    for model in [m for m, _ in MODELS] + ["deterministic_tools"]:
        own = [r for r in study_rows if r["model_key"] == model]
        numeric = [r for r in own if r["numeric_case"]]
        ask = [r for r in own if r["expected_action"] == "ASK_FOR_DATA"]
        summary["models"][model] = {"n": len(own), "correct": sum(r["correct"] for r in own),
            "action_correct": sum(r["action_correct"] for r in own), "declared_tool_correct": sum(r["tool_correct"] for r in own),
            "numeric_n": len(numeric), "numeric_correct": sum(r["numeric_correct"] for r in numeric),
            "numeric_rounding_1e4_correct": sum(r["numeric_rounding_1e4_correct"] for r in numeric),
            "missing_input_unit_n": len(ask), "missing_input_unit_correct": sum(r["correct"] for r in ask),
            "invalid_units_n": sum(r["category"] == "units" for r in own),
            "parse_invalid": sum(not r["parse_success"] for r in own),
            "declared_selection_replay_correct": sum(r["declared_selection_tool_replay_correct"] for r in own),
            "latency_s": distribution([r["latency_s"] for r in own]),
            "by_group": {group: {"n": len(sub), "correct": sum(r["correct"] for r in sub)} for group in sorted({r["group"] for r in own}) if (sub := [r for r in own if r["group"] == group])}}
    summary["limitations"] = ["27 constructed development cases, typed task supplied", "Declared tool name is not actual tool invocation", "Strict numerical tolerance frozen; 1e-4 secondary diagnostic predeclared", "Deterministic reference uses authoritative formulas / experiment-defined rain gap, not agronomic advice"]
    write(SAFE / "study_c_summary.json", summary)
    with (SAFE / "telemetry_table.csv").open("x", encoding="utf-8", newline="") as handle:
        fields = ["model_key", "task_id", "block", "domain", "latency_s", "backend_tps", "backend_ttft_s", "client_ttft_s", "gpu_peak_mib", "ram_peak_gib", "rss_peak_mib", "input_tokens", "output_tokens", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for r in records:
            if r["kind"] != "telemetry": continue
            writer.writerow({"model_key":r["model_key"],"task_id":r["task_id"],"block":r["block"],"domain":r["domain"],"latency_s":r["latency_s"],"backend_tps":r["stats"]["tokens_per_second"],"backend_ttft_s":r["stats"]["time_to_first_token_seconds"],"client_ttft_s":r["timing"]["client_ttft_answer_s"],"gpu_peak_mib":r["resources"]["gpu_memory_used_mib_peak_sampled"],"ram_peak_gib":r["resources"]["system_ram_used_gib_peak_sampled"],"rss_peak_mib":r["resources"]["lmstudio_process_group_rss_mib_peak_sampled"],"input_tokens":r["stats"]["input_tokens"],"output_tokens":r["stats"]["total_output_tokens"],"error":r["error"]})
    print(json.dumps({"systems": result, "study_c": summary}, ensure_ascii=True), flush=True)


def run():
    plan, blocks, cases, assignments = prepare()
    key, _ = resolve_api_key("local", env_path=ROOT / ".env")
    if not key:
        raise RuntimeError("Local credential unavailable")
    client = httpx.Client(timeout=httpx.Timeout(60), trust_env=False)
    screen.idle(client, key)
    write(SAFE / "host_before.json", device_snapshot())
    inventory = json.loads((ROOT / "results/20261003_local_screen_571682f5/inventory.json").read_text(encoding="utf-8"))
    write(SAFE / "software_identity.json", {"lm_studio_version": inventory.get("hardware", {}).get("lm_studio_version"),
        "historical_inventory_sha256": sha((ROOT / "results/20261003_local_screen_571682f5/inventory.json").read_bytes()),
        "runtime_cli_observed": guards.command([guards.LMS, "runtime", "ls"]).stdout,
        "per_model_runtime_identity": "UNKNOWN_native_response_not_exposed", "module_version": VERSION})
    loads = []
    for index, (block, (model, ratio)) in enumerate(assignments):
        identifier = f"systems-{index}-{model}"
        load = {"block": block, "model_key": model, "gpu_requested": ratio, "actual_gpu_layers": None,
                "stabilized_idle": stabilized(), "load_start_utc": utc_now()}
        argv = [guards.LMS, "load", model, "--context-length", "2048", "--parallel", "1", "--gpu", ratio,
                "--no-speculative-draft-mtp", "--identifier", identifier, "--yes"]
        attempted = False
        try:
            started = time.perf_counter(); attempted = True
            response = guards.guarded_load(argv, RAW / f"load_{index}.txt", load)
            load["load_latency_s"] = time.perf_counter() - started
            if response.returncode:
                raise RuntimeError("Load failed")
            matches = [(m, i) for m in native.native_models(client, key) for i in m.get("loaded_instances", []) if i["id"] == identifier]
            if len(matches) != 1:
                raise RuntimeError("Exact model instance unavailable")
            meta, instance = matches[0]
            config = instance.get("config") or {}
            if config.get("context_length") != 2048 or config.get("parallel") != 1 or config.get("speculative_draft_mtp") is not False:
                raise RuntimeError("Load config not confirmed")
            load["config"] = config
            load["native_model_identity"] = {k: meta.get(k) for k in ["key", "display_name", "architecture", "quantization", "size_bytes", "path"]}
            load["resource_after_load"] = device_snapshot()
            warm = call(client, key, identifier, screen.SYSTEM, screen.WARMUP, "synthetic_warmup", model, block, "warmup", "synthetic")
            append(RAW / "raw.jsonl", warm); append(SAFE / "inference_metrics.jsonl", safe_record(warm))
            load["warmup_latency_s"] = warm["latency_s"]
            if warm["error"] or not warm["parse_success"]:
                raise RuntimeError("Warmup compatibility failed")
            for item in blocks[block]:
                assert item.split == "dev"
                raw = call(client, key, identifier, screen.SYSTEM, item.prompt, item.item_id, model, block, "telemetry", item.domain)
                append(RAW / "raw.jsonl", raw); append(SAFE / "inference_metrics.jsonl", safe_record(raw))
                if raw["resource_errors"]:
                    raise RuntimeError("Resource observation failed")
            for case in cases[block::2]:
                prompt = json.dumps(public_request(case), ensure_ascii=False)
                raw = call(client, key, identifier, study_system(), prompt, case["id"], model, block, "study_c", case["group"])
                scored = score_text(case, raw["response_text"], raw["error"])
                append(RAW / "raw.jsonl", raw); append(SAFE / "inference_metrics.jsonl", safe_record(raw))
                append(SAFE / "study_c_scores.jsonl", {"model_key": model, "latency_s": raw["latency_s"], "error": raw["error"], **scored})
                if raw["resource_errors"]:
                    raise RuntimeError("Resource observation failed")
            print(json.dumps({"model": model, "block": block, "telemetry_done": len(blocks[block]), "study_c_done": len(cases[block::2])}), flush=True)
        finally:
            if attempted:
                unloaded = guards.command([guards.LMS, "unload", identifier])
                load["unload_success"] = unloaded.returncode == 0
                screen.idle(client, key)
                if not load["unload_success"]:
                    raise RuntimeError("Own model cleanup failed")
            load["resource_after_unload"] = device_snapshot()
            loads.append(load)
            append(SAFE / "loads_append.jsonl", redact(load, key))
    write(SAFE / "load_receipts.json", redact(loads, key))
    for case in cases:
        started = time.perf_counter(); output = execute_request(public_request(case)); elapsed = time.perf_counter()-started
        scored = score_text(case, json.dumps(output))
        append(SAFE / "study_c_scores.jsonl", {"model_key": "deterministic_tools", "latency_s": elapsed, "error": None, **scored})
    write(SAFE / "host_after.json", device_snapshot())
    write(SAFE / "completion_receipt.json", {"run_id":RUN,"finished_utc":utc_now(),"state":"COMPLETE","models_unloaded":True,
          "raw_sha256":sha((RAW / "raw.jsonl").read_bytes()),"inference_metrics_sha256":sha((SAFE / "inference_metrics.jsonl").read_bytes()),
          "new_paid_api_spend_authorized_usd":0,"paid_api_calls":0,"private_test_run":False})
    client.close()
    analyze()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.run: run()
    elif args.analyze: analyze()
    else: parser.print_help()

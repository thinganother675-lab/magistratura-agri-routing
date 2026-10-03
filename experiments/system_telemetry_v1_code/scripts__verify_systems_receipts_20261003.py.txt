# SPDX-License-Identifier: Apache-2.0
"""Independent append-only audit of the frozen systems/Study C run.

No inference, no repairs of original run files. Raw restricted content is read
locally to verify hashes/payload projection; only aggregate checks are exported.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.deterministic_study_20261003 import public_request
from agro_route.lm_telemetry_20261003 import safe_record
from agro_route.resource_analysis_20261003 import distribution

RUN = "20261003_systems_study_c_v1"
KEYS = ("qwen3.5-9b", "qwen3.8-27b")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def journal(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def inspect(root=ROOT):
    root = Path(root)
    safe, raw = root / "results" / RUN, root / ".runtime/mera" / RUN
    plan_path, raw_path, safe_path = safe / "protocol_frozen.json", raw / "raw.jsonl", safe / "inference_metrics.jsonl"
    plan, receipt = read(plan_path), read(safe / "completion_receipt.json")
    if receipt["state"] != "COMPLETE":
        raise ValueError("Attempt run has not completed")
    records, projected = journal(raw_path), journal(safe_path)
    cases = {c["id"]: c for c in read(root / "data/study_c_technical_20261003.json")["cases"]}
    scores = journal(safe / "study_c_scores.jsonl")
    loads = read(safe / "load_receipts.json")
    code_hashes = {name: sha(root / name) == digest for name, digest in plan["source_code_sha256"].items()}
    expected_sequence = []
    for assignment in plan["assignment_order"]:
        model, block = assignment["model_key"], assignment["block"]
        expected_sequence += [(model, block, "warmup", "synthetic_warmup")]
        expected_sequence += [(model, block, "telemetry", item) for item in plan["blocks"][block]]
        expected_sequence += [(model, block, "study_c", item) for item in plan["study_c_case_blocks"][block]]
    observed_sequence = [(r["model_key"], r["block"], r["kind"], r["task_id"]) for r in records]
    historical_rows = {
        model: {r["item_id"]: r for r in journal(root / "results/20261003_local_screen_571682f5/dev293" / f"{model}_metrics.jsonl")}
        for model in KEYS}
    checks = {
        "frozen_code_hashes_match": all(code_hashes.values()),
        "raw_completion_hash_match": sha(raw_path) == receipt["raw_sha256"],
        "safe_completion_hash_match": sha(safe_path) == receipt["inference_metrics_sha256"],
        "study_pack_hash_match": sha(root / "data/study_c_technical_20261003.json") == plan["study_c_sha256"],
        "safe_projection_matches_raw": projected == [safe_record(r) for r in records],
        "sequence_matches_counterbalanced_plan": observed_sequence == expected_sequence,
        "all_expected_attempts_once": len(observed_sequence) == len(set(observed_sequence)),
        "no_paid_api_or_private_test": plan["paid_api_calls"] == receipt["paid_api_calls"] == 0 and plan["private_test_run"] is receipt["private_test_run"] is False,
        "all_own_models_unloaded": receipt["models_unloaded"] is True and all(r["unload_success"] for r in loads),
        "tools_disabled_in_all_requests": all(r["request"].get("integrations") == [] for r in records),
        "storage_history_disabled": all(r["request"].get("store") is False and "previous_response_id" not in r["request"] for r in records),
        "no_tools_in_response_events": all(not e["data"]["type"].startswith("tool_call.") for r in records for e in r.get("events", [])),
        "reasoning_off_requested_and_unobserved": all(r["request"]["reasoning"] == "off" and not r.get("reasoning_text") and not (r.get("stats") or {}).get("reasoning_output_tokens") for r in records),
        "request_hashes_match": all(hashlib.sha256(json.dumps(r["request"], ensure_ascii=False, sort_keys=True).encode()).hexdigest() == r["request_sha256"] for r in records),
        "prompt_bytes_hash_match": all(hashlib.sha256(r["request"]["input"].encode()).hexdigest() == r["prompt_sha256"] and len(r["request"]["input"].encode()) == r["prompt_bytes"] for r in records),
        "historical_mera_prompt_hashes_match": all(r["prompt_sha256"] == historical_rows[r["model_key"]][r["task_id"]]["prompt_sha256"] for r in records if r["kind"] == "telemetry"),
        "study_gold_not_in_public_payload": all(json.loads(r["request"]["input"]) == public_request(cases[r["task_id"]]) for r in records if r["kind"] == "study_c"),
        "system_prompt_hashes_match": all(hashlib.sha256(r["request"]["system_prompt"].encode()).hexdigest() == plan["prompt_hashes"]["study_c_system" if r["kind"] == "study_c" else "mera_system"] for r in records),
        "actual_load_context_parallel_mtp_match": all(r["config"]["context_length"] == 2048 and r["config"]["parallel"] == 1 and r["config"]["speculative_draft_mtp"] is False for r in loads),
        "native_model_keys_match_load": all(r["native_model_identity"]["key"] == r["model_key"] for r in loads),
        "timing_components_nonnegative_bounded_by_http_latency": all(v is None or 0 <= v <= r["latency_s"] + 1e-6 for r in records for k, v in (r.get("timing") or {}).items() if k.endswith("_s")),
        "whole_device_and_process_scope_disclosed": all("NOT per-model allocation" in r["resources"]["scope"] for r in records),
        "energy_unknown_not_estimated": all(r["resources"]["energy_j"] is None for r in records),
        "native_finish_reason_unknown_preserved": all(r["finish_reason"] is None and r["finish_reason_source"] == "UNKNOWN_NATIVE_API_DOES_NOT_EXPOSE_STOP_REASON" for r in records),
    }
    model_checks = {}
    for model in KEYS:
        telemetry = [r for r in records if r["model_key"] == model and r["kind"] == "telemetry"]
        study = [r for r in records if r["model_key"] == model and r["kind"] == "study_c"]
        valid = [r for r in telemetry if not r["error"] and r.get("stream_complete")]
        failed = [r for r in telemetry + study if r["error"]]
        sub = [r for r in scores if r["model_key"] == model]
        eligible = [r for r in sub if cases[r["id"]]["expected"].get("tool") is not None]
        units = [r for r in sub if cases[r["id"]]["expected"].get("reason_code") == "EXPLICIT_CONVERSION_REQUIRED"]
        unit_counts = {"n": len(units), "correct": sum(r["correct"] for r in units)}
        model_checks[model] = {
            "telemetry_attempts": len(telemetry), "telemetry_stream_success": len(valid),
            "telemetry_transport_or_guard_error": len(telemetry)-len(valid),
            "successful_latency_s_conditional_only": distribution([r["latency_s"] for r in valid], unit="s"),
            "study_c_attempts": len(study), "study_c_stream_success": sum(not r["error"] and bool(r.get("stream_complete")) for r in study),
            "failed_attempts_with_ram_below_guard": sum(r["resources"]["system_ram_available_gib_min_sampled"] < 2 for r in failed),
            "failed_attempts_with_gpu_below_guard": sum(r["resources"]["gpu_memory_free_mib_min_sampled"] < 512 for r in failed),
            "all_failed_attempts_error_type": dict(Counter(r["error"] for r in failed)),
            "minimum_sampled_ram_available_gib": min(r["resources"]["system_ram_available_gib_min_sampled"] for r in telemetry + study),
            "declared_real_tool_eligible_n": len(eligible),
            "declared_real_tool_correct_requires_parse_and_no_error": sum(r["tool_correct"] and r["parse_success"] and not r["error"] for r in eligible),
            "unit_validation_expected_conversion": unit_counts,
            "numeric_quality_status": "RESOURCE_CONFOUNDED_NOT_MODEL_QUALITY" if not any(not r["error"] and r.get("stream_complete") for r in study) else "DEV_TYPED_FORMULAS_PROVIDED_MODEL_ONLY",
        }
    common = set(r["task_id"] for r in records if r["model_key"] == KEYS[0] and r["kind"] == "telemetry" and not r["error"] and r.get("stream_complete"))
    common &= set(r["task_id"] for r in records if r["model_key"] == KEYS[1] and r["kind"] == "telemetry" and not r["error"] and r.get("stream_complete"))
    paired = {}
    for model in KEYS:
        own = [r for r in records if r["model_key"] == model and r["kind"] == "telemetry" and r["task_id"] in common]
        paired[model] = distribution([r["latency_s"] for r in own], unit="s")
    return {
        "status": "INDEPENDENT_QA_APPEND_ONLY", "run_id": RUN, "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha(plan_path), "checks": checks, "all_integrity_checks_pass": all(checks.values()),
        "executed_code_hash_checks": code_hashes, "models": model_checks,
        "paired_success_latency": {"n_common_success": len(common), "models": paired,
            "p50_ratio_q27_over_q9": paired[KEYS[1]]["p50"] / paired[KEYS[0]]["p50"],
            "status": "CONDITIONAL_SUCCESS_BIASED_SUBSET_NOT_FULL40_SYSTEMS_EQUIVALENCE"},
        "defects_and_limitations": [
            {"id": "GUARD_FAILURES_MIXED_IN_LATENCY", "severity": "MATERIAL", "correction": "Do not use all-attempt Q27 latency as successful inference latency. Show failures and conditional common-success subset separately."},
            {"id": "Q27_STUDY_C_ALL_GUARD_FAILED", "severity": "MATERIAL", "correction": "0/27 is end-to-end operational outcome, not numerical reasoning measurement. No Q27 arithmetic comparison possible."},
            {"id": "NULL_TOOL_FAILURE_COMPONENT_CREDIT", "severity": "MEASUREMENT", "correction": "Count actual declared-tool matches only among 26 tool-eligible cases and require parse-success/error-free response; failed empty unsupported output cannot earn tool credit."},
            {"id": "UNIT_CATEGORY_DENOMINATOR_MISMATCH", "severity": "MEASUREMENT", "correction": "Original invalid_units_n==0 derives nonexistent category units. Overlay unit-validation N using expected reason_code EXPLICIT_CONVERSION_REQUIRED."},
            {"id": "TWO_LOAD_P99_AND_FORTY_REQUEST_P99", "severity": "PRECISION", "correction": "Two-load/two-warmup p90/p95/p99 are not meaningful tail characterization. Request p99 at N40 is extremely sparse; prefer p50/p95 with N."},
            {"id": "PROCESS_BASENAME_RSS_SCOPE", "severity": "DISCLOSURE", "correction": "RSS is a basename allowlisted sum of working sets, without lineage. It may include unrelated llama-server and double-count shared pages; never call per-model allocated RAM."},
            {"id": "APP_VERSION_FROM_HISTORICAL_INVENTORY", "severity": "DISCLOSURE", "correction": "LMStudio app version copied from historical inventory; current default runtime listed but actual per-model runtime UNKNOWN. Link root live version check if available."},
            {"id": "RECORD_UTC_PRE_RESOURCE_OBSERVATION", "severity": "DISCLOSURE", "correction": "request_utc recorded before before/sampler preparation snapshots; latency starts immediately before HTTP. It excludes instrumentation setup cost; do not subtract these UTCs to claim HTTP timing."},
            {"id": "SINGLE_CONTROLLER_CONTINUED_AFTER_GUARD", "severity": "IMPLEMENTATION", "correction": "Per-request guard prevents continued response but parent only checks resource_errors, not tripped flag, so later scheduled requests continued. Preserve original evidence; future runner should abort block on resource trip."},
        ],
        "source_hashes": {p.relative_to(root).as_posix(): sha(p) for p in (plan_path, raw_path, safe_path, safe/"completion_receipt.json", safe/"study_c_scores.jsonl", safe/"load_receipts.json", safe/"systems_summary.json", safe/"study_c_summary.json", root/"data/study_c_technical_20261003.json", Path(__file__))},
        "private_test_run": False, "new_inference_calls": 0, "original_files_modified": False,
    }


def main():
    result = inspect()
    path = ROOT / "results/20261003_resource_session/independent_systems_qa.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2); handle.write("\n")
    print(json.dumps({"qa_path": str(path), "integrity_pass": result["all_integrity_checks_pass"],
                      "failed_checks": [k for k,v in result["checks"].items() if not v], "models": result["models"],
                      "paired_success_latency": result["paired_success_latency"]}, ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    main()

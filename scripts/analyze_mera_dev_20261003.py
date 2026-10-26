# SPDX-License-Identifier: Apache-2.0
"""Analyze public DEV only; no inference, uploads, hidden gold or HOME150 rewrite."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_adapter_20261003 import (
    diagnostic_set_scores, ensure_restricted_path, isolate_dev_references,
    official_scores, route_local, sha256_bytes,
)


def policy_replay(local_rows, cloud_rows, references, options, *, threshold):
    """A cached counterfactual, never a claim of actual avoided requests."""
    if set(local_rows) != set(cloud_rows) or not local_rows:
        raise ValueError("A complete paired development screen is required")
    records = []
    for item_id, local in local_rows.items():
        signal = {k: local.get(k) for k in ("valid_options", "option_token_confidence", "error")}
        route = route_local(signal, threshold=threshold)
        chosen = local if route == "local" else cloud_rows[item_id]
        strict = diagnostic_set_scores(references[item_id], chosen["prediction"], options[item_id])
        compatible = official_scores(references[item_id], chosen["prediction"])
        records.append({"item_id": item_id, "route": route, "set_correct": strict["set_exact_match"],
                        "set_f1": strict["set_f1"], "compatible_exact_match": compatible["exact_match"],
                        "compatible_f1": compatible["f1"],
                        "simulated_latency_ms": local["latency_ms"] + (cloud_rows[item_id]["latency_ms"] if route == "cloud" else 0),
                        "simulated_remote_cost_usd": cloud_rows[item_id]["cost_usd_estimate"] if route == "cloud" else 0})
    remote = sum(x["route"] == "cloud" for x in records)
    known = [x["simulated_remote_cost_usd"] for x in records if x["simulated_remote_cost_usd"] is not None]
    return {"status": "COUNTERFACTUAL_CACHED_DEV_REPLAY", "n": len(records), "threshold": threshold,
            "local_generation_calls_if_deployed": len(records), "cloud_generation_calls_if_deployed": remote,
            "hosted_router_calls_if_deployed": 0, "cloud_task_fraction_if_deployed": remote / len(records),
            "hosted_task_fraction_if_deployed": remote / len(records), "hosted_requests_per_task_if_deployed": remote / len(records),
            "local_resolution_fraction_if_deployed": 1 - remote / len(records),
            "relative_cloud_call_reduction_if_deployed": 1 - remote / len(records),
            "diagnostic_set_exact_match": statistics.mean(x["set_correct"] for x in records if x["set_correct"] is not None),
            "diagnostic_set_f1": statistics.mean(x["set_f1"] for x in records if x["set_f1"] is not None),
            "official_compatible_normalized_exact_match": statistics.mean(x["compatible_exact_match"] for x in records),
            "official_compatible_normalized_f1": statistics.mean(x["compatible_f1"] for x in records),
            "simulated_mean_latency_ms": statistics.mean(x["simulated_latency_ms"] for x in records),
            "simulated_known_cost_usd": sum(known), "simulated_unknown_cost_n": len(records) - len(known),
            "actual_requests_saved_in_this_screen": 0, "quality_noninferiority_established": False,
            "per_item": records}


def run(study, dev_rows):
    study = (ROOT / study).resolve()
    if not study.is_relative_to(ROOT / "results"):
        raise ValueError("Use the separate Study B directory")
    dev_rows = ensure_restricted_path(dev_rows, ROOT)
    items, references = isolate_dev_references(json.loads(dev_rows.read_text(encoding="utf-8")))
    options = {i.item_id: i.options for i in items}
    restricted = ensure_restricted_path(ROOT / ".runtime/mera" / study.name, ROOT)
    manifests = {p.name.removesuffix("_dev_manifest.json"): json.loads(p.read_text(encoding="utf-8"))
                 for p in study.glob("*_dev_manifest.json")}
    local_name, cloud_name = "gemma-4-26b-a4b-it", "mercury-2_instant-256"
    predictions = {}
    for name in manifests:
        rows = [json.loads(x) for x in (restricted / (name + "_raw.jsonl")).read_text(encoding="utf-8").splitlines() if x]
        if any(r["split"] != "dev" for r in rows):
            raise ValueError("TEST records cannot enter a DEV analysis")
        if len({r["item_id"] for r in rows}) != len(rows):
            raise ValueError("Duplicate measured DEV ID")
        predictions[name] = {r["item_id"]: r for r in rows}
    if len(predictions.get(local_name, {})) != 60 or len(predictions.get(cloud_name, {})) != 60:
        raise ValueError("The complete selected local/cloud screen is unavailable")
    grid = [None, .5, .7, .8, .9, .95, .98, .99, 1.0]
    replays = [policy_replay(predictions[local_name], predictions[cloud_name], references, options, threshold=t) for t in grid]
    measurements = []
    for name, rows in predictions.items():
        for item_id, row in rows.items():
            strict = diagnostic_set_scores(references[item_id], row["prediction"], options[item_id])
            original = official_scores(references[item_id], row["prediction_raw"].lstrip())
            normalized = official_scores(references[item_id], row["prediction"])
            raw_choice = (row.get("raw") or {}).get("choices", [{}])[0]
            measurements.append({"model_profile": name, "item_id": item_id, "split": "dev",
                "set_correct": strict["set_exact_match"], "set_f1": strict["set_f1"],
                "official_compatible_raw_exact_match": original["exact_match"],
                "official_compatible_raw_f1": original["f1"],
                "official_compatible_normalized_exact_match": normalized["exact_match"],
                "official_compatible_normalized_f1": normalized["f1"],
                "valid_options": row["valid_options"], "strict_format": row["strict_format"],
                "option_token_confidence": row["option_token_confidence"] if row["valid_options"] else None,
                "latency_ms": row["latency_ms"], "cost_usd_estimate": row["cost_usd_estimate"],
                "prompt_tokens": row["usage"].get("prompt_tokens"), "completion_tokens": row["usage"].get("completion_tokens"),
                "reasoning_tokens": row["usage"].get("completion_tokens_details", {}).get("reasoning_tokens"),
                "finish_reason": raw_choice.get("finish_reason"), "error": row["error"]})
    costs = [r["cost_usd_estimate"] for r in measurements if r["model_profile"].startswith("mercury") and r["cost_usd_estimate"] is not None]
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "study_id": study.name,
        "status": "DEV_ONLY_EXPLORATORY_NOT_CONFIRMATORY", "analysis_code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "analysis_source_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "input_manifest_sha256": {p.name: sha256_bytes(p.read_bytes()) for p in study.glob("*_dev_manifest.json")},
        "raw_source_sha256": {k: manifests[k]["raw_sha256"] for k in manifests},
        "model_profiles": {k: {"summary": v["summary"], "actual_calls": v["actual_calls"],
                               "resource_stop": v.get("resource_stop"), "inference_baseline_commit": v["code_commit"],
                               "executed_source_hashes": v["uncommitted_source_hashes"]} for k, v in manifests.items()},
        "selected_local_candidate": local_name, "cloud_candidate": "mercury-2", "cloud_primary_selection_status": "NOT_FROZEN",
        "cloud_profile_limitations": "medium128 is output-budget failure; instant256 is valid-format but weak small-DEV baseline; no calibrated strong cloud comparison established",
        "partial_local_not_ranked": "qwen3.8-27b: resource stop17/60; no repeated requests",
        "candidate_router_status": "REFERENCE_FREE_RULES_EXPLORATORY_ONLY; no learned router",
        "counterfactual_grid": replays,
        "actual_inference_accounting": {"local_requests": sum(v["actual_calls"] for k, v in manifests.items() if not k.startswith("mercury")),
                                      "hosted_generation_requests": sum(v["actual_calls"] for k, v in manifests.items() if k.startswith("mercury")),
                                      "hosted_router_requests": 0, "mera_scoring_submissions": 0,
                                      "known_remote_cost_usd_estimate": sum(costs),
                                      "provider_invoice_available": False, "actual_requests_saved_by_cascade": 0},
        "MERA_PRIVATE_TEST_READY": "NO", "private_test_run": False, "official_remote_scores": None,
        "paired_confirmatory_ci": None, "metric_server_version": "UNVERIFIED",
        "blockers": ["Official published SQuAD scorer removes option A; server behavior/version requires clarification",
                     "Final cloud profile and routing threshold not frozen; small DEV screens not independent test",
                     "Human approval of RQ/design and interpretation pending", "No authorization for external MERA submission in this session",
                     "Submission service acceptance/per-item correctness capability unverified"],
        "data_rights": "USE_WITH_RESTRICTIONS; source questions/full outputs DO_NOT_REDISTRIBUTE",
        "recommended_paper_now": "A", "target_paper_after_confirmatory_resolution": "B", "split_into_two_empirical_papers": "NOT_JUSTIFIED"}
    for path, content in [(study / "dev_analysis.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
                          (study / "dev_measurements_only.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in measurements))]:
        with path.open("x", encoding="utf-8") as f: f.write(content)
    with (study / "dev_use_ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": result["created_utc"], "purpose": "cached_DEV_metric_check_and_reference_free_threshold_grid",
                           "inference_calls": 0, "new_private_scores": 0, "source_ids": sorted(predictions[local_name]),
                           "status": "EXPLORATORY_NO_PRIMARY_THRESHOLD_SELECTED"}) + "\n")
    print(json.dumps({"study": study.name, "accounting": result["actual_inference_accounting"],
                      "format_rule_replay": {k: v for k, v in replays[0].items() if k != "per_item"}}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", required=True, type=Path)
    parser.add_argument("--dev-rows", required=True, type=Path)
    args = parser.parse_args(); run(args.study_dir, args.dev_rows)

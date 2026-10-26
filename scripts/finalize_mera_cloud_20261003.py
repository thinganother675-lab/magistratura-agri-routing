# SPDX-License-Identifier: Apache-2.0
"""Offline aggregate of three bounded Mercury profiles; never inference/TEST."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_screen_analysis_20261003 import digest, validate_claims


def write_new(path, obj):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")


def run():
    diagnostic_path = ROOT / "results/20261003_cloud_baseline_7c019d4a/diagnostic_corrected.json"
    budget = ROOT / "results/20261003_cloud_budget_only_c1184a27"
    combined_path = budget / "mercury25_instant512_t05_dev60_combined.json"
    diagnostics = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    combined = json.loads(combined_path.read_text(encoding="utf-8"))
    rows = combined["rows"]
    if len(rows) != 60 or len({r["item_id"] for r in rows}) != 60 or any(r.get("split") != "dev" for r in rows):
        raise ValueError("Only the full attempted common DEV60 cloud data is accepted")
    profiles = diagnostics["profiles"]
    profile512 = {"summary": combined["summary"], "known_cost_usd_estimate": sum(r["cost_usd_estimate"] or 0 for r in rows),
                  "execution_status": "ATTEMPT_COVERAGE_COMPLETE_WITH_FAILURES",
                  "unknown_cost_calls": sum(r["cost_usd_estimate"] is None for r in rows),
                  "hidden_reasoning_tokens": sum(r.get("reasoning_tokens") or 0 for r in rows),
                  "returned_model_ids": sorted({r["returned_model"] for r in rows if r.get("returned_model")}),
                  "requested_model": "mercury-2.5", "temperature": .5, "reasoning_effort": "instant", "max_completion_tokens": 512,
                  "operational_dev12_gate_passed": True, "operational_full60_error_free": combined["summary"]["complete_coverage"],
                  "primary_selection_before_extension_sha256": digest((budget / "cloud_primary_frozen.json").read_bytes())}
    for p in profiles.values():
        p["hidden_reasoning_tokens"] = sum(r.get("reasoning_tokens") or 0 for r in p["rows"])
    profiles["mercury25_instant512_t05"] = profile512
    extension_manifest = budget / "mercury25_instant512_t05_dev60_manifest.json"
    write_new(budget / "manifest_status_correction.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "status": "DEV",
        "reason": "Original executed cloud runner labelled all attempted48 COMPLETE despite4 length errors; original manifest preserved. Safe row scoring already zero, metrics unchanged.",
        "original_extension_manifest_sha256": digest(extension_manifest.read_bytes()),
        "original_extension_status": json.loads(extension_manifest.read_text(encoding="utf-8"))["status"],
        "corrected_extension_status": "ATTEMPT_COVERAGE_COMPLETE_WITH_FAILURES", "extension_attempts": 48,
        "extension_successful_completed": 44, "combined_attempts": 60, "combined_successful_completed": 56,
        "metric_values_changed": False, "private_test_run": False})
    result = {"run_id": "20261003_cloud_development", "status": "DEV", "private_test_run": False,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "analysis_source_sha256": digest(Path(__file__).read_bytes()),
              "source_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p.read_bytes()) for p in (diagnostic_path, combined_path)},
              "profiles": {name: {k: v for k, v in p.items() if k != "rows"} for name, p in profiles.items()},
              "actual_hosted_generation_attempts": sum(p["summary"]["n_attempted"] for p in profiles.values()),
              "actual_received_responses": sum(p["summary"]["n_response_received"] for p in profiles.values()),
              "actual_completed_responses": sum(p["summary"]["n_completed"] for p in profiles.values()),
              "known_cost_usd_estimate": sum(p["known_cost_usd_estimate"] for p in profiles.values()),
              "unknown_cost_calls": sum(p["unknown_cost_calls"] for p in profiles.values()),
              "provider_invoice_available": False, "retries": 0,
              "primary_cloud_recommendation": "mercury-2.5 direct Inception instant512 temperature.5",
              "primary_cloud_status": "PROVISIONAL_DEV_REFERENCE_NOT_PRIVATE_TEST_READY",
              "reason": "Legitimate direct provider ID, operational12 gate frozen before extension, common attempted60; full60 has4 length failures requiring prospective protocol decision, no more tuning here",
              "confidence_logprobs": "NOT_MEASURED", "MERA_scoring_submissions": 0,
              "official_server_metric": "UNKNOWN", "MERA_PRIVATE_TEST_READY": "NO",
              "rights": "USE_WITH_RESTRICTIONS", "full293_cloud_run": False,
              "OpenRouter_supplement": {"status": "NOT_RUN_FREE_QUOTA_GUARD", "read_only_metadata_requests": 3,
                "quota_remaining": 19, "quota_limit": 50, "quota_used": 31, "key_limit_usd": 0,
                "include_byok_in_limit": True, "privacy_filtered_model_eligible": True,
                "model_id": "qwen/qwen3.8-27b:free", "canonical_slug": "qwen/qwen3.8-27b-20260814",
                "provider_tag": "modelrun/fp4", "quantization": "fp4", "metadata_time_utc": "2026-10-03T08:38:33.010164+00:00",
                "metadata_source": "targeted current /key + authenticated /models/user + one /models/<exactID>/endpoints; inlinePython allowlisted existing credential; no settings/inference",
                "inference_calls": 0, "reason": "remaining19 cannot support planned sameDEV60 or a bounded2642 TEST baseline; no account/key/limit changes"}}
    path = budget / "cloud_development_analysis.json"; write_new(path, result)
    claims = []
    def add(id_, pointer, value, text):
        claims.append({"claim_id": id_, "statement": text, "study_run_id": result["run_id"],
                       "data_path": str(path.relative_to(ROOT)).replace("\\", "/"), "analysis_field": pointer,
                       "value": value, "code_commit": result["code_commit"], "data_sha256": digest(path.read_bytes()), "status": "DEV"})
    for key in ("actual_hosted_generation_attempts", "actual_received_responses", "actual_completed_responses", "known_cost_usd_estimate", "unknown_cost_calls", "primary_cloud_recommendation", "primary_cloud_status"):
        add("cloud_" + key, "/" + key, result[key], "Bounded Mercury DEV: " + key)
    for name, p in result["profiles"].items():
        for key in ("n_expected", "n_attempted", "n_completed", "n_response_received", "n_scored", "strict_em_count", "strict_set_em", "strict_set_f1", "invalid_output", "errors", "timeouts", "latency_p50_s", "latency_p95_s", "input_tokens", "output_tokens"):
            add("cloud_" + name + "_" + key, "/profiles/" + name + "/summary/" + key, p["summary"][key], name + " public DEV " + key)
        for key in ("hidden_reasoning_tokens", "known_cost_usd_estimate", "unknown_cost_calls"):
            add("cloud_" + name + "_" + key, "/profiles/" + name + "/" + key, p[key], name + " public DEV " + key)
    add("openrouter_remaining_quota_guard", "/OpenRouter_supplement/quota_remaining", 19, "Read-only OpenRouter quota preflight prevents common60 inference")
    write_new(ROOT / "manuscript/CLAIM_PROVENANCE_CLOUD_BASELINE_20261003.json", {"run_id": result["run_id"], "claims": claims, "validation": validate_claims(claims, ROOT), "human_confirmation": "PENDING"})
    print(json.dumps({k: result[k] for k in ("actual_hosted_generation_attempts", "actual_received_responses", "actual_completed_responses", "known_cost_usd_estimate", "unknown_cost_calls", "primary_cloud_status")}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()

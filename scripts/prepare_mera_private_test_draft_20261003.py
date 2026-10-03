# SPDX-License-Identifier: Apache-2.0
"""Prepare an evidence-linked TEST draft and inspect readiness, never submit."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_private_test_guard_20261003 import readiness
from agro_route.mera_screen_analysis_20261003 import digest, validate_claims
from analyze_mera_local_screen_20261003 import load_protocol


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(study_dir, cloud_analysis):
    safe, cloud_path = (ROOT / study_dir).resolve(), (ROOT / cloud_analysis).resolve()
    if not safe.is_relative_to(ROOT / "results") or not cloud_path.is_relative_to(ROOT / "results"):
        raise ValueError("Only existing private workspace result artifacts may be used")
    local_path = safe / "final_analysis.json"
    local, cloud = read(local_path), read(cloud_path)
    protocol, _ = load_protocol(safe)
    if local["status"] != "DEV" or local["private_test_run"] is not False or cloud["status"] != "DEV" or cloud["private_test_run"] is not False:
        raise ValueError("Only DEV evidence and unrun TEST may enter this draft")
    model_key = local["primary_local"]
    profile = next(p for p in local["stage2"] if p["model_key"] == model_key)
    if profile["status"] != "COMPLETE" or profile["summary"]["complete_coverage"] is not True:
        raise ValueError("Primary local needs completed comparable full DEV evidence")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    utc = datetime.now(timezone.utc).isoformat()
    def gate(approved, rationale, path=None):
        item = {"approved": approved, "rationale": rationale, "authority": "AGENT_DEV_EVIDENCE_ONLY" if approved else "PENDING"}
        if path:
            item.update(evidence_path=path.relative_to(ROOT).as_posix(), evidence_sha256=digest(path.read_bytes()))
        return item
    draft = {
        "protocol_id": "mera_private_test_draft_20261003", "protocol_status": "DRAFT_NOT_FROZEN",
        "created_utc": utc, "preparation_code_commit": commit,
        "preparation_source_sha256": digest(Path(__file__).read_bytes()),
        "dataset": "MERA-evaluation/ruTXTAgroBench", "dataset_revision": protocol["source_revision"],
        "planned_private_test_inputs": 2642, "private_test_run": False, "test_gold_dependency": False,
        "evidence_classification": "DEV", "human_review": False,
        "source_evidence": {local_path.relative_to(ROOT).as_posix(): digest(local_path.read_bytes()), cloud_path.relative_to(ROOT).as_posix(): digest(cloud_path.read_bytes())},
        "primary_local": {
            "model_key": model_key, "quantization_backend_label": profile["quantization"],
            "status": "AGENT_DEV_RECOMMENDATION_PENDING_AUTHORS",
            "selection": "Highest STRICT_SET_EM on parseable original DEV293 references; fullDEV includes screen60 and is not independent validation",
            "quality_evidence": {"n_scored": profile["summary"]["n_scored"], "strict_set_em": profile["summary"]["strict_set_em"], "strict_set_f1": profile["summary"]["strict_set_f1"]},
            "proposed_parameters": protocol["request_parameters"], "context_length": protocol["context_length"],
            "reasoning_effort_requested": profile["reasoning_effort_requested"],
            "requested_gpu_ratio": profile["gpu_requested"], "actual_gpu_layers": profile["actual_gpu_layers"],
            "resource_policy": {"sequential": True, "fixed_reload_every_n": protocol["fixed_reload_every_n"], "parallel": 1, "guards_must_remain_enabled": True},
        },
        "primary_cloud": {
            "model_id": "mercury-2.5", "provider": "Inception Labs direct", "endpoint": "https://api.inceptionlabs.ai/v1/chat/completions",
            "status": "PROVISIONAL_DEV_REFERENCE_NOT_FROZEN", "reasoning_effort": "instant",
            "temperature": .5, "max_tokens": 512, "response_contract": "JSON object with choices array of Latin option letters",
            "limitation": "CommonDEV60:56/60 error-free completions, four length truncations; protocol operational stability and provider weight revision unresolved",
            "selection_rationale": "Direct documented model/API identity chosen by operational12 gate before48 extension, not by privateTEST score",
            "full_dev293_run": False,
        },
        "routing_rule": {
            "status": "PROPOSAL_NOT_FROZEN", "fallback": "Unparseable choice-set output, transport error, or explicit abstention -> cloud",
            "confidence_threshold": None, "reference_fields_allowed_at_decision": False,
            "development_grid": [None, .5, .7, .8, .9, .95, .98, .99, 1.],
            "exploratory_dev_em_margin": .05, "margin_human_confirmation": "PENDING",
            "rationale": "Primary local validity-only DEV60 replay is trivially local-only; confidence benefit and live cascade savings not established",
            "freeze_required_before_test": True,
        },
        "scoring_policy": {"development": "STRICT_SET_EM and question-level STRICT_SET_F1 with original gold preserved", "production_server_status": "UNKNOWN", "unresolved_reference_policy": "No semantic repair; report original parseability issues and denominators", "official_score_must_remain_separate": True},
        "rights": {"status": "USE_WITH_RESTRICTIONS", "benchmark_content_redistribution": "BLOCKED_PENDING_OFFICIAL_TERMS", "raw_outputs": "IGNORED_PRIVATE_RUNTIME_ONLY"},
        "gates": {
            "primary_local_selected": gate(True, "Completed comparable fullDEV supports agent selection; this is not author approval", local_path),
            "primary_cloud_selected": gate(False, "Provisional direct baseline has four truncations; no author-confirmed stable frozen primary", cloud_path),
            "routing_rule_frozen": gate(False, "DEV proposal/grid exists, margin and final rule require author review", local_path),
            "server_scoring_resolved": gate(False, "Public option-A normalizer defect reproduced; production/server scorer version is undocumented"),
            "official_workflow_verified": gate(False, "Actual private submission acceptance/scoring/results workflow has not been exercised or authorized"),
            "content_rights_understood": gate(False, "Dataset content and raw-output terms remain USE_WITH_RESTRICTIONS"),
            "antoniy_approval": gate(False, "No direct human protocol approval recorded"),
            "denis_approval": gate(False, "No direct human protocol approval recorded"),
            "explicit_submission_authorization": gate(False, "No separate user authorization for privateTEST submission/scoring"),
        },
        "next_actions": ["Authors review DEV model/rule recommendations and approve a stable cloud configuration", "Send prepared maintainer question only with explicit messaging authorization", "Resolve scoring/rights and verify official workflow", "Freeze agreed protocol before any privateTEST exposure", "Obtain separate explicit TEST submission authorization"],
    }
    draft_path = ROOT / "experiments/mera_private_test_protocol_draft_20261003.json"
    write_new(draft_path, draft)
    inspected = readiness(draft, ROOT)
    if inspected["MERA_PRIVATE_TEST_READY"] or inspected["inference_permitted"] or inspected["submission_permitted"]:
        raise ValueError("A pending development draft must remain blocked")
    receipt = {"status": "DEV_READINESS_INSPECTION", "created_utc": utc, "code_commit": commit,
               "protocol_path": draft_path.relative_to(ROOT).as_posix(), "protocol_sha256": digest(draft_path.read_bytes()),
               "guard_source_sha256": digest((ROOT / "src/agro_route/mera_private_test_guard_20261003.py").read_bytes()),
               "private_test_run": False, "test_gold_dependency": False, **inspected}
    receipt_path = ROOT / "results/20261003_local_screen_session/private_test_readiness.json"
    write_new(receipt_path, receipt)
    claims = []
    for name in ("MERA_PRIVATE_TEST_READY", "blockers", "inference_permitted", "submission_permitted", "private_test_run", "test_gold_dependency"):
        claims.append({"claim_id": "private_test_readiness_" + name, "statement": "Fail-closed pending draft readiness inspection: " + name,
                       "study_run_id": "20261003_dev_protocol_readiness", "data_path": receipt_path.relative_to(ROOT).as_posix(),
                       "analysis_field": "/" + name, "value": receipt[name], "code_commit": commit,
                       "data_sha256": digest(receipt_path.read_bytes()), "status": "DEV"})
    write_new(ROOT / "manuscript/CLAIM_PROVENANCE_PRIVATE_TEST_READINESS_20261003.json", {"status": "DEV", "claims": claims, "validation": validate_claims(claims, ROOT), "human_confirmation": "PENDING"})
    print(json.dumps({"MERA_PRIVATE_TEST_READY": inspected["MERA_PRIVATE_TEST_READY"], "blockers": inspected["blockers"], "protocol": str(draft_path)}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--cloud-analysis", type=Path, required=True)
    args = parser.parse_args()
    main(args.study_dir, args.cloud_analysis)

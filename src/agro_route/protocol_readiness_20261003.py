# SPDX-License-Identifier: Apache-2.0
"""Read-only structural readiness guard; no provider calls and no freeze writes.

Passing checks does not independently establish scientific truth or human
identity. Evidence and approval records remain human research responsibilities.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

GATES = (
    "source_rights_complete", "source_groups_finalized", "translations_grouped",
    "historical_overlap_excluded", "semantic_overlap_review_complete",
    "two_human_reviews_complete", "adjudication_complete", "domain_expert_cases_resolved",
    "ask_abstain_evidence_rubric_finalized", "scorer_finalized_on_dev",
    "routing_methods_finalized_on_dev", "public_payload_oracle_audit_passed",
    "group_adequacy_and_uncertainty_approved", "margin_and_hypotheses_justified",
    "runtime_versions_and_settings_verified", "cost_and_retry_guards_verified",
    "measurement_and_analysis_plan_finalized",
)
ARTIFACT_ROLES = (
    "dataset", "dataset_manifest", "groups_manifest", "human_adjudicated_gold",
    "human_review_provenance", "rights_audit", "overlap_audit", "group_adequacy_plan",
    "scorer_code", "router_code", "public_payload_audit", "prompts_manifest",
    "runtime_manifest", "measurement_analysis_plan", "hypothesis_margin_justification",
)
FINAL_FIELDS = (
    "dataset_manifest_path", "dataset_sha256", "group_ids", "prompts", "model_ids",
    "provider_versions", "local_quantization", "tools", "router_questions", "scoring",
    "retry_policy", "latency_methodology", "cost_accounting", "total_external_accounting",
    "abstention_scoring", "primary_hypotheses", "statistical_test", "margin", "success_conditions",
)


def validate_readiness(protocol, root):
    """Return blockers; changing ready/status flags cannot promote an empty draft."""
    blockers = []
    if not isinstance(protocol, dict):
        return {"ready_for_freeze": False, "inference_permitted": False, "blockers": ["invalid_protocol"]}
    if protocol.get("status") != "READY_FOR_FREEZE" or protocol.get("ready") is not True:
        blockers.append("not_ready_for_freeze")
    if protocol.get("protocol_state") != "NOT_FROZEN" or protocol.get("inference_state") != "NOT_RUN" or protocol.get("inference_run") is not False:
        blockers.append("must_be_unfrozen_and_unrun")
    if protocol.get("human_review") is not True:
        blockers.append("human_review_pending")
    gates = protocol.get("readiness_gates", {})
    if not isinstance(gates, dict):
        gates = {}
    blockers.extend("gate:" + gate for gate in GATES if gates.get(gate) is not True)
    finalized = protocol.get("finalized_fields", {})
    if not isinstance(finalized, dict):
        finalized = {}
    for field in FINAL_FIELDS:
        value = finalized.get(field)
        if value is None or value is False or value == [] or value == {} or (isinstance(value, str) and value.strip().upper() in {"", "PENDING", "TBD", "NOT_FINALIZED"}):
            blockers.append("unfinalized:" + field)
    group_ids = finalized.get("group_ids")
    if not isinstance(group_ids, list) or not group_ids or not all(isinstance(g, str) and g for g in group_ids) or len(set(group_ids)) != len(group_ids):
        blockers.append("invalid_group_ids")
    if not isinstance(finalized.get("dataset_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", finalized["dataset_sha256"]):
        blockers.append("invalid_dataset_hash")
    candidate = protocol.get("scorer_candidate", {})
    if not isinstance(candidate, dict) or candidate.get("dev_only") is not False or candidate.get("production_wired") is not True:
        blockers.append("candidate_dev_scorer_cannot_score_final")
    if protocol.get("gold_action_source") != "HUMAN_ADJUDICATED_TASK_EVIDENCE_NOT_NA":
        blockers.append("gold_action_evidence_unresolved")
    artifacts = protocol.get("freeze_evidence", [])
    if not isinstance(artifacts, list):
        artifacts = []
    by_role = {role: [item for item in artifacts if isinstance(item, dict) and item.get("role") == role] for role in ARTIFACT_ROLES}
    base = Path(root).resolve()
    for role, items in by_role.items():
        if len(items) != 1:
            blockers.append("evidence_missing_or_ambiguous:" + role)
            continue
        item = items[0]
        try:
            relative = item["path"]
            expected = item["sha256"]
            if not isinstance(relative, str) or Path(relative).is_absolute() or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError
            path = (base / relative).resolve()
            if not path.is_relative_to(base) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError
        except (KeyError, ValueError, OSError):
            blockers.append("evidence_hash_or_path_invalid:" + role)
    if len(by_role["dataset"]) == 1 and finalized.get("dataset_sha256") != by_role["dataset"][0].get("sha256"):
        blockers.append("dataset_hash_not_linked_to_evidence")
    if len(by_role["dataset_manifest"]) == 1 and finalized.get("dataset_manifest_path") != by_role["dataset_manifest"][0].get("path"):
        blockers.append("dataset_manifest_path_not_linked_to_evidence")
    return {"ready_for_freeze": not blockers, "inference_permitted": False,
            "validator_scope": "STRUCTURAL_AND_HASH_CHECK_ONLY_NOT_SCIENTIFIC_OR_IDENTITY_VERIFICATION",
            "blockers": sorted(set(blockers)),
            "next_state_if_ready": "Create a separate author-approved actual freeze artifact and execution guard before any inference"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = validate_readiness(json.loads(args.protocol.read_text(encoding="utf-8")), args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ready_for_freeze"] else 2)


if __name__ == "__main__":
    main()

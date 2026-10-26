# SPDX-License-Identifier: Apache-2.0
"""Fail-closed consistency checks for a metadata-only backup recommendation.

This validator checks recorded evidence state. It cannot establish legal rights,
expert label correctness, or absence of model pretraining contamination.
"""
from __future__ import annotations


READINESS_GATES = (
    "license_declaration_verified",
    "use_scope_compatible",
    "access_terms_satisfied",
    "files_acquired_and_hashed",
    "labels_schema_verified",
    "expert_provenance_documented",
    "scorer_locally_verified",
    "project_overlap_audit_complete",
    "model_prompt_protocol_frozen",
)


def assess_readiness(candidate: dict) -> dict:
    """Unknown, missing, and merely truthy values remain blockers."""
    gates = candidate.get("readiness_gates", {})
    blockers = [gate for gate in READINESS_GATES if gates.get(gate) is not True]
    if candidate.get("previous_project_model_use") is not False:
        blockers.append("previous_project_model_use_not_excluded")
    if candidate.get("license_state") not in {"DECLARED_CLEAR_WITH_ATTRIBUTION", "VERIFIED_SCOPED_PERMISSION"}:
        blockers.append("license_state_not_eligible")
    return {"status": "NOT_READY" if blockers else "READY", "blockers": blockers,
            "inference_permitted": not blockers, "scope": "RECORDED_STATE_CONSISTENCY_ONLY"}


def validate_research(audit: dict) -> list[str]:
    errors = []
    candidates = audit.get("candidates", [])
    selected = [row for row in candidates if row.get("selected_for_future") is True]
    if len(selected) != 1:
        errors.append("exactly_one_primary_backup_required")
    elif selected[0].get("candidate_id") != audit.get("primary_backup"):
        errors.append("primary_backup_identity_mismatch")
    for candidate in candidates:
        actual = assess_readiness(candidate)
        if candidate.get("status") != actual["status"]:
            errors.append(f"readiness_status_mismatch:{candidate.get('candidate_id')}")
        if candidate.get("inference_run") is not False:
            errors.append(f"unexpected_inference:{candidate.get('candidate_id')}")
    return errors

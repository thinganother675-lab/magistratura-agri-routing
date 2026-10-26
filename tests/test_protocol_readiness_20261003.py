# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path

import pytest

from agro_route.protocol_readiness_20261003 import ARTIFACT_ROLES, FINAL_FIELDS, GATES, validate_readiness

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "experiments/NEXT_CONFIRMATORY_DRAFT_20261003.json"


def test_real_draft_is_blocked_and_unfrozen_without_any_final_run():
    protocol = json.loads(DRAFT.read_text(encoding="utf-8"))
    report = validate_readiness(protocol, ROOT)
    assert protocol["status"] == "DATA_BLOCKED"
    assert protocol["protocol_state"] == "NOT_FROZEN" and protocol["inference_state"] == "NOT_RUN"
    assert protocol["human_review"] is False and protocol["ready"] is False
    assert not report["ready_for_freeze"] and not report["inference_permitted"]
    assert all(value is None for value in protocol["finalized_fields"].values())


def test_flipping_flags_cannot_promote_draft_to_freeze():
    protocol = json.loads(DRAFT.read_text(encoding="utf-8"))
    protocol.update(status="READY_FOR_FREEZE", ready=True, human_review=True)
    report = validate_readiness(protocol, ROOT)
    assert not report["ready_for_freeze"] and "candidate_dev_scorer_cannot_score_final" in report["blockers"]
    assert "evidence_missing_or_ambiguous:human_adjudicated_gold" in report["blockers"]


def structural_fixture(tmp_path):
    # Deliberately synthetic records test the structural guard, not real approval.
    file = tmp_path / "synthetic_fixture.txt"
    file.write_text("synthetic readiness hash fixture")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    p = {"status": "READY_FOR_FREEZE", "ready": True, "protocol_state": "NOT_FROZEN", "inference_state": "NOT_RUN", "inference_run": False, "human_review": True,
         "readiness_gates": {gate: True for gate in GATES}, "finalized_fields": {field: "synthetic_fixture_only" for field in FINAL_FIELDS},
         "scorer_candidate": {"dev_only": False, "production_wired": True}, "gold_action_source": "HUMAN_ADJUDICATED_TASK_EVIDENCE_NOT_NA",
         "freeze_evidence": [{"role": role, "path": file.name, "sha256": digest} for role in ARTIFACT_ROLES]}
    p["finalized_fields"].update(group_ids=["fixture_group"], dataset_sha256=digest, dataset_manifest_path=file.name)
    return p, file


def test_structural_success_never_itself_permits_inference(tmp_path):
    protocol, _ = structural_fixture(tmp_path)
    report = validate_readiness(protocol, tmp_path)
    assert report["ready_for_freeze"] and report["inference_permitted"] is False
    assert "NOT_SCIENTIFIC_OR_IDENTITY" in report["validator_scope"]


def test_changed_evidence_hash_and_missing_gate_fail_closed(tmp_path):
    protocol, file = structural_fixture(tmp_path)
    del protocol["readiness_gates"]["two_human_reviews_complete"]
    file.write_text("changed after purported hash lock")
    report = validate_readiness(protocol, tmp_path)
    assert not report["ready_for_freeze"]
    assert "gate:two_human_reviews_complete" in report["blockers"]
    assert "evidence_hash_or_path_invalid:dataset" in report["blockers"]


@pytest.mark.parametrize("bad_groups", [[{}], ["group", "group"], [None], "one_group", []])
def test_invalid_or_duplicate_source_groups_fail_closed(tmp_path, bad_groups):
    protocol, _ = structural_fixture(tmp_path)
    protocol["finalized_fields"]["group_ids"] = bad_groups
    assert not validate_readiness(protocol, tmp_path)["ready_for_freeze"]


def test_na_annotation_cannot_become_evidence_for_abstention(tmp_path):
    protocol, _ = structural_fixture(tmp_path)
    protocol["gold_action_source"] = "UPSTREAM_NA_CONVERTED_TO_ABSTAIN"
    assert "gold_action_evidence_unresolved" in validate_readiness(protocol, tmp_path)["blockers"]

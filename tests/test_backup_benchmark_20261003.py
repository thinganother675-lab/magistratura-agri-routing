# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from agro_route.backup_benchmark_audit_20261003 import (
    READINESS_GATES,
    assess_readiness,
    validate_research,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "results/20261003_backup_benchmark/research.json"
RECEIPTS = ROOT / "results/20261003_backup_benchmark/source_receipts.json"


def research():
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def selected():
    return next(row for row in research()["candidates"] if row["selected_for_future"])


def test_exactly_one_recommendation_is_still_unrun_and_not_ready():
    audit = research()
    assert validate_research(audit) == []
    assert audit["primary_backup"] == "bbk_english"
    assert sum(row["selected_for_future"] for row in audit["candidates"]) == 1
    assert not assess_readiness(selected())["inference_permitted"]
    assert audit["benchmark_rows_downloaded_this_session"] == 0
    assert audit["new_model_inference_calls"] == audit["new_paid_api_spend_usd"] == 0
    assert audit["access_conditions_accepted"] is False


def test_license_declaration_does_not_open_gate_or_certify_gold():
    candidate = selected()
    assert candidate["license"]["dataset_declaration"] == "CC-BY-4.0"
    assert candidate["readiness_gates"]["license_declaration_verified"] is True
    assert candidate["readiness_gates"]["access_terms_satisfied"] is False
    assert candidate["readiness_gates"]["labels_schema_verified"] is False
    assert candidate["labels"]["actual_file_values_verified"] is False
    assert candidate["size"]["rows_locally_verified"] is None


@pytest.mark.parametrize("gate", READINESS_GATES)
def test_missing_or_truthy_gate_is_not_validated_permission(gate):
    candidate = selected()
    candidate["readiness_gates"] = {item: True for item in READINESS_GATES}
    for value in (None, "True", 1, False):
        candidate["readiness_gates"][gate] = value
        result = assess_readiness(candidate)
        assert not result["inference_permitted"] and gate in result["blockers"]


def test_unknown_license_stays_blocked_even_with_all_other_gates():
    candidate = selected()
    candidate["readiness_gates"] = {gate: True for gate in READINESS_GATES}
    candidate["license_state"] = "UNKNOWN"
    result = assess_readiness(candidate)
    assert "license_state_not_eligible" in result["blockers"]
    assert result["status"] == "NOT_READY"


def test_previous_project_model_use_cannot_be_confirmatory_recommendation():
    candidate = selected()
    candidate["readiness_gates"] = {gate: True for gate in READINESS_GATES}
    for value in (True, None, "unknown"):
        candidate["previous_project_model_use"] = value
        assert "previous_project_model_use_not_excluded" in assess_readiness(candidate)["blockers"]


def test_promoting_ready_flag_or_selecting_second_backup_is_detected():
    audit = research()
    audit["candidates"][0]["status"] = "READY"
    assert any(error.startswith("readiness_status_mismatch") for error in validate_research(audit))
    audit = research()
    audit["candidates"][1]["selected_for_future"] = True
    assert "exactly_one_primary_backup_required" in validate_research(audit)


def test_receipts_preserve_gated_access_and_pinned_identity():
    receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in receipts["receipts"]}
    metadata = sources["bbk_metadata"]["metadata"]
    assert metadata["gated"] == "auto"
    assert sources["bbk_card"]["http_status"] == 401
    assert selected()["data_revision"] == metadata["sha"]
    assert selected()["scoring"]["frozen_code_revision"] == sources["bbk_code_tree"]["metadata"]["sha"]
    assert metadata["cardData"]["license"] == "cc-by-4.0"
    assert receipts["gates_accepted"] is False and receipts["credentials_read"] is False
    for row in receipts["receipts"]:
        assert row["authentication"] == "ANONYMOUS"
        assert urlsplit(row["url"]).scheme == "https"
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])


def test_metadata_projection_cannot_capture_auth_or_environment():
    spec = importlib.util.spec_from_file_location("backup_audit_sources", ROOT / "scripts/audit_backup_benchmark_sources_20261003.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = "synthetic" + "_secret"
    fake = {"id": "synthetic_public_metadata", "token": marker, "authorization": marker,
            "environment": {"api_key": marker}, "cardData": {"license": "cc-by-4.0", "token": marker},
            "rows": [{"question": "synthetic benchmark", "correct_answer": "synthetic gold"}]}
    projection = module.metadata_projection(copy.deepcopy(fake))
    assert projection == {"id": "synthetic_public_metadata", "cardData": {"license": "cc-by-4.0"}}
    assert "synthetic_secret" not in json.dumps(projection)
    assert "synthetic gold" not in json.dumps(projection)


def test_historical_awm_is_never_marked_as_fresh_independent_test():
    awm = next(row for row in research()["candidates"] if row["candidate_id"] == "awm_family")
    assert awm["previous_project_model_use"] is True
    assert awm["size"]["family_is_one_test"] is False
    assert not awm["selected_for_future"]
    assert not assess_readiness(awm)["inference_permitted"]

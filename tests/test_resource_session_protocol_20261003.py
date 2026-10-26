# SPDX-License-Identifier: Apache-2.0
"""Scientific draft guards: descriptive measurements cannot authorize holdout."""
import copy
import json
from pathlib import Path

from agro_route.protocol_readiness_20261003 import validate_readiness

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "experiments/next_resource_protocol_20261003.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_resource_draft_keeps_human_choices_unset_and_execution_unauthorized():
    protocol = read(DRAFT)
    assert protocol["status"] == "DRAFT_NOT_AUTHORIZED_CONFIRMATORY"
    assert protocol["authors"] == ["Antoniy Sarychev", "Denis Shesternin"]
    for field in ("quality_loss_margin_pp", "latency_budget_s", "whole_gpu_budget_mib", "whole_system_ram_budget_gib"):
        assert protocol[field] is None
    for field in ("independent_holdout", "private_test_run", "private_test_authorized", "submission_authorized", "publication_authorized", "denis_answers_filled"):
        assert protocol[field] is False
    assert type(protocol["new_paid_api_spend_authorized_usd"]) is int
    assert protocol["new_paid_api_spend_authorized_usd"] == 0


def test_resource_draft_cannot_be_used_as_an_executable_confirmatory_freeze():
    protocol = read(DRAFT)
    # Even a cosmetic promotion cannot bypass the project's existing evidence
    # guard. This summary draft supplies no acquired/hashed independent data,
    # scientific margin justification, or author review evidence.
    promoted = copy.deepcopy(protocol)
    promoted.update(status="READY_FOR_FREEZE", ready=True, human_review=True)
    result = validate_readiness(promoted, ROOT)
    assert result["inference_permitted"] is False
    assert result["ready_for_freeze"] is False
    assert {"unfinalized:margin", "evidence_missing_or_ambiguous:dataset", "evidence_missing_or_ambiguous:hypothesis_margin_justification"} <= set(result["blockers"])


def test_resource_evidence_roles_and_reused_study_profiles_remain_distinct():
    systems = read(ROOT / "results/20261003_systems_checkpoint0_v2/systems_corrected_aggregate.json")
    study = read(ROOT / "results/20261003_systems_checkpoint0_v2/study_c_corrected_aggregate.json")
    assert systems["status"] == "SYSTEMS_TELEMETRY"
    assert systems["historical_quality_status"] == "DEV"
    assert systems["quality_remeasured"] is False and systems["private_test_run"] is False
    assert study["status"] == "DEV" and study["private_test_run"] is False
    assert study["models"]["qwen3.5-9b"]["source_run_counts"] == {"20261003_systems_study_c_v1": 27}
    assert study["models"]["qwen3.8-27b"]["source_run_counts"] == {"20261003_systems_checkpoint0_v2": 27}
    for model in study["models"].values():
        assert model["declared_tool_executor_replay"]["status"] == "SIMULATED"
        assert model["declared_tool_executor_replay"]["live_model_tool_calls"] == 0

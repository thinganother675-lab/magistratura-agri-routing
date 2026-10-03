# SPDX-License-Identifier: Apache-2.0
import copy
import json

import pytest

from agro_route.mera_screen_analysis_20261003 import (
    confidence_diagnostic, digest, domain_and_cardinality, replay_cascade,
    route_signal, select_shortlist, summarize_measurements, validate_claims,
    validate_comparable,
    select_dev_routing_rule,
    wilson_em_interval, paired_correctness,
)


def measured(item, correct=1, valid=True, **extra):
    return {"item_id": item, "split": "dev", "domain": "synthetic discipline",
            "gold_valid": True, "gold_cardinality": 1, "em": correct,
            "f1": float(correct), "pred_valid": valid, "error": None,
            "latency_s": 1., "response_received": True, **extra}


def profile(key, em=.5, speed=1., gpu=1000., ram=10., n=60):
    return {"model_key": key, "stage": "dev60", "split": "dev", "status": "COMPLETE",
            "ids": list(range(n)), "dataset_revision": "synthetic", "source_sha256": "a",
            "selection_sha256": "b", "system_sha256": "c", "output_contract": "JSON choices",
            "score_policy": "Latin strict", "common_parameters_sha256": "d",
            "common_load_policy_sha256": "e", "reasoning_policy_sha256": "f",
            "summary": {"n_completed": n, "n_scored": n, "reference_issues": 0,
                        "complete_coverage": True,
                        "strict_set_em": em, "strict_set_f1": em, "latency_p50_s": speed,
                        "latency_p95_s": speed, "invalid_output": 0, "errors": 0,
                        "peak_gpu_mib": gpu, "peak_ram_used_gib": ram}}


def test_partial_higher_percentage_excluded_from_main_ranking():
    partial = profile("large", .9, n=17)
    partial["status"] = "PARTIAL_RESOURCE_GUARD"
    chosen = select_shortlist([partial, profile("complete", .5)], range(60))
    assert chosen["selected"] == ["complete"]
    assert "INCOMPLETE_COVERAGE" in chosen["excluded"]["large"]


def test_same_count_different_ids_or_prompt_is_incomparable():
    a, b = profile("a"), profile("b")
    b["ids"][-1] = 100
    assert "INCOMPLETE_COVERAGE" in validate_comparable([a, b], range(60))[1]["b"]
    b = profile("b"); b["system_sha256"] = "changed"
    assert "INCOMPARABLE_PROTOCOL" in validate_comparable([a, b], range(60))[1]["b"]


def test_altered_token_budget_or_load_context_cannot_rank_as_same_protocol():
    a, b = profile("a"), profile("b")
    b["common_parameters_sha256"] = "different_budget"
    assert "INCOMPARABLE_PROTOCOL" in validate_comparable([a, b], range(60))[1]["b"]
    b = profile("b"); b["common_load_policy_sha256"] = "different_context"
    assert "INCOMPARABLE_PROTOCOL" in validate_comparable([a, b], range(60))[1]["b"]


def test_all_attempted_but_failed_response_not_complete():
    row = measured(1, 0, valid=False, error={"type": "ReadTimeout"}, response_received=False)
    summary = summarize_measurements([row], [1])
    assert summary["n_attempted"] == 1 and summary["n_completed"] == 0
    assert summary["attempted_coverage"] is True and summary["complete"] is False


def test_pareto_keeps_quality_fast_small_and_does_not_pad_dominated():
    result = select_shortlist([profile("quality", .7, 3, 9000, 20),
                              profile("fast", .6, 1, 6000, 15),
                              profile("small", .3, 2, 1000, 10),
                              profile("dominated", .2, 5, 10000, 25)], range(60))
    assert set(result["selected"]) == {"quality", "fast", "small"}
    assert result["roles"]["BALANCED"] == "fast"
    assert result["roles"]["HIGH_QUALITY"] == "quality"
    assert "dominated" not in result["pareto_models"]


def test_unknown_resources_are_unknown_not_zero():
    a, b = profile("a"), profile("b", .6, 2)
    a["summary"]["peak_gpu_mib"] = None
    result = select_shortlist([a, b], range(60))
    assert result["resource_objectives_available"] is False
    assert "LOW_RESOURCE" not in result["roles"]


def test_unresolved_gold_excluded_with_all_n_denominator_explicit():
    rows = [measured(1), measured(2, gold_valid=False, gold_cardinality=None, em=None, f1=None)]
    result = summarize_measurements(rows, [1, 2])
    assert result["n_scored"] == 1 and result["reference_issues"] == 1
    assert result["strict_set_em"] == 1 and result["conservative_all_n_em"] == .5


@pytest.mark.parametrize("bad", ["question", "gold", "prediction_raw", "outputs", "choices"])
def test_safe_analysis_never_accepts_source_content(bad):
    with pytest.raises(ValueError, match="Restricted content"):
        summarize_measurements([measured(1, **{bad: "synthetic"})], [1])


def test_error_and_invalid_outputs_cannot_acquire_credit():
    with pytest.raises(ValueError, match="cannot score positively"):
        summarize_measurements([measured(1, valid=False)], [1])
    assert summarize_measurements([measured(1, 0, valid=False)], [1])["strict_set_em"] == 0


def test_duplicate_measurement_and_test_split_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_measurements([measured(1), measured(1)], [1])
    with pytest.raises(ValueError, match="Only public DEV"):
        summarize_measurements([measured(1, split="test")], [1])


def test_router_rejects_gold_and_falls_back_for_missing_probability():
    with pytest.raises(ValueError, match="observable signals"):
        route_signal({"pred_valid": True, "em": 1})
    assert route_signal({"pred_valid": True}) == "local"
    assert route_signal({"pred_valid": True}, threshold=.7) == "cloud"
    assert route_signal({"pred_valid": False, "option_token_confidence": .99}) == "cloud"


def test_saved_cascade_completeness_and_no_actual_savings_claim():
    local = [measured(1, 0, valid=False), measured(2)]
    cloud = [measured(1), measured(2, 0)]
    result = replay_cascade(local, cloud, [1, 2])
    assert result["strict_set_em"] == 1
    assert result["cloud_calls_if_deployed"] == 1
    assert result["relative_cloud_call_reduction_if_deployed"] == .5
    assert result["actual_requests_saved"] == 0 and result["status"] == "SIMULATED"
    with pytest.raises(ValueError, match="full common DEV coverage"):
        replay_cascade(local, cloud[:1], [1, 2])


def test_routing_decision_does_not_depend_on_gold_correctness():
    local = [measured(1, 0, valid=False), measured(2)]
    cloud = [measured(1), measured(2, 0)]
    count = replay_cascade(local, cloud, [1, 2])["cloud_calls_if_deployed"]
    swapped = copy.deepcopy(local)
    swapped[1].update(em=0, f1=0.)
    assert replay_cascade(swapped, cloud, [1, 2])["cloud_calls_if_deployed"] == count


def test_domains_are_exact_source_labels_and_single_multi_unresolved_separate():
    rows = [measured(1), measured(2, gold_cardinality=2),
            measured(3, gold_valid=False, gold_cardinality=None, em=None, f1=None)]
    result = domain_and_cardinality(rows)
    assert list(result["domains"]) == ["synthetic discipline"]
    assert set(result["answer_cardinality"]) == {"single", "multi", "unresolved_reference"}


def test_real_confidence_is_diagnostic_and_absent_not_fabricated():
    assert confidence_diagnostic([measured(1)])["status"] == "UNAVAILABLE"
    diagnostic = confidence_diagnostic([measured(1, option_token_confidence=.9),
                                        measured(2, 0, option_token_confidence=.1)])
    assert diagnostic["auc_correctness"] == 1
    assert diagnostic["calibrated_probability_of_correctness"] is False
    assert diagnostic["primary_threshold_selected"] is False


def test_routing_grid_trivial_local_success_does_not_invent_confidence_benefit():
    local = [measured(1, option_token_confidence=.9), measured(2, option_token_confidence=.9)]
    cloud = [measured(1), measured(2, 0)]
    result = select_dev_routing_rule(local, cloud, [1, 2])
    assert result["selected"]["threshold"] is None
    assert result["selected"]["cloud_calls_if_deployed"] == 0
    assert result["trivial_local_resolution_suffices_on_dev"] is True
    assert result["confidence_benefit_established"] is False
    assert result["confirmatory_noninferiority_established"] is False


def test_routing_grid_selects_threshold_on_dev_but_decisions_observable_only():
    local = [measured(1, 0, option_token_confidence=.1), measured(2, option_token_confidence=.9)]
    cloud = [measured(1), measured(2)]
    result = select_dev_routing_rule(local, cloud, [1, 2])
    assert result["selected"]["threshold"] == .5
    assert result["selected"]["cloud_calls_if_deployed"] == 1
    assert result["exploratory_em_margin"] == .05
    assert result["margin_human_confirmation"] == "PENDING"
    assert result["dev_observed_em_improvement_with_confidence"] is True
    assert result["confidence_benefit_established"] is False


def test_all_cloud_is_not_a_confidence_routing_benefit():
    result = select_dev_routing_rule([measured(1, 0, option_token_confidence=.1)], [measured(1)], [1])
    assert result["selected"]["cloud_fraction_if_deployed"] == 1
    assert result["dev_observed_em_improvement_with_confidence"] is False
    assert result["confidence_benefit_established"] is False


def test_wilson_descriptive_interval_handles_zero_all_and_no_reference():
    assert wilson_em_interval(0, 0)["lower"] is None
    zero, all_ = wilson_em_interval(0, 59), wilson_em_interval(59, 59)
    assert zero["lower"] == 0 and zero["upper"] == pytest.approx(.0611293705268)
    assert all_["upper"] == 1 and all_["lower"] == pytest.approx(1 - zero["upper"])
    assert all_["independent_confirmatory_inference"] is False
    with pytest.raises(ValueError, match="bounded integer"):
        wilson_em_interval(60, 59)


def test_paired_correctness_counts_discordance_and_preserves_unresolved():
    a = [measured(1), measured(2), measured(3, 0), measured(4, 0), measured(5, gold_valid=False, em=None, f1=None)]
    b = [measured(1), measured(2, 0), measured(3), measured(4, 0), measured(5, gold_valid=False, em=None, f1=None)]
    result = paired_correctness(a, b, range(1, 6))
    assert [result[k] for k in ("both_correct", "left_only_correct", "right_only_correct", "both_incorrect")] == [1, 1, 1, 1]
    assert result["n_scored"] == 4 and result["reference_issues"] == 1
    assert result["em_difference_left_minus_right"] == 0
    assert result["confirmatory_p_value"] is None and result["independent_holdout"] is False
    with pytest.raises(ValueError, match="full common"):
        paired_correctness(a[:-1], b, range(1, 6))


def test_provenance_integrity_and_dev_not_promoted(tmp_path):
    data = tmp_path / "result.json"
    data.write_text(json.dumps({"summary": {"n": 2}}), encoding="utf-8")
    claim = {"claim_id": "synthetic_n", "statement": "Synthetic count", "study_run_id": "synthetic_dev60",
             "data_path": data.name, "analysis_field": "/summary/n", "code_commit": "synthetic",
             "data_sha256": digest(data.read_bytes()), "status": "DEV", "value": 2}
    assert validate_claims([claim], tmp_path)["valid"]
    bad = {**claim, "status": "CONFIRMATORY", "private_test_authorized": True}
    with pytest.raises(ValueError, match="cannot be promoted"):
        validate_claims([bad], tmp_path)
    data.write_text(json.dumps({"summary": {"n": 3}}), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        validate_claims([claim], tmp_path)


def test_provenance_rejects_value_field_mismatch(tmp_path):
    data = tmp_path / "result.json"; data.write_text('{"n": 2}', encoding="utf-8")
    claim = {"claim_id": "n", "statement": "Synthetic", "study_run_id": "synthetic_dev",
             "data_path": data.name, "analysis_field": "/n", "code_commit": "synthetic",
             "data_sha256": digest(data.read_bytes()), "status": "DEV", "value": 3}
    with pytest.raises(ValueError, match="does not match"):
        validate_claims([claim], tmp_path)


@pytest.mark.parametrize("classification", ["DEV", "SIMULATED", "HISTORICAL"])
def test_provenance_cannot_hide_source_role_by_renaming_run(tmp_path, classification):
    data = tmp_path / "result.json"; data.write_text(json.dumps({"classification": classification, "n": 2}), encoding="utf-8")
    claim = {"claim_id": "n", "statement": "Synthetic", "study_run_id": "renamed_innocent_run",
             "data_path": data.name, "analysis_field": "/n", "code_commit": "synthetic",
             "data_sha256": digest(data.read_bytes()), "status": "CONFIRMATORY", "value": 2,
             "private_test_authorized": True}
    with pytest.raises(ValueError, match="source evidence cannot be promoted"):
        validate_claims([claim], tmp_path)

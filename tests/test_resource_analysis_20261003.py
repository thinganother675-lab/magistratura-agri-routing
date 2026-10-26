# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from agro_route.resource_analysis_20261003 import (
    align_pairs, confidence_analysis, distribution, fixed_threshold_replay,
    grouped_pairs, paired_bootstrap, validate_rows,
)


def row(item, em=1, **kwargs):
    return {"item_id": item, "split": "dev", "domain": "synthetic", "gold_valid": True,
            "gold_cardinality": 1, "em": em, "f1": float(em) if em is not None else None, "pred_valid": True,
            "error": None, "response_received": True, "prompt_sha256": f"synthetic_{item}",
            "latency_s": 1., "ttft_s": .2, "generation_span_s": .6,
            "option_token_confidence": .9 if em else .1, **kwargs}


def test_pairs_align_by_id_instead_of_row_order_and_exclude_bad_reference():
    a = [row(1), row(2, 0), row(3, gold_valid=False, em=None, f1=None)]
    b = [copy.deepcopy(r) for r in reversed(a)]
    assert [r[0]["item_id"] for r in align_pairs(a, b, [1, 2, 3])] == [1, 2]


def test_pairs_reject_mismatched_prompt_and_reference_annotations():
    a, b = [row(1)], [row(1, prompt_sha256="different")]
    with pytest.raises(ValueError, match="prompts differ"):
        align_pairs(a, b, [1])
    b = [row(1, gold_cardinality=2)]
    with pytest.raises(ValueError, match="annotations differ"):
        align_pairs(a, b, [1])


def test_paired_bootstrap_does_not_unpair_or_claim_noninferiority():
    a = [row(1), row(2, 0), row(3), row(4, 0)]
    result = paired_bootstrap(a, copy.deepcopy(a), [1, 2, 3, 4], samples=100)
    assert result["em_interval"] == [0., 0.] and result["f1_interval"] == [0., 0.]
    assert result["equivalence_or_noninferiority_established"] is False
    assert result["independent_confirmatory_inference"] is False and result["p_value"] is None


def test_bootstrap_preserves_fixed_domain_counts_and_seed():
    a = [row(1, domain="a"), row(2, 0, domain="b")]
    b = [row(1, 0, domain="a"), row(2, domain="b")]
    first = paired_bootstrap(a, b, [1, 2], samples=100)
    assert first == paired_bootstrap(a, b, [1, 2], samples=100)
    # A pooled bootstrap would fluctuate; one fixed item per domain cannot.
    assert first["domain_counts_fixed"] and first["em_interval"] == [0., 0.]


@pytest.mark.parametrize("kwargs", [{"samples": 0}, {"samples": True}, {"samples": 99}])
def test_bootstrap_requires_meaningful_replicates(kwargs):
    with pytest.raises(ValueError, match="100 bootstrap"):
        paired_bootstrap([row(1)], [row(1)], [1], **kwargs)
    with pytest.raises(ValueError, match="100 bootstrap"):
        confidence_analysis([row(1)], [1], **kwargs)


@pytest.mark.parametrize("field,value", [("latency_s", -1), ("ttft_s", float("inf")),
                                        ("client_tps", True), ("generation_span_s", float("nan"))])
def test_timing_and_rate_units_reject_nonphysical_values(field, value):
    with pytest.raises(ValueError, match="finite nonnegative"):
        validate_rows([row(1, **{field: value})], [1])


def test_timing_components_cannot_exceed_end_to_end_or_convert_milliseconds_silently():
    with pytest.raises(ValueError, match="exceeds end-to-end"):
        validate_rows([row(1, ttft_s=200.)], [1])
    assert validate_rows([row(1, ttft_s=None)], [1])["strict_em_count"] == 1


def test_boolean_em_rejected_as_nonmeasurement():
    with pytest.raises(ValueError, match="not boolean"):
        validate_rows([row(1, em=True)], [1])


@pytest.mark.parametrize("bad", ["question", "prompt", "gold", "choices", "prediction_raw", "api_key", "environment", "unknown_extra"])
def test_restricted_content_and_secret_fields_cannot_enter_analysis(bad):
    with pytest.raises(ValueError):
        validate_rows([row(1, **{bad: "synthetic forbidden value"})], [1])


def test_nested_secret_in_error_cannot_be_captured():
    with pytest.raises(ValueError, match="Secret"):
        validate_rows([row(1, 0, error={"Authorization": "synthetic"})], [1])


def test_test_split_and_missing_coverage_rejected():
    with pytest.raises(ValueError, match="public DEV"):
        validate_rows([row(1, split="test")], [1])
    with pytest.raises(ValueError, match="Full common"):
        validate_rows([row(1)], [1, 2])


def test_distribution_retains_unknown_and_limits_tail_precision():
    result = distribution([None, 1., 3.], unit="s")
    assert result["n_total"] == 3 and result["n_observed"] == 2
    assert result["mean"] == 2. and result["p50"] == 2.
    assert result["p99"] is None and result["p99_status"] == "INSUFFICIENT_N_LT_100"
    assert distribution([None], unit="MiB")["mean"] is None
    assert distribution(range(100), unit="s")["p99"] == pytest.approx(98.01)


def test_confidence_auc_ties_reverse_and_missing_are_not_calibration():
    tied = confidence_analysis([row(1, option_token_confidence=.5), row(2, 0, option_token_confidence=.5)], [1, 2], samples=100)
    assert tied["auc_correctness"] == .5 and tied["auc_interval"] == [.5, .5]
    reverse = confidence_analysis([row(1, option_token_confidence=.1), row(2, 0, option_token_confidence=.9)], [1, 2], samples=100)
    assert reverse["auc_correctness"] == 0.
    missing = confidence_analysis([row(1, option_token_confidence=None)], [1], samples=100)
    assert missing["n_observed_scored"] == 0 and missing["auc_correctness"] is None
    assert tied["ece"] is None and tied["brier"] is None and not tied["calibrated_probability_of_correctness"]
    assert sum(b["n"] for b in tied["confidence_bins"]) == 2


def test_cardinality_is_analysis_metadata_never_required_in_routing_signal():
    a = [row(1), row(2, 0, gold_cardinality=2)]
    b = [row(1, 0), row(2, gold_cardinality=2)]
    groups = grouped_pairs(a, b, [1, 2], field="answer_cardinality")
    assert groups["single"]["em_left_minus_right"] == 1
    assert groups["multiple"]["em_left_minus_right"] == -1
    original = fixed_threshold_replay(a, b, [1, 2])
    a[0].update(em=0, f1=0.)
    changed = fixed_threshold_replay(a, b, [1, 2])
    assert [v["cloud_calls_if_deployed"] for v in original["grid"]] == [v["cloud_calls_if_deployed"] for v in changed["grid"]]
    assert original["actual_requests_saved"] == 0 and not original["confidence_benefit_established"]


def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts/analyze_resource_efficiency_20261003.py"
    spec = importlib.util.spec_from_file_location("resource_script_for_tests", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_raw_timing_extractor_only_emits_scalar_timing_and_no_prompt_or_secret(tmp_path):
    record = {"kind": "benchmark", "latency_s": 1., "usage": {"completion_tokens": 2},
              "request": {"messages": [{"content": "synthetic benchmark question"}], "headers": {"Authorization": "synthetic secret"}},
              "timing": {"first_nonempty_delta_s_client": .2, "last_nonempty_delta_s_client": .7},
              "raw": {"finish_reason": "stop", "events": [{"content": "synthetic answer"}]}}
    path = tmp_path / "raw.jsonl"; path.write_text(json.dumps(record), encoding="utf-8")
    manifest = {"raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    result = load_script().safe_raw_timing([row(1, output_tokens=2)], manifest, path)
    assert result[0]["generation_span_s"] == pytest.approx(.5)
    encoded = json.dumps(result)
    assert "synthetic secret" not in encoded and "benchmark question" not in encoded and "synthetic answer" not in encoded
    assert "request" not in result[0] and "raw" not in result[0]
    manifest["raw_sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash mismatch"):
        load_script().safe_raw_timing([row(1, output_tokens=2)], manifest, path)


def test_raw_ordering_mismatch_fails_closed(tmp_path):
    path = tmp_path / "raw.jsonl"
    path.write_text(json.dumps({"kind": "benchmark", "latency_s": 2., "usage": {"completion_tokens": 2}}), encoding="utf-8")
    with pytest.raises(ValueError, match="ordering differ"):
        load_script().safe_raw_timing([row(1, output_tokens=2)], {"raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, path)

# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mera_cloud_baseline_20261003 import PROFILES, request, reserve_usd, selected_probe, safe_measurement, execution_status
from agro_route.mera_adapter_20261003 import InferenceItem


def test_cloud_uses_provider_supported_temperature_and_reasoning_total_cap():
    for name in PROFILES:
        body = request(name, "synthetic question")
        assert body["temperature"] == .5
        assert "max_completion_tokens" in body and "max_tokens" not in body
        assert body["response_format"]["type"] == "json_schema"
        assert "seed" not in body and "logprobs" not in body
        assert set(body["messages"][0]) == {"role", "content"}


def test_probe_selection_has_same_fixed12_without_gold_access():
    values = [object() for _ in range(60)]
    assert selected_probe(values) == values[::5]
    with pytest.raises(ValueError): selected_probe(values[:59])


def test_byte_budget_reserves_output_cap_and_input_before_paid_attempt():
    for name, config in PROFILES.items():
        assert reserve_usd(name, "synthetic") > config["max_completion_tokens"] * config["prices"][1] / 1e6
        assert reserve_usd(name, "synthetic longer") > reserve_usd(name, "synthetic")


def test_no_other_models_or_test_stage_in_contract():
    with pytest.raises(ValueError, match="Unfrozen"):
        request("arbitrary", "synthetic")
    assert set(PROFILES) == {"mercury25_instant256_t05", "mercury2_medium1024_t05", "mercury25_instant512_t05"}


def test_one_additional_budget_profile_changes_only_budget():
    a = request("mercury25_instant256_t05", "synthetic question")
    b = request("mercury25_instant512_t05", "synthetic question")
    assert {k: v for k, v in a.items() if k != "max_completion_tokens"} == {k: v for k, v in b.items() if k != "max_completion_tokens"}
    assert a["max_completion_tokens"] == 256 and b["max_completion_tokens"] == 512


def test_truncated_parseable_json_is_incomplete_and_scores_zero():
    item = InferenceItem(1, "dev", "synthetic question", tuple("ABCD"), "synthetic discipline")
    body = request("mercury25_instant256_t05", item.prompt)
    raw = {"model": "mercury-2.5", "choices": [{"finish_reason": "length"}], "usage": {"prompt_tokens": 5, "completion_tokens": 256}}
    row = safe_measurement(item, "A", body, '{"choices":["A"]}', 1, None, raw)
    assert row["strict_set_em"] == 0 and row["strict_set_f1"] == 0
    assert row["error"]["type"] == "IncompleteCompletion"
    assert row["prediction_valid"] is False


def test_all_attempts_with_last_error_is_not_successfully_complete():
    assert execution_status([{"response_received": True, "error": None}], 1) == "COMPLETE"
    assert execution_status([{"response_received": True, "error": {"type": "IncompleteCompletion"}}], 1) == "ATTEMPT_COVERAGE_COMPLETE_WITH_FAILURES"
    assert execution_status([], 1) == "PARTIAL"

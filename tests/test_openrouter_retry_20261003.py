# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("retry", Path(__file__).resolve().parents[1] / "scripts/openrouter_retry_20261003.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def fixture():
    model = {"id": "example/model:free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text"]}}
    ep = {"tag": "example", "pricing": model["pricing"], "supported_parameters": ["temperature", "max_tokens"]}
    row = {"resolved_model_id": model["id"], "selected_endpoint": ep}
    return row, model, [ep]

@pytest.mark.parametrize("price", ["0.01", None, "NaN", True, "-1"])
def test_changed_endpoint_prices_fail_closed(price):
    row, model, eps = copy.deepcopy(fixture())
    eps[0]["pricing"]["request"] = price
    with pytest.raises(ValueError):
        m.validate_current(row, model, eps)

def test_pinned_provider_must_remain_exact():
    row, model, eps = copy.deepcopy(fixture())
    row["selected_endpoint"] = {**eps[0], "tag": "other"}
    with pytest.raises(ValueError):
        m.validate_current(row, model, eps)

def test_zero_is_only_confirmed_bill():
    assert m.confirmed_cost({"usage": {"cost": 0}}) == 0
    for value in (None, True, float("nan"), -1, "0"):
        assert m.confirmed_cost({"usage": {"cost": value}}) is None
    assert m.confirmed_cost({"usage": {"cost": .01}}) == .01

def test_scrub_nested_credentials_and_account_fields():
    assert m.scrub({"error": {"message": "secretVALUE sk-or-v1-fakevalue", "hash": "private"}}, ["secretVALUE"]) == {"error": {"message": "[REDACTED] [REDACTED]"}}

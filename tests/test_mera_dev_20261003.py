# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import sys
import httpx
import pytest
from agro_route.mera_adapter_20261003 import InferenceItem

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("mera_dev_runner", ROOT / "scripts/mera_dev_20261003.py")
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


def test_fixed_selection_ignores_gold_and_balances_domains():
    items = [InferenceItem(i + 100*d, "dev", "Придуманный вопрос", tuple("ABCD"), str(d))
             for d in range(10) for i in range(10)]
    selected = runner.select_balanced(items)
    assert len(selected) == 60
    assert {d: sum(x.domain == str(d) for x in selected) for d in range(10)} == {d: 6 for d in range(10)}
    assert [x.item_id for x in selected if x.domain == "0"] == [0, 1, 3, 5, 6, 8]


def test_real_logprob_absence_is_not_fake_confidence():
    assert runner.token_confidence(None) is None
    assert runner.token_confidence({"content": [{"token": "A", "logprob": -.1}]}) == pytest.approx(.904837418)
    assert runner.token_confidence({"content": [{"token": "A", "logprob": 10}]}) is None


def call_mock(text, local=True):
    item = InferenceItem(1, "dev", "Придуманный вопрос 1+1?", tuple("ABCD"), "Пример")
    def reply(request):
        payload = __import__('json').loads(request.content)
        assert payload["messages"] == [{"role": "user", "content": item.prompt}]
        assert "outputs" not in payload and "gold" not in payload
        return httpx.Response(200, json={"model": "fixture", "choices": [{"message": {"content": text},
             "logprobs": {"content": [{"token": "A", "logprob": -.1}, {"token": "B", "logprob": -.8}]}}],
             "usage": {"prompt_tokens": 100, "completion_tokens": 3}})
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        return runner.call_model(client, "https://synthetic.invalid/", "fixture-secret", "fixture", item,
                                 local=local, prices=(.25, .75))


def test_prose_letter_confidence_not_used_for_routing():
    row = call_mock("Ответ: A. Объяснение B упоминается как неверный.")
    assert row["prediction"] == "A"
    assert row["option_token_confidence"] is None


def test_model_output_normalization_preserves_wrong_choice():
    row = call_mock("C, A", local=False)
    assert row["prediction"] == "A, C" and row["prediction_raw"] == "C, A"
    assert row["cost_usd_estimate"] == pytest.approx(.00002725)
    assert row["option_token_confidence"] is None


def test_cloud_revision_explicitly_controls_reasoning_and_total_output_budget():
    item = InferenceItem(1, "dev", "Придуманный вопрос", tuple("ABCD"), "Пример")
    def reply(request):
        payload = __import__('json').loads(request.content)
        assert payload["reasoning_effort"] == "instant" and payload["temperature"] == .75
        assert payload["max_completion_tokens"] == 256 and "max_tokens" not in payload
        return httpx.Response(200, json={"choices": [{"message": {"content": "A"}}],
                             "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        row = runner.call_model(client, "https://synthetic.invalid", "", "fixture", item,
                               local=False, prices=(.25, .75), cloud_profile="instant-256")
    assert row["valid_options"]


def test_nontext_content_is_recorded_as_error_after_request():
    row = call_mock([{"type": "text", "text": "A"}])
    assert row["error"]["type"] == "ValueError" and not row["valid_options"]


@pytest.mark.parametrize("tokens", [-1, True, 1.5])
def test_malformed_usage_cannot_reduce_budget(tokens):
    item = InferenceItem(1, "dev", "Пример", tuple("ABCD"), "Пример")
    def reply(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "A"}}],
                             "usage": {"prompt_tokens": tokens, "completion_tokens": 1}})
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        row = runner.call_model(client, "https://synthetic.invalid", "", "fixture", item, local=False, prices=(.25, .75))
    assert row["cost_usd_estimate"] is None

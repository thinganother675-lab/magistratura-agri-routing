"""Mock-only checks of streaming accounting and credential/data boundaries."""
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest


@pytest.fixture
def runner(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/home_lm_api_benchmark.py"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("home_lm_api_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(obj):
    return "data: " + json.dumps(obj)


def test_stream_counts_usage_and_separates_reasoning_from_answer(runner):
    ticks = iter([.1, .3, .5, .6, .7])
    result = runner.consume_sse([
        event({"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]}),
        event({"choices": [{"delta": {"reasoning": "think"}, "finish_reason": None}]}),
        event({"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}]}),
        event({"choices": [], "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}}),
        "data: [DONE]"], 0, clock=lambda: next(ticks))
    assert result["usage"]["completion_tokens"] == 10
    assert result["timing"]["first_nonempty_delta_s_client"] == .3
    assert result["timing"]["first_answer_delta_s_client"] == .5
    assert result["timing"]["first_reasoning_delta_s_client"] == .3
    assert result["timing"]["completion_tokens_per_second_client_approx"] == pytest.approx(50)
    assert result["timing"]["backend_tokens_per_second"] is None
    assert result["final_content"] == "{}" and result["reasoning_content"] == "think"


def test_payload_has_schema_and_does_not_leak_gold_or_use_unknown_controls(runner):
    body = runner.payload("fixture", {"input": "question", "context": "source", "inputs": {}, "expected": "GOLD", "split": "dev"})
    assert "GOLD" not in json.dumps(body)
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["temperature"] == 0 and body["seed"] == 42 and body["max_tokens"] == 512
    assert not {"previous_response_id", "tools", "integrations", "reasoning", "reasoning_effort", "chat_template_kwargs"} & body.keys()


def test_missing_done_or_length_remains_incomplete(runner):
    answer = json.dumps({"action": "ANSWER", "answer": "OK", "numeric": None, "unit": None, "tool": None})
    def handler(request):
        return httpx.Response(200, text=event({"choices": [{"delta": {"content": answer}, "finish_reason": "length"}]}) + "\n\ndata: [DONE]\n\n")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = runner.api_call(client, "fixture-secret", "fixture-model", {"input": "q"})
    assert result["error"]["type"] == "IncompleteCompletion"
    assert result["output"] is None and result["raw"]["final_content"] == answer


def test_http_auth_error_does_not_persist_credential_echo(runner):
    def handler(request):
        return httpx.Response(401, json={"error": "bad fixture-secret token"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = runner.api_call(client, "fixture-secret", "fixture", {"input": "q"})
    assert result["error"] == {"type": "HTTPStatusError", "http_status": 401}
    assert "fixture-secret" not in json.dumps(result)


def test_stream_error_wins_over_final_stop_and_secret_is_redacted(runner):
    def handler(request):
        return httpx.Response(200, text=event({"error": {"message": "fixture-secret"}}) + "\n\n" + event({"choices": [{"delta": {}, "finish_reason": "stop"}]}) + "\n\ndata: [DONE]\n\n")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = runner.api_call(client, "fixture-secret", "fixture", {"input": "q"})
    assert result["error"] and result["output"] is None
    assert "fixture-secret" not in json.dumps(result)
    assert "[REDACTED]" in json.dumps(result)


def test_unknown_usage_is_missing_not_zero(runner):
    result = runner.consume_sse([event({"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}]}), "data: [DONE]"], 0, clock=lambda: 1)
    assert result["usage"] == {}
    assert result["timing"]["completion_tokens_per_second_client_approx"] is None
    assert result["timing"]["backend_ttft_s"] is None


def test_experimental_reasoning_field_is_explicit_opt_in(runner):
    assert "reasoning_effort" not in runner.payload("fixture", {"input": "q"})
    assert runner.payload("fixture", {"input": "q"}, "none")["reasoning_effort"] == "none"


def test_malformed_sse_preserves_prior_data_and_never_claims_completion(runner):
    result = runner.consume_sse([event({"choices": [{"delta": {"content": "partial"}, "finish_reason": None}]}), "data: {invalid"], 0, clock=lambda: 1)
    assert result["final_content"] == "partial"
    assert result["events"][-1]["unparsed_data"] == "{invalid"
    assert result["event_error"] == "MalformedSSE" and result["stream_done"] is False


def test_custom_final_holdout_is_rejected(runner, tmp_path):
    path = tmp_path / "samples.jsonl"
    path.write_text(json.dumps({"id": "test", "split": "test"}) + "\n")
    with pytest.raises(ValueError, match="development"):
        runner.select_samples(1, path)


def test_custom_bilingual_pairs_counterbalanced_without_gold_changes(runner, tmp_path):
    samples = [{"id": f"{group}-{lang}", "split": "dev", "group": group, "language": lang, "expected": {"answer": "gold"}} for group in ("a", "b") for lang in ("en", "ru")]
    path = tmp_path / "samples.jsonl"
    path.write_text("\n".join(json.dumps(s) for s in samples))
    selected = runner.select_samples(4, path)
    assert [s["id"] for s in selected] == ["a-en", "a-ru", "b-ru", "b-en"]
    assert all(s["expected"] == {"answer": "gold"} for s in selected)

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("home_openrouter_benchmark", Path(__file__).resolve().parents[1]/"scripts/home_openrouter_benchmark.py")
or_bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(or_bench)


def model():
    return {"id": "vendor/general:free", "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["temperature", "max_tokens", "response_format", "structured_outputs"]}


@pytest.mark.parametrize("model_id,prompt", [("vendor/general", "0"), ("vendor/general:free", "0.001"), ("vendor/general:free", "NaN"), ("vendor/general:free", None)])
def test_paid_or_nonexplicit_zero_refused(model_id, prompt):
    item = model()
    item["id"], item["pricing"]["prompt"] = model_id, prompt
    with pytest.raises(ValueError):
        or_bench.validate_model(model_id, {model_id: item})


def test_zero_price_fallback_guards_gold_filtered_and_schema():
    item = model()
    or_bench.validate_model(item["id"], {item["id"]: item})
    sample = {"id": "dev", "input": "Calculate", "expected": {"secret_gold": "omitted"}, "language": "ru", "category": "numeric"}
    body = or_bench.request_payload(item, sample)
    assert body["model"].endswith(":free") and "models" not in body and "route" not in body
    assert body["provider"] == {"allow_fallbacks": False, "require_parameters": True, "max_price": {"prompt": 0, "completion": 0, "request": 0}}
    assert "secret_gold" not in json.dumps(body)
    assert body["temperature"] == 0 and body["max_tokens"] == 512
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in body and "plugins" not in body


def test_quota_safe_allowlist_no_key_label():
    def handler(request):
        return httpx.Response(200, json={"data": {"label": "SENSITIVE_VALUE", "hash": "OTHER_SENSITIVE", "usage": 0, "free_model_daily_requests": {"remaining": 50}}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        quota = or_bench.safe_quota(client, "SENSITIVE_VALUE")
    assert "label" not in quota and "hash" not in quota
    assert quota["free_model_daily_requests"]["remaining"] == 50
    assert "SENSITIVE_VALUE" not in json.dumps(quota)


def test_429_no_retry_and_no_sensitive_error_body(tmp_path):
    sample = {"id": "dev", "input": "x", "language": "ru", "category": "numeric"}
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={"error": "SENSITIVE_VALUE"}, headers={"Retry-After": "60"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, reason = or_bench.execute_model(model(), [sample]*3, client=client, key="SENSITIVE_VALUE", output=tmp_path, progress=[0], min_interval=0)
    assert len(requests) == 1 and requests[0].url == or_bench.ENDPOINT
    assert reason == "HTTP_429" and len(rows) == 1
    assert "SENSITIVE_VALUE" not in (tmp_path/"raw.jsonl").read_text(encoding="utf-8")


def test_nonzero_reported_cost_stops():
    with pytest.raises(ValueError, match="cost"):
        or_bench.normalize(model(), {}, {"usage": {"cost": 0.01}})


def test_auth_failure_has_no_quality_or_inference_latency():
    summary = or_bench.summarize("vendor/general:free", [{"latency_ms": 123, "http_status": 401, "error": "HTTP_401", "language": "en", "category": "extractive_qa"}])
    assert summary["successful_generations"] == 0
    assert summary["quality_accuracy"] is None
    assert summary["p50_latency_ms"] is None

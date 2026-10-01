import importlib.util
import json
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location("home_jev_benchmark", Path(__file__).resolve().parents[1] / "scripts/home_jev_benchmark.py")
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


def response(noul=0.5):
    return {"model": jev.MODEL, "answers": {"route": {"choice": "abstain"}, "missing_data": {"noul": noul}}, "usage": {"input_tokens": 100, "output_tokens": 10}}


def test_payload_identical_public_state_and_questions_without_gold():
    cases, questions = jev.load_baseline()
    assert len(cases) == 12
    payload = jev.public_payload(cases[0], questions)
    assert set(payload) == {"state", "model", "questions"}
    assert payload["state"] == cases[0]["state"]
    assert payload["questions"] == questions
    assert payload["model"] == "jev-1.13.0"


def test_noul_threshold_and_input_only_cost():
    case = {"gold_route": "abstain", "gold_missing_data": True}
    out = jev.normalize(case, response())
    assert out["correct_missing_data"] is True
    assert out["estimated_cost_usd"] == pytest.approx(0.0000042)
    assert jev.normalize(case, response(0.499))["correct_missing_data"] is False


@pytest.mark.parametrize("noul", [True, float("nan"), -0.1, 1.1, "0.5"])
def test_invalid_noul_rejected(noul):
    with pytest.raises(ValueError):
        jev.normalize({"gold_route": "abstain", "gold_missing_data": True}, response(noul))


def test_429_stops_no_retry_no_secret_artifact(tmp_path):
    cases, questions = jev.load_baseline()
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={"error": "SENSITIVE_TEST_VALUE"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, reason = jev.execute(cases, questions, client=client, key="SENSITIVE_TEST_VALUE", output=tmp_path)
    assert len(requests) == 1
    assert requests[0].url == jev.ENDPOINT
    assert reason == "HTTP_429"
    artifact = (tmp_path / "raw.jsonl").read_text(encoding="utf-8")
    assert "SENSITIVE_TEST_VALUE" not in artifact
    assert "Authorization" not in artifact


def test_response_exact_secret_recursive_redaction():
    assert jev.redact({"x": ["hello secret", {"secret": "secret"}]}, "secret") == {"x": ["hello [REDACTED]", {"[REDACTED]": "[REDACTED]"}]}

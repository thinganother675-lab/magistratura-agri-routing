"""Mocked HOME configuration and paid-pilot boundaries; no actual API calls."""
import importlib.util
import json
from pathlib import Path

import pytest

from agro_route.home_config import parse_allowlisted_env, resolve_api_key, resolve_from_sources

ROOT = Path(__file__).resolve().parents[1]


def pilot_module():
    spec = importlib.util.spec_from_file_location("mercury_pilot_test", ROOT / "scripts/home_cloud_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample(sid="dev-1"):
    return {"id": sid, "split": "dev", "input": "Choose a tool", "category": "tool_selection",
            "language": "en", "group": sid, "scoring": "exact",
            "expected": {"action": "ANSWER", "answers": ["gdd"]}}


def good_result():
    return {"output": {"action": "ANSWER", "answer": "gdd"}, "error": None,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}, "cost_usd": .000007,
            "raw": {"id": "fake-completion"}, "latency_ms": 1.}


def prepare(monkeypatch, tmp_path, n=2):
    pilot = pilot_module()
    monkeypatch.setattr(pilot, "verify_protected", lambda root: {"historical_hashes_match": True})
    monkeypatch.setattr(pilot, "choose_dev_samples", lambda count: [sample(f"dev-{i}") for i in range(count)])
    monkeypatch.setattr(pilot, "resolve_api_key", lambda *a, **k: ("test-placeholder", "project_env:mercury_api_key"))
    return pilot


def test_empty_canonical_uses_provider_alias_without_mutating_sources():
    process = {"CLOUD_API_KEY": "", "openrouter_api_key": "not-a-real-key"}
    project = {"mercury_api_key": "test-placeholder"}
    assert resolve_from_sources("mercury", process, project) == ("test-placeholder", "project_env:mercury_api_key")
    assert process["CLOUD_API_KEY"] == ""
    assert resolve_from_sources("mercury", process, {}) == ("", None)


def test_nonempty_canonical_file_has_priority_over_process_alias():
    assert resolve_from_sources("mercury", {"mercury_api_key": "not-a-real-key"},
                                {"CLOUD_API_KEY": "test-placeholder"}) == ("test-placeholder", "project_env:CLOUD_API_KEY")


def test_process_canonical_priority_and_local_alias():
    assert resolve_from_sources("local", {"LOCAL_API_KEY": "test-placeholder"},
                                {"LOCAL_API_KEY": "not-a-real-key"})[1] == "process:LOCAL_API_KEY"
    assert resolve_from_sources("local", {}, {"LM_API_TOKEN": "test-placeholder"})[1] == "project_env:LM_API_TOKEN"
    assert resolve_from_sources("openrouter", {}, {"openrouter_api_key": "test-placeholder"})[1] == "project_env:openrouter_api_key"
    assert resolve_from_sources("jev", {}, {"jev_api_key": "test-placeholder"})[1] == "project_env:jev_api_key"


def test_allowlist_and_quoted_values(tmp_path):
    text = '# comment\nCLOUD_API_KEY=\nmercury_api_key="test-placeholder"\nOTHER_SECRET=discard\n'
    assert parse_allowlisted_env(text) == {"CLOUD_API_KEY": "", "mercury_api_key": "test-placeholder"}
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8-sig")
    assert resolve_api_key("mercury", env_path=env_file, environ={})[1] == "project_env:mercury_api_key"
    assert env_file.read_text(encoding="utf-8-sig") == text


def test_invalid_provider_and_linebreak_are_safe_errors():
    with pytest.raises(ValueError, match="Unknown credential provider"):
        resolve_from_sources("unknown", {}, {})
    with pytest.raises(ValueError, match="invalid line break"):
        resolve_from_sources("mercury", {}, {"mercury_api_key": "one\ntwo"})


@pytest.mark.parametrize("n", [0, 13, True, -1])
def test_call_ceiling_rejects_before_credentials_or_network(monkeypatch, tmp_path, n):
    pilot = prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(pilot, "resolve_api_key", lambda *a, **k: pytest.fail("credential read"))
    with pytest.raises(ValueError, match="1 to 12"):
        pilot.run(n, execute=True, root=tmp_path)
    assert not (tmp_path / "results").exists()


def test_plan_only_never_reads_credentials_or_creates_results(monkeypatch, tmp_path):
    pilot = prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(pilot, "resolve_api_key", lambda *a, **k: pytest.fail("credential read"))
    result = pilot.run(12, root=tmp_path)
    assert result["n"] == 12 and result["planning_cost_estimate_usd"] == pytest.approx(.0038016)
    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize("samples", [[{**sample(), "split": "test"}], [sample(), sample()]])
def test_non_dev_and_duplicate_ids_rejected(samples):
    with pytest.raises(ValueError):
        pilot_module().validate_samples(samples, len(samples))


def test_unknown_usage_and_cost_remain_unknown():
    pilot = pilot_module()
    summary = pilot.summarize([{"cloud": {"usage": {}, "cost_usd": None, "error": {"type": "HTTPError"}},
                                "score": {"correct": False}}])
    assert summary["input_tokens_known_sum"] is None
    assert summary["known_cost_estimate_usd"] is None and summary["unknown_cost_calls"] == 1
    assert summary["input_usage_coverage_n"] == 0


def test_success_saved_once_and_fixed_provider(monkeypatch, tmp_path):
    pilot = prepare(monkeypatch, tmp_path)
    calls = []
    class Fake:
        def __init__(self, url, model, key, inp, out, timeout):
            assert url == "https://api.inceptionlabs.ai/v1" and model == "mercury-2.5"
            assert key == "test-placeholder" and timeout == 60
        def call(self, request):
            calls.append(request)
            assert "expected" not in request
            return good_result()
    monkeypatch.setattr(pilot, "Model", Fake)
    directory = pilot.run(2, execute=True, root=tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(calls) == 2 and manifest["state"] == "completed"
    assert manifest["cloud_calls_actual"] == 2 and manifest["summary"]["correct"] == 2
    assert "test-placeholder" not in "".join(p.read_text() for p in directory.iterdir())
    original = (directory / "mercury_raw.jsonl").read_bytes()
    second = pilot.run(2, execute=True, root=tmp_path)
    assert second != directory and (directory / "mercury_raw.jsonl").read_bytes() == original


@pytest.mark.parametrize("status", [401, 402, 429, 503])
def test_provider_failure_stops_without_paid_retry(monkeypatch, tmp_path, status):
    pilot = prepare(monkeypatch, tmp_path)
    calls = []
    class Fake:
        def __init__(self, *a, **k): pass
        def call(self, request):
            calls.append(request)
            return {"output": None, "error": {"type": "HTTPStatusError", "http_status": status},
                    "usage": {}, "cost_usd": None, "raw": None}
    monkeypatch.setattr(pilot, "Model", Fake)
    directory = pilot.run(2, execute=True, root=tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(calls) == 1 and manifest["cloud_calls_actual"] == 1
    assert manifest["state"] == "partial_stopped" and manifest["summary"]["unknown_cost_calls"] == 1


def test_interrupted_attempt_remains_visible(monkeypatch, tmp_path):
    pilot = prepare(monkeypatch, tmp_path)
    class Fake:
        def __init__(self, *a, **k): pass
        def call(self, request): raise KeyboardInterrupt()
    monkeypatch.setattr(pilot, "Model", Fake)
    with pytest.raises(KeyboardInterrupt):
        pilot.run(2, execute=True, root=tmp_path)
    directory = next((tmp_path / "results").iterdir())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["state"] == "partial_interrupted" and manifest["cloud_calls_actual"] == 1
    assert manifest["summary"]["n_saved"] == 0


def test_hash_mismatch_blocks_network(monkeypatch, tmp_path):
    pilot = prepare(monkeypatch, tmp_path)
    def mismatch(root): raise RuntimeError("Protected historical core hash mismatch")
    monkeypatch.setattr(pilot, "verify_protected", mismatch)
    monkeypatch.setattr(pilot, "resolve_api_key", lambda *a, **k: pytest.fail("credential read"))
    with pytest.raises(RuntimeError, match="hash mismatch"):
        pilot.run(2, execute=True, root=tmp_path)


def test_exact_credential_echo_is_redacted():
    assert pilot_module().sanitize({"raw": {"content": "test-placeholder"}}, "test-placeholder") == {
        "raw": {"content": "[REDACTED_CREDENTIAL]"}}

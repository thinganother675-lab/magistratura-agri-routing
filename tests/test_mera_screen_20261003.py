"""Invented fixtures, no benchmark content, real backend or hidden TEST gold."""
import importlib.util
from pathlib import Path
import sys

import pytest

from agro_route.mera_screen_metrics_20261003 import choice_set, set_score, summarize
from agro_route.mera_adapter_20261003 import InferenceItem


@pytest.fixture
def runner():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("mera_screen_test", scripts / "mera_local_screen_20261003.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strict_a_never_deleted():
    assert set_score("A", "", "ABCD")["strict_set_em"] == 0
    assert set_score("A,C", '{"choices":["C"]}', "ABCD")["strict_set_f1"] == pytest.approx(2 / 3)
    assert set_score("A", '{"choices":["A"]}', "ABCD")["strict_set_em"] == 1


def test_multi_answer_presentation_only():
    result = set_score("A,C", '{"choices":["c", "a"]}', "ABCD")
    assert result["strict_set_em"] == 1
    assert result["strict_set_f1"] == 1
    assert result["gold_cardinality"] == 2


@pytest.mark.parametrize("text", ["Ответ: A потому что...", "The answer is A", "А", '{"choices":["A"],"reason":"x"}', '{"choices":["Z"]}', '{"choices":[]}'])
def test_semantic_repair_and_cyrillic_not_allowed(text):
    assert not choice_set(text, "ABCD")[0]


def test_ambiguous_gold_excluded_and_never_repaired():
    result = set_score("А", '{"choices":["A"]}', "ABCD")
    assert result["gold_valid"] is False
    assert result["strict_set_em"] is None


def fixture_row(item_id, gold="A", prediction='{"choices":["A"]}'):
    return {"item_id": item_id, "domain": "invented", **set_score(gold, prediction, "ABCD"),
            "latency_s": 1, "response_received": True, "error": None}


def test_partial_coverage_does_not_rank_as_complete():
    result = summarize([fixture_row(1)], [1, 2])
    assert not result["complete_coverage"]
    assert result["conservative_all_n_em"] == .5


def test_reference_sensitivity_denominator_explicit():
    result = summarize([fixture_row(1), fixture_row(2, gold="А")], [1, 2])
    assert result["complete_coverage"]
    assert result["n_scored"] == 1
    assert result["reference_issues"] == 1
    assert result["strict_set_em"] == 1
    assert result["conservative_all_n_em"] == .5


def test_duplicate_or_unexpected_ids_fail():
    with pytest.raises(ValueError, match="Duplicate or unexpected"):
        summarize([fixture_row(1), fixture_row(1)], [1, 2])
    with pytest.raises(ValueError, match="Duplicate or unexpected"):
        summarize([fixture_row(3)], [1, 2])


def test_payload_no_gold_and_same_output_budget(runner):
    payload = runner.payload("invented-model", "Invented question A:x B:y C:z D:w", None)
    assert "gold" not in str(payload)
    assert payload["messages"][0]["content"] == runner.SYSTEM
    assert payload["max_tokens"] == 512
    assert payload["temperature"] == 0
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_guards_not_weakened_and_uniform_chunk_policy(runner):
    assert runner.PROTOCOL["fixed_reload_every_n"] == 10
    assert runner.PROTOCOL["inference_min_ram_gib"] == 2
    assert runner.PROTOCOL["inference_min_gpu_free_mib"] == 512
    assert runner.PROTOCOL["private_test_run"] is False


def test_dev60_selection_reference_free(runner):
    items = [InferenceItem(i, "dev", "invented question", tuple("ABCD"), domain)
             for domain in ["x", "y"] for i in range(7 if domain == "x" else 10, 14 if domain == "x" else 17)]
    assert runner.select_balanced(items) == runner.select_balanced(list(reversed(items)))
    assert len(runner.select_balanced(items)) == 12


def test_immutable_source_rejects_before_parsing(runner, monkeypatch):
    source = Path("invented.json")
    monkeypatch.setattr(Path, "read_bytes", lambda path: b'{"outputs":"hidden test answer"}')
    monkeypatch.setattr(runner, "ensure_restricted_path", lambda path, root: path)
    with pytest.raises(ValueError, match="immutability"):
        runner.validate_source(source, "incorrect-hash")


def test_confidence_only_emitted_choice_tokens(runner):
    events = [{"data": {"choices": [{"logprobs": {"content": [
        {"token": "choices", "logprob": -.01}, {"token": "A", "logprob": -.5}]}}]}}]
    conf = runner.confidence_from_events(events)
    assert conf["option_logprob_token_n"] == 1
    assert conf["option_token_confidence"] == pytest.approx(0.6065306597)


def test_gpt_reasoning_change_explicit(runner):
    assert runner.reasoning_config({"architecture": "gpt-oss"}) == "low"
    assert runner.reasoning_config({"capabilities": {"reasoning": {"allowed_options": ["off", "on"]}}}) == "none"


def test_monitor_uses_actual_free_wddm(runner, monkeypatch):
    monkeypatch.setattr(runner.guards.Monitor, "sample", lambda self: None)
    monkeypatch.setattr(runner.guards, "resource_headroom", lambda: {"ram_available_gib": 8, "gpu_free_mib": 400})
    monitor = runner.ResourceMonitor()
    monitor.rows = [{"vram_mib_total": 15500}]
    # total-used=811 would pass; actual free400 must trip the512MiB guard.
    monitor.sample()
    assert monitor.tripped.is_set()
    assert monitor.trip["gpu_free_mib"] == 400


def test_monitor_fails_closed_missing_measurement(runner, monkeypatch):
    monkeypatch.setattr(runner.guards.Monitor, "sample", lambda self: None)
    def unavailable():
        raise RuntimeError("measurement unavailable")
    monkeypatch.setattr(runner.guards, "resource_headroom", unavailable)
    monitor = runner.ResourceMonitor()
    monitor.sample()
    assert monitor.tripped.is_set()
    assert monitor.trip["measurement_error_type"] == "RuntimeError"

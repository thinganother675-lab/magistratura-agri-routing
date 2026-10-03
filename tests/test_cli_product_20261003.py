import json
from pathlib import Path

import pytest
from agro_route.cli_product_20261003 import (
    build_invocation, parse_output, redact_sensitive, subscription_environment,
)


def test_environment_drops_credentials_and_provider_overrides():
    env = {"PATH": "bin", "SystemRoot": "win", "ANTHROPIC_API_KEY": "secret",
           "OPENAI_API_KEY": "secret", "CODEX_API_KEY": "secret", "CLAUDE_CODE_OAUTH_TOKEN": "secret",
           "ANTHROPIC_BASE_URL": "paid", "ANTHROPIC_DEFAULT_SONNET_MODEL": "unexpected", "SECRET": "secret"}
    assert subscription_environment(env) == {"PATH": "bin", "SystemRoot": "win"}


def test_claude_disables_tools_mcp_customization_and_retains_oauth():
    args = build_invocation("claude", "claude.exe", Path("empty"), "synthetic", "sonnet", "medium")
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args and "--safe-mode" in args
    assert "--disable-slash-commands" in args and "--restricted" in args
    assert "--bare" not in args and "--dangerously-skip-permissions" not in args


def test_codex_disables_context_tools_and_forces_subscription():
    args = build_invocation("codex", "codex.exe", Path("empty"), "synthetic", "gpt-6-luna", "medium")
    assert 'forced_login_method="chatgpt"' in args and 'web_search="disabled"' in args
    assert "project_doc_max_bytes=0" in args and "mcp_servers={}" in args
    assert "--ignore-user-config" in args and "--ignore-rules" in args and "--ephemeral" in args
    disabled = [args[i + 1] for i, x in enumerate(args[:-1]) if x == "--disable"]
    assert {"shell_tool", "apps", "plugins", "memories", "hooks", "multi_agent", "browser_use", "computer_use"}.issubset(disabled)


def test_claude_usage_and_tool_exposure():
    events = [{"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "model": "sonnet"},
              {"type": "result", "result": '{"choices":["A"]}', "usage": {"input_tokens": 30, "output_tokens": 7},
               "modelUsage": {"sonnet": {}}, "total_cost_usd": .004}]
    r = parse_output("claude", "\n".join(map(json.dumps, events)))
    assert r["output_tokens"] == 7 and r["returned_model_ids"] == ["sonnet"]
    assert r["harness_confounded"] is False
    events[0]["tools"] = ["Read"]
    assert parse_output("claude", "\n".join(map(json.dumps, events)))["harness_confounded"]


@pytest.mark.parametrize("kind", ["command_execution", "mcp_tool_call", "web_search", "file_change", "plan"])
def test_codex_tool_events_are_confounded(kind):
    events = [{"type": "item.completed", "item": {"type": kind}}, {"type": "turn.completed", "usage": {}}]
    r = parse_output("codex", "\n".join(map(json.dumps, events)))
    assert r["tool_calls_n"] == 1 and r["harness_confounded"]


def test_codex_only_final_agent_text_and_usage():
    events = [{"type": "item.completed", "item": {"type": "reasoning", "text": "do not score"}},
              {"type": "item.completed", "item": {"type": "agent_message", "text": '{"choices":["A"]}'}},
              {"type": "turn.completed", "usage": {"input_tokens": 200, "cached_input_tokens": 100, "output_tokens": 10}}]
    r = parse_output("codex", "\n".join(map(json.dumps, events)))
    assert r["text"] == '{"choices":["A"]}' and r["output_tokens"] == 10
    assert not r["harness_confounded"] and r["displayed_model"] is None


def test_codex_recovered_transport_warning_is_not_tool_or_failed_completion():
    events = [{"type": "error", "message": "Reconnecting... 2/5"},
              {"type": "item.completed", "item": {"type": "error", "message": "HTTPS fallback"}},
              {"type": "item.completed", "item": {"type": "agent_message", "text": '{"choices":["A"]}'}},
              {"type": "turn.completed", "usage": {"input_tokens": 200, "output_tokens": 10}}]
    r = parse_output("codex", "\n".join(map(json.dumps, events)))
    assert r["error"] is None and r["tool_calls_n"] == 0 and not r["harness_confounded"]
    assert r["transport_warning_events_n"] == 2 and r["product_internal_reconnect_events_n"] == 1


def test_sensitive_auth_diagnostics_redacted_before_capture():
    s = 'Bearer abc.def.ghi {"access_token":"sensitive", "api_key":"another"} sk-abcdefghijklm'
    result = redact_sensitive(s)
    assert all(x not in result for x in ("abc.def.ghi", "sensitive", "another", "sk-abcdefghijklm"))


def test_no_gold_in_invocation():
    args = build_invocation("codex", "codex.exe", Path("empty"), "supplied instructions", "gpt-6-luna", "medium")
    assert not any(x in " ".join(args) for x in ("gold", "reference", "answer_key", "target"))
    # Only text and a system instruction are accepted; no reference argument exists.
    import inspect
    from agro_route.cli_product_20261003 import run_request
    assert list(inspect.signature(run_request).parameters) == ["config", "prompt"]


def test_effort_subset_independent_of_gold_and_predictions():
    import importlib.util
    from types import SimpleNamespace
    script = Path(__file__).resolve().parents[1] / "scripts/cli_product_effort_20261003.py"
    import sys
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location("test_cli_effort_selector", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    items = [SimpleNamespace(item_id=j * 10 + i, domain="d" + str(i), split="dev", gold="A", prediction="B")
             for j in range(2) for i in range(10)]
    assert [r.item_id for r in module.select_effort_subset(items)] == list(range(10))
    for item in items: item.gold = "C"; item.prediction = "D"
    assert [r.item_id for r in module.select_effort_subset(items)] == list(range(10))
    items[0].split = "test"
    with pytest.raises(ValueError, match="DEV only"):
        module.select_effort_subset(items)


def test_gold_cannot_influence_supplied_prompt_bytes():
    from agro_route.mera_adapter_20261003 import isolate_dev_references
    row = {"inputs": {"question": "Synthetic question?", "option_a": "yes", "option_b": "no", "option_c": "unknown", "option_d": "maybe"},
           "instruction": "{question} A:{option_a} B:{option_b} C:{option_c} D:{option_d}",
           "meta": {"id": 1, "domain": "invented"}, "outputs": "A"}
    items_a, _ = isolate_dev_references([row])
    row["outputs"] = "D"
    items_d, _ = isolate_dev_references([row])
    assert items_a[0].prompt.encode() == items_d[0].prompt.encode()


def test_committed_cli_rows_do_not_capture_question_gold_or_provider_prose():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "results/20261003_cli_products").glob("*_metrics.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            assert not {"text", "prompt", "reference", "gold", "stdout", "stderr", "access_token", "api_key"}.intersection(row)


def test_cli_claim_pointers_and_hashes_when_finalized():
    from agro_route.cli_product_20261003 import sha
    root = Path(__file__).resolve().parents[1]
    claim_paths = list((root / "results/20261003_cli_products").glob("claims*_integration.json"))
    if not claim_paths:
        pytest.skip("CLI baseline still in progress")
    for claim_path in claim_paths:
        for claim in json.loads(claim_path.read_text(encoding="utf-8"))["claims"]:
            path = root / claim["data_path"]
            assert sha(path.read_bytes()) == claim["data_sha256"]
            value = json.loads(path.read_text(encoding="utf-8"))
            for key in claim["analysis_field"].strip("/").split("/"): value = value[key]
            assert value == claim["value"] and claim["status"] == "SUPPLEMENTARY"


def test_final_effort_receipts_preserve_equal_context_and_no_tool_leakage():
    root = Path(__file__).resolve().parents[1]
    path = root / "results/20261003_cli_products/effort_summary.json"
    if not path.exists(): pytest.skip("Effort sensitivity still in progress")
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["new_calls"] == 22 and body["reused_medium_calls"] == 10
    assert len({r["input_tokens"] for r in body["profiles"].values()}) == 1
    assert all(r["attempted"] == r["completed"] == 10 for r in body["profiles"].values())
    assert all(r["n_scored"] == 9 and r["observed_tool_calls"] == 0 for r in body["profiles"].values())
    assert body["unsupported_efforts"] == ["instant", "none"]
    assert body["status"] == "SUPPLEMENTARY" and body["private_test_run"] is False


class _EmptyMockDirectory:
    """No filesystem writes are needed for mocked subprocess contract checks."""
    def __fspath__(self):
        return str(Path(__file__).resolve().parents[1] / ".runtime/synthetic_empty_cli_test")
    def is_dir(self): return True
    def iterdir(self): return iter(())


def test_request_uses_utf8_stdin_no_shell_and_monotonic_seconds(monkeypatch):
    import subprocess
    import agro_route.cli_product_20261003 as mod
    received = {}
    def complete(args, **kwargs):
        received.update(kwargs)
        stdout = '\n'.join(map(json.dumps, [
            {"type": "item.completed", "item": {"type": "agent_message", "text": '{"choices":["A"]}'}},
            {"type": "turn.completed", "usage": {"input_tokens": 4, "output_tokens": 5}}])).encode()
        return subprocess.CompletedProcess(args, 0, stdout, b"")
    monkeypatch.setattr(mod.subprocess, "run", complete)
    timestamps = iter([10.0, 12.5])
    monkeypatch.setattr(mod.time, "perf_counter", lambda: next(timestamps))
    config = mod.ProductConfig("codex", "codex.exe", "gpt-6-luna", "medium", _EmptyMockDirectory(), "Synthetic")
    result, raw = mod.run_request(config, "Пример")
    assert received["input"] == "Пример".encode("utf-8") and received["shell"] is False
    assert result["latency_s"] == 2.5 and result["prompt_bytes"] == len("Пример".encode())
    assert "ttft_s" not in result and "generation_tps" not in result
    assert result["subscription_cost"] == "SUBSCRIPTION_INCLUDED"


def test_timeout_does_not_capture_partial_secret_diagnostics(monkeypatch):
    import subprocess
    import agro_route.cli_product_20261003 as mod
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("codex", 120, output=b"Bearer sensitive-secret", stderr=b"api_key=private")
    monkeypatch.setattr(mod.subprocess, "run", fail)
    config = mod.ProductConfig("codex", "codex.exe", "gpt-6-luna", "medium", _EmptyMockDirectory(), "Synthetic")
    result, raw = mod.run_request(config, "Synthetic")
    assert result["error"]["type"] == "CLIWallTimeout" and not result["response_received"]
    assert raw["stdout"] == raw["stderr"] == ""

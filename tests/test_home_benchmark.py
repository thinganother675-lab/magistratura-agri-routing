"""HOME-PC harness checks with mocked LM Studio; never performs inference/network."""
import importlib.util
import json
from pathlib import Path
import subprocess

import httpx
import pytest


@pytest.fixture
def runner(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/home_pc_benchmark.py"
    spec = importlib.util.spec_from_file_location("home_pc_benchmark_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not call LM Studio, nvidia-smi or a real API")

    monkeypatch.setattr(module, "command", forbidden)
    monkeypatch.setattr(module.httpx, "Client", forbidden)
    monkeypatch.setattr(module.subprocess, "Popen", forbidden)
    module.actual_resource_headroom = module.resource_headroom
    monkeypatch.setattr(module, "resource_headroom", forbidden)
    return module


def sample(identifier="dev-a", group="group-a", language="ru", category="rule_interpretation"):
    return {
        "id": identifier, "group": group, "split": "dev", "language": language,
        "category": category, "input": "Return NO_RISK.", "context": "",
        "inputs": {}, "expected": {"action": "ANSWER", "answers": ["NO_RISK"]},
        "scoring": "exact_label", "source": "synthetic test fixture",
    }


def output():
    return json.dumps({"action": "ANSWER", "answer": "NO_RISK", "numeric": None, "unit": None, "tool": None})


def dataset_root(tmp_path, records):
    (tmp_path / "data").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "data/benchmark.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return tmp_path


def test_sample_selection_dev_only_stable_and_category_balanced(runner, monkeypatch, tmp_path):
    records = [sample("a", category="a"), sample("b", category="b"), sample("c", category="c")]
    old_test = sample("test-answer-untouched", category="a")
    old_test["split"] = "test"
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, [old_test, *reversed(records)]))
    chosen = runner.choose_samples(3)
    assert [r["category"] for r in chosen] == ["a", "b", "c"]
    assert all(r["split"] == "dev" for r in chosen)
    assert chosen == runner.choose_samples(3)


def test_sample_selection_rotates_groups_inside_each_language(runner, monkeypatch, tmp_path):
    records = [sample("ru-a-0", "ru-a"), sample("ru-a-1", "ru-a"),
               sample("ru-b-0", "ru-b"), sample("ru-b-1", "ru-b"),
               sample("en-c-0", "en-c", "en"), sample("en-c-1", "en-c", "en")]
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, records))
    chosen = runner.choose_samples(3)
    assert [s["language"] for s in chosen] == ["ru", "en", "ru"]
    assert len({s["group"] for s in chosen}) == 3


def test_cli_filters_gold_and_recovers_ansi_stderr_statistics(runner, monkeypatch):
    calls = []
    stats = "\x1b[32mPrediction Stats:\x1b[0m\r\nTokens/Second: 42.5\nTime to First Token: 0.123\nPrompt Tokens: 100\nPredicted Tokens: 25\n"

    def mocked_command(args, timeout=240):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "\x1b[0m" + output(), stats)

    monkeypatch.setattr(runner, "command", mocked_command)
    request = sample()
    request["expected"]["answers"] = ["GOLD_MUST_NOT_REACH_MODEL"]
    result = runner.cli_call("home-fixture", request)
    args = calls[0]
    prompt = json.loads(args[args.index("--prompt") + 1])
    assert set(prompt) == {"input", "context", "inputs"}
    assert "GOLD_MUST_NOT_REACH_MODEL" not in " ".join(args)
    assert result["output"]["answer"] == "NO_RISK" and result["error"] is None
    assert result["stats"] == {"tokens_per_second": 42.5, "time_to_first_token_seconds": .123, "prompt_tokens": 100., "completion_tokens": 25.}
    assert result["usage"] == {"prompt_tokens": 100., "completion_tokens": 25.}


def test_cli_malformed_json_preserves_decoding_statistics(runner, monkeypatch):
    monkeypatch.setattr(runner, "command", lambda args, timeout=240: subprocess.CompletedProcess(args, 0, "invalid JSON", "Tokens/Second: 5.0\n"))
    result = runner.cli_call("home-fixture", sample())
    assert result["output"] is None and result["error"]
    assert result["stats"]["tokens_per_second"] == 5.0
    assert result["raw"] == "invalid JSON"


def test_cli_timeout_is_error_without_exception_text(runner, monkeypatch):
    def timeout(args, limit=240):
        raise subprocess.TimeoutExpired("sensitive-command", limit)

    monkeypatch.setattr(runner, "command", timeout)
    result = runner.cli_call("home-fixture", sample())
    assert result["error"] == {"type": "TimeoutExpired"}
    assert "sensitive-command" not in json.dumps(result)


@pytest.mark.parametrize("payload", [{"choices": []}, ["malformed non-object response"]])
def test_api_malformed_envelope_is_recorded_provider_error(runner, monkeypatch, payload):
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            assert url.startswith("http://127.0.0.1:1234/")
            sent = json.loads(kwargs["json"]["messages"][1]["content"])
            assert "expected" not in sent
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setenv("LOCAL_API_KEY", "invalid-test-fixture-only")
    monkeypatch.setattr(runner.httpx, "Client", FakeClient)
    result = runner.api_call("home-fixture", sample())
    assert result["output"] is None and result["error"]
    assert "invalid-test-fixture-only" not in json.dumps(result)


def test_api_http_auth_error_records_status_without_credential(runner, monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            return httpx.Response(401, json={"error": "Unauthorized"}, request=httpx.Request("POST", url))

    monkeypatch.setenv("LOCAL_API_KEY", "invalid-test-fixture-only")
    monkeypatch.setattr(runner.httpx, "Client", FakeClient)
    result = runner.api_call("home-fixture", sample())
    assert result["error"] == {"type": "HTTPStatusError", "http_status": 401}
    assert result["output"] is None and "invalid-test-fixture-only" not in json.dumps(result)


def test_resource_absence_remains_unknown(runner):
    summary = runner.Monitor().summary()
    assert summary["samples"] == 0
    assert summary["vram_mib_peak_sampled_total"] is None
    assert summary["ram_gib_peak_sampled_system_used"] is None
    assert "entire GPU" in summary["resource_scope"]


@pytest.mark.parametrize('reading', ['nan', 'inf', '-1'])
def test_resource_guard_rejects_invalid_gpu_headroom(runner, monkeypatch, reading):
    from types import SimpleNamespace
    def fake_memory(pointer):
        pointer._obj.available = 4 * 2**30
        return True
    monkeypatch.setattr(runner.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=fake_memory)))
    monkeypatch.setattr(runner, 'command', lambda args, timeout=240: subprocess.CompletedProcess(args, 0, reading, ''))
    with pytest.raises(RuntimeError, match='measurement invalid'):
        runner.actual_resource_headroom()


def test_resource_scope_sampled_gpu_and_system_not_model(runner, monkeypatch):
    monkeypatch.setattr(runner, "command", lambda args, timeout=240: subprocess.CompletedProcess(args, 0, "1000, 75\n", ""))
    monkeypatch.setattr(runner, "ram_used", lambda: 12.5)
    monitor = runner.Monitor()
    monitor.sample()
    summary = monitor.summary()
    assert summary["vram_mib_peak_sampled_total"] == 1000
    assert summary["ram_gib_peak_sampled_system_used"] == 12.5
    assert "entire GPU" in summary["resource_scope"] and "entire system" in summary["resource_scope"]


@pytest.mark.parametrize("mode", ["nonzero", "missing", "malformed"])
def test_resource_poll_failure_is_recorded_and_nonfatal(runner, monkeypatch, mode):
    def failure(args, timeout=240):
        if mode == "missing":
            raise FileNotFoundError("nvidia-smi absent")
        return subprocess.CompletedProcess(args, 1 if mode == "nonzero" else 0, "" if mode == "nonzero" else "not a CSV reading", "")

    monkeypatch.setattr(runner, "command", failure)
    monkeypatch.setattr(runner, "ram_used", lambda: 12.5)
    monitor = runner.Monitor()
    monitor.sample()
    summary = monitor.summary()
    assert summary["resource_poll_errors"]
    assert summary["samples"] == 0 and summary["vram_mib_peak_sampled_total"] is None


def test_run_cli_defaults_marked_unknown_and_zero_cloud_calls(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, [sample()]))
    monkeypatch.setattr(runner, "load_env", lambda: None)
    model = runner.CANDIDATES[0][0]
    calls = []

    def cli_inventory(*args):
        return [{"modelKey": model, "sizeBytes": 123, "quantization": {"name": "test-fixture"}}] if args[0] == "ls" else []

    def command(args, timeout=240):
        assert args[1] in ("load", "unload")
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "mocked", "")

    class FakeMonitor(runner.Monitor):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def local(identifier, request):
        return {"output": json.loads(output()), "error": None, "raw": output(), "stats": {}, "usage": {}, "latency_ms": 1000, "cost_usd": 0.}

    monkeypatch.setattr(runner, "cli_json", cli_inventory)
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "Monitor", FakeMonitor)
    monkeypatch.setattr(runner, "cli_call", local)
    runner.run(1, [model], "cli")
    directories = list((tmp_path / "results").iterdir())
    assert len(directories) == 1
    manifest = json.loads((directories[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "completed" and manifest["cloud_calls"] == 0
    assert manifest["temperature"] == "CLI default UNKNOWN"
    assert manifest["max_tokens"] == "CLI default UNKNOWN"
    assert manifest["phase"] == "development_only" and not manifest["historical_test_used_for_selection"]
    assert manifest["models"][model]["summary"]["decode_tps_median"] is None
    assert [args[1] for args in calls] == ["load", "load", "unload"]
    assert "--estimate-only" in calls[0] and "--estimate-only" not in calls[1]


def test_offline_trace_replay_uses_deterministic_gate_without_cloud(runner):
    # Cached-model callbacks do not measure original inference time. Reporting
    # must label the reconstructed trace latency, not decide() wall time.
    def forbidden(request):
        raise AssertionError("No inference/cloud call should occur for a complete deterministic request")

    request = {"input": "Calculate rainfall deficit.", "context": "", "inputs": {"target": 10, "rain": [3], "precipitation_unit": "mm"}}
    result = runner.decide(request, "offline", forbidden, forbidden, cloud_available=False)
    assert result["route"] == "DETERMINISTIC_TOOL" and result["output"]["numeric"] == 7
    assert result["cloud_calls"] == 0 and result["local_calls"] == 0


def test_unknown_model_rejected_before_environment_or_cli(runner, monkeypatch):
    def forbidden_environment():
        raise AssertionError("Unknown model must be rejected before importing credentials")

    monkeypatch.setattr(runner, "load_env", forbidden_environment)
    with pytest.raises(ValueError, match="Unknown candidate"):
        runner.run(1, ["uninstalled-or-unrecognized"], "cli")


def test_missing_inventory_model_rejected_before_loading_or_outputs(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, [sample()]))
    monkeypatch.setattr(runner, "load_env", lambda: None)
    monkeypatch.setattr(runner, "cli_json", lambda *args: [])
    with pytest.raises(ValueError, match="absent from inventory"):
        runner.run(1, [runner.CANDIDATES[0][0]], "cli")
    assert list((tmp_path / "results").iterdir()) == []


@pytest.mark.parametrize("failure", ["nonzero", "still_present"])
def test_initial_own_unload_failure_stops_before_new_load(runner, monkeypatch, tmp_path, failure):
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, [sample()]))
    monkeypatch.setattr(runner, "load_env", lambda: None)
    model = runner.CANDIDATES[0][0]
    identifier = "home-previous-own-model"
    commands = []
    monkeypatch.setattr(runner, "cli_json", lambda *args:
                        [{"modelKey": model}] if args[0] == "ls" else [{"identifier": identifier}])

    def command(args, timeout=240):
        assert args == [runner.LMS, "unload", identifier]
        commands.append(args)
        return subprocess.CompletedProcess(args, 1 if failure == "nonzero" else 0, "", "")

    monkeypatch.setattr(runner, "command", command)
    with pytest.raises(RuntimeError, match="previous model could not be unloaded"):
        runner.run(1, [model], "cli")
    assert len(commands) == 1 and list((tmp_path / "results").iterdir()) == []


def configure_mock_run(runner, monkeypatch, tmp_path, *, load_code=0, estimate_code=0, model_keys=None):
    """A fake backend records exact loads/unloads; no child process or GPU work."""
    monkeypatch.setattr(runner, "ROOT", dataset_root(tmp_path, [sample()]))
    monkeypatch.setattr(runner, "load_env", lambda: None)
    model = runner.CANDIDATES[0][0]
    model_keys = model_keys or [model]
    state = {"loaded": [], "commands": [], "inferences": []}

    def cli_json(*args):
        if args[0] == "ls":
            return [{"modelKey": key, "sizeBytes": 123, "quantization": {"name": "test-fixture"}}
                    for key in model_keys]
        return [{"identifier": identifier} for identifier in state["loaded"]]

    def command(args, timeout=240):
        state["commands"].append(args)
        if args[1] == "load":
            if "--estimate-only" in args:
                return subprocess.CompletedProcess(args, estimate_code, "mock estimate", "")
            if load_code == 0:
                state["loaded"] = [args[args.index("--identifier") + 1]]
            return subprocess.CompletedProcess(args, load_code, "mock load", "")
        assert args[1] == "unload"
        state["loaded"] = [identifier for identifier in state["loaded"] if identifier != args[2]]
        return subprocess.CompletedProcess(args, 0, "mock unload", "")

    class FakeMonitor(runner.Monitor):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def local(identifier, request):
        state["inferences"].append(identifier)
        return {"output": json.loads(output()), "error": None, "raw": output(),
                "stats": {}, "usage": {}, "latency_ms": 1, "cost_usd": 0.}

    monkeypatch.setattr(runner, "cli_json", cli_json)
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "Monitor", FakeMonitor)
    monkeypatch.setattr(runner, "cli_call", local)
    return model, state


def saved_manifest(tmp_path):
    directories = list((tmp_path / "results").iterdir())
    assert len(directories) == 1
    return json.loads((directories[0] / "manifest.json").read_text(encoding="utf-8"))


def test_nonzero_load_records_failure_and_never_infers(runner, monkeypatch, tmp_path):
    model, state = configure_mock_run(runner, monkeypatch, tmp_path, load_code=7)
    with pytest.raises(RuntimeError, match="incomplete loading"):
        runner.run(1, [model], "cli")
    manifest = saved_manifest(tmp_path)
    assert manifest["state"] == "stopped_after_uncertain_load"
    assert manifest["models"][model]["phase_error"] == {"type": "LoadNonzero", "returncode": 7}
    assert not manifest["models"][model]["load_success"]
    assert state["inferences"] == []
    assert state["commands"][-1] == [runner.LMS, "unload", "home-" + model]


def test_nonzero_estimate_prevents_load_without_claiming_success(runner, monkeypatch, tmp_path):
    model, state = configure_mock_run(runner, monkeypatch, tmp_path, estimate_code=9)
    runner.run(1, [model], "cli")
    manifest = saved_manifest(tmp_path)
    assert manifest["state"] == "completed_with_model_failures"
    assert manifest["models"][model]["preflight_estimate_returncode"] == 9
    assert not manifest["models"][model].get("load_attempted")
    assert len(state["commands"]) == 1 and "--estimate-only" in state["commands"][0]
    assert state["inferences"] == []


def test_aborted_pending_load_stops_next_model_even_if_not_in_ps(runner, monkeypatch, tmp_path):
    models = [key for key, _ in runner.CANDIDATES[:2]]
    model, state = configure_mock_run(runner, monkeypatch, tmp_path, model_keys=models)
    def aborted_load(args, log_path, meta):
        meta["resource_guard_stop"] = {"ram_available_gib": 1.9, "gpu_free_mib": 2048}
        # A backend load might still be pending, so ps deliberately returns [].
        raise RuntimeError("Model loading stopped by resource guard")

    monkeypatch.setattr(runner, "guarded_load", aborted_load)
    with pytest.raises(RuntimeError, match="incomplete loading"):
        runner.run(1, models, "cli", guard=True)
    assert state["inferences"] == []
    assert state["commands"][-1] == [runner.LMS, "unload", "home-" + model]
    assert len(state["commands"]) == 2  # First estimate + exact cleanup, no next load.
    manifest = saved_manifest(tmp_path)
    assert manifest["state"] == "stopped_after_uncertain_load"
    assert list(manifest["models"]) == [model]


@pytest.mark.parametrize("headroom", [
    {"ram_available_gib": 2.99, "gpu_free_mib": 4096},
    {"ram_available_gib": 10, "gpu_free_mib": 1023},
])
def test_guard_rejects_low_baseline_without_spawning_process(runner, monkeypatch, tmp_path, headroom):
    monkeypatch.setattr(runner, "resource_headroom", lambda: headroom)
    meta = {}
    with pytest.raises(RuntimeError, match="baseline headroom"):
        runner.guarded_load(["mock-lms", "load", "home-fixture"], tmp_path / "load.txt", meta)
    assert meta["headroom_before_load"] == headroom
    assert not (tmp_path / "load.txt").exists()


@pytest.mark.parametrize("headroom", [
    {"ram_available_gib": 1.99, "gpu_free_mib": 4096},
    {"ram_available_gib": 10, "gpu_free_mib": 511},
])
def test_guard_kills_its_cli_on_loading_pressure(runner, monkeypatch, tmp_path, headroom):
    readings = iter([{"ram_available_gib": 10, "gpu_free_mib": 4096}, headroom])
    monkeypatch.setattr(runner, "resource_headroom", lambda: next(readings))
    calls = []

    class FakeProcess:
        returncode = None
        def poll(self):
            return self.returncode
        def kill(self):
            calls.append("kill")
            self.returncode = -9
        def wait(self, timeout):
            calls.append(("wait", timeout))
            return self.returncode

    process = FakeProcess()
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: process)
    meta = {}
    with pytest.raises(RuntimeError, match="resource guard"):
        runner.guarded_load(["mock-lms", "load", "home-fixture"], tmp_path / "load.txt", meta)
    assert calls == ["kill", ("wait", 10)]
    assert meta["resource_guard_stop"] == headroom


def test_guard_measurement_failure_kills_active_own_cli(runner, monkeypatch, tmp_path):
    readings = iter([{"ram_available_gib": 10, "gpu_free_mib": 4096}, RuntimeError("guard unavailable")])
    def resource():
        value = next(readings)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(runner, "resource_headroom", resource)
    calls = []
    class FakeProcess:
        returncode = None
        def poll(self):
            return self.returncode
        def kill(self):
            calls.append("kill")
            self.returncode = -9
        def wait(self, timeout):
            calls.append("wait")
            return self.returncode

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    with pytest.raises(RuntimeError, match="guard unavailable"):
        runner.guarded_load(["mock-lms", "load"], tmp_path / "load.txt", {})
    assert calls == ["kill", "wait"]


def test_pressure_before_inference_unloads_exact_identifier(runner, monkeypatch, tmp_path):
    model, state = configure_mock_run(runner, monkeypatch, tmp_path)
    def guarded(args, log_path, meta):
        state["loaded"] = [args[args.index("--identifier") + 1]]
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(runner, "guarded_load", guarded)
    monkeypatch.setattr(runner, "resource_headroom", lambda:
                        {"ram_available_gib": 1.5, "gpu_free_mib": 2048})
    # A guard interruption may intentionally stop the entire run after cleanup.
    try:
        runner.run(1, [model], "cli", guard=True)
    except RuntimeError:
        pass
    assert state["inferences"] == [] and state["loaded"] == []
    assert state["commands"][-1] == [runner.LMS, "unload", "home-" + model]
    manifest = saved_manifest(tmp_path)
    assert manifest["state"] != "completed"
    assert manifest["models"][model]["resource_guard_stop"]["ram_available_gib"] == 1.5

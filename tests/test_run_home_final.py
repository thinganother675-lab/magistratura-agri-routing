"""Mock-only acceptance checks; no models, HTTP or paid calls are used."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_home_final as final


@pytest.fixture
def frozen(tmp_path):
    for relative in final.DEPENDENCIES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((final.ROOT / relative).read_bytes())
    samples = []
    for category, n in final.CATEGORIES.items():
        for i in range(n):
            samples.append({"id": f"holdout_{category}_{i}", "group": f"family_{category}_{i//2}",
                            "split": "home_final", "category": category, "language": "en" if i % 2 == 0 else "ru",
                            "input": "A supplied test question", "context": "OK is supported", "inputs": {},
                            "expected": {"action": "ANSWER", "answers": ["OK"]}, "scoring": "exact"})
    (tmp_path / "data").mkdir()
    dataset = tmp_path / "data/home_holdout_20261001.jsonl"
    dataset.write_text("\n".join(json.dumps(s) for s in samples) + "\n", encoding="utf-8")
    protocol = {"status": "FROZEN", "n": 150, "dataset_path": "data/home_holdout_20261001.jsonl",
                "dataset_sha256": final.sha(dataset), "holdout_ids": [s["id"] for s in samples],
                "prompt_sha256": hashlib.sha256(final.SYSTEM_PROMPT.encode()).hexdigest(),
                "code_sha256": {relative: final.sha(tmp_path / relative) for relative in final.DEPENDENCIES},
                "local": deepcopy(final.LOCAL), "cloud": deepcopy(final.CLOUD), "policies": list(final.METHODS),
                "execution_seed": 20261001, "budget_cap_usd": .25, "planning_input_tokens_per_call": 6000,
                "criteria": deepcopy(final.CRITERIA), "statistic": deepcopy(final.STATISTIC)}
    path = tmp_path / "protocol.json"
    final.write_new(path, protocol)
    (tmp_path / "results").mkdir()
    return tmp_path, path, protocol, samples


def record(answer="OK", *, provider="local", error=None, cost=0.):
    return {"provider": provider, "output": {"action": "ANSWER", "answer": answer, "numeric": None,
                                              "unit": None, "tool": None}, "error": error, "raw": {},
            "latency_ms": 1., "usage": {}, "timing": {}, "cost_usd": cost}


def test_plan_is_zero_http_and_zero_key_access(frozen, monkeypatch):
    root, path, _, _ = frozen
    def forbidden(*args, **kwargs):
        raise AssertionError("Plan must not access live provider/keys")
    monkeypatch.setattr(final, "resolve_api_key", forbidden)
    monkeypatch.setattr(final.httpx, "Client", forbidden)
    plan = final.run(path, root=root)
    assert plan["max_cloud_calls"] == 450
    assert plan["planning_cost_estimate_usd"] == pytest.approx(.14256)
    assert not list((root / "results").iterdir())


def test_sha_reads_in_bounded_blocks(tmp_path, monkeypatch):
    path = tmp_path / "weight.bin"
    contents = b"weight" * 1024
    path.write_bytes(contents)
    original_open = Path.open
    observed = []
    class GuardedReader:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def read(self, size=-1):
            assert 0 < size <= 4 * 1024 * 1024
            observed.append(size)
            return self.stream.read(size)
    def guarded_open(self, mode="r", *args, **kwargs):
        stream = original_open(self, mode, *args, **kwargs)
        return GuardedReader(stream) if self == path and mode == "rb" else stream
    monkeypatch.setattr(Path, "open", guarded_open)
    assert final.sha(path) == hashlib.sha256(contents).hexdigest()
    assert observed == [4 * 1024 * 1024, 4 * 1024 * 1024]


def test_optional_main_weight_metadata_supported(frozen):
    root, path, protocol, _ = frozen
    protocol["local"].update(gguf_sha256="c1ac61e3af04b40c7688dfe0686c54d68ff5ed26178a56f0b18c8a0e2b94db83",
                             file_size_bytes=14556687680)
    path.write_text(json.dumps(protocol), encoding="utf-8")
    checked, _, _ = final.validate_protocol(path, root)
    assert checked["local"]["file_size_bytes"] == 14556687680


def test_preflight_checks_main_file_separately_from_catalog_total(tmp_path, monkeypatch):
    relative = "unsloth/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-UD-IQ4_NL_XL.gguf"
    weight = tmp_path / ".lmstudio/models" / relative
    weight.parent.mkdir(parents=True)
    weight.write_bytes(b"small mocked main gguf")
    native = {"key": final.LOCAL["model"], "size_bytes": 16847892149,
              "quantization": {"name": "IQ4_NL_XL"}, "loaded_instances": []}
    monkeypatch.setattr(final.api, "native_models", lambda *args: [native])
    monkeypatch.setattr(final.home, "cli_json", lambda *args: [{"modelKey": final.LOCAL["model"], "path": relative}])
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(final.home, "resource_headroom", lambda: {"ram_available_gib": 10, "gpu_free_mib": 4000})
    monkeypatch.setattr(final.home, "command", lambda *args: SimpleNamespace(returncode=0, stdout="safe", stderr=""))
    protocol = {"local": {**final.LOCAL, "gguf_sha256": final.sha(weight), "file_size_bytes": weight.stat().st_size}}
    _, metadata, _, _ = final.preflight_local(protocol, None, "MOCK_SECRET")
    assert metadata["gguf_file_size_bytes"] == weight.stat().st_size
    assert metadata["catalog_size_bytes"] == 16847892149
    protocol["local"]["file_size_bytes"] = 16847892149
    with pytest.raises(RuntimeError, match="frozen weight file"):
        final.preflight_local(protocol, None, "MOCK_SECRET")


@pytest.mark.parametrize("mutation", ["status", "hash", "seed", "schema", "prices", "policy", "split", "ids", "code"])
def test_rejects_frozen_protocol_mutation(frozen, mutation):
    root, path, protocol, samples = frozen
    if mutation == "status": protocol["status"] = "DRAFT"
    elif mutation == "hash": protocol["dataset_sha256"] = "0" * 64
    elif mutation == "seed": protocol["local"]["seed"] = 7
    elif mutation == "schema": protocol["local"]["response_format"] = "json_object"
    elif mutation == "prices": protocol["cloud"]["input_usd_per_m"] = 0
    elif mutation == "policy": protocol["policies"] = ["cloud"]
    elif mutation == "code": (root / "src/agro_route/routing.py").write_text("changed", encoding="utf-8")
    else:
        if mutation == "split": samples[0]["split"] = "dev"
        else: samples[1]["id"] = samples[0]["id"]
        data = root / protocol["dataset_path"]
        data.write_text("\n".join(json.dumps(s) for s in samples), encoding="utf-8")
        protocol["dataset_sha256"] = final.sha(data)
    path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError): final.validate_protocol(path, root)


def test_schedules_every_policy_per_case_reproducibly(frozen):
    _, _, _, samples = frozen
    a = final.schedule(samples)
    assert a == final.schedule(samples)
    assert len(a) == 150 and all(set(row["methods"]) == set(final.METHODS) for row in a)
    assert len({tuple(row["methods"]) for row in a}) > 1


def test_five_policies_independent_calls_and_no_gold():
    observed = []
    sample = {"input": "Read", "context": "OK supported", "inputs": {}}
    def local(request):
        assert set(request).issubset({"input", "context", "inputs"})
        observed.append("local"); return record()
    def cloud(request):
        observed.append("cloud"); return record(provider="cloud", cost=.01)
    decisions = [final.measured_decision(sample, method, local, cloud) for method in final.METHODS]
    assert observed.count("local") == 3 and observed.count("cloud") == 2
    assert sum(d["local_calls"] for d in decisions) == 3
    assert all(d["status"] == "MEASURED" for d in decisions)


def test_no_context_hybrid_skips_local_offline_abstains():
    def forbidden(request): raise AssertionError("No unnecessary local inference")
    req = {"input": "Use supplied risk rule", "inputs": {}}
    hybrid = final.measured_decision(req, "hybrid", forbidden, lambda _: record(provider="cloud"))
    offline = final.measured_decision(req, "offline", forbidden, forbidden)
    assert hybrid["cloud_calls"] == 1 and hybrid["local_calls"] == 0
    assert offline["output"]["action"] == "ABSTAIN" and offline["trace"] == []


def test_hard_gate_preserves_real_numeric_and_missing_output():
    def forbidden(request): raise AssertionError("Deterministic gate must not call model")
    req = {"input": "Calculate GDD", "inputs": {"tmin": [10], "tmax": [20], "base": 5, "temperature_unit": "C"}}
    # Use the public tool contract from the frozen code; valid gate or missing gate
    # must be preserved exactly rather than rebuilt into a schema/proxy.
    gate = final.hard_gate(req)
    assert gate["output"]["numeric"] == 10 and gate["tool_calls"] == 1
    for method in ("hybrid", "offline", "tool_cloud"):
        result = final.measured_decision(req, method, forbidden, forbidden)
        assert result["output"] == gate["output"] and result["tool_calls"] == gate["tool_calls"]
    missing = final.measured_decision({"input": "Calculate GDD", "inputs": {}}, "hybrid", forbidden, forbidden)
    assert missing["output"]["action"] == "ASK_FOR_DATA" and missing["tool_calls"] == 0


def test_cloud_length_rejected_even_if_valid_json():
    r = record(provider="cloud", cost=.2)
    r.update(raw={"choices": [{"finish_reason": "length"}]}, usage={"prompt_tokens": 100, "completion_tokens": 512})
    out = final.strict_cloud_record(r)
    assert out["output"] is None and out["error"]["type"] == "IncompleteCompletion"
    assert out["cost_usd"] == pytest.approx((100 * .04 + 512 * .15) / 1e6)


def calls_fixture(tmp_path, local=None, cloud=None, headroom=None, stop=lambda: None):
    manifest = {"cloud_calls_actual": 0, "local_calls_actual": 0}
    final.write_new(tmp_path / "manifest.json", manifest)
    calls = final.Calls(local or (lambda _: record()), cloud or (lambda _: record(provider="cloud", cost=.01)),
                        manifest, tmp_path, secrets=("MOCK_SECRET",), headroom=headroom or (lambda: {"ram_available_gib": 10, "gpu_free_mib": 4096}),
                        on_local_stop=stop)
    return calls, manifest


def test_auth_failure_stops_cloud_but_local_and_gate_continue(tmp_path):
    calls, m = calls_fixture(tmp_path, cloud=lambda _: record(provider="cloud", error={"type": "HTTPStatusError", "http_status": 401}, cost=None))
    first = final.measured_decision({"input": "Read"}, "cloud", calls.local, calls.cloud)
    second = final.measured_decision({"input": "Read"}, "cloud", calls.local, calls.cloud)
    local = final.measured_decision({"input": "Read"}, "local", calls.local, calls.cloud)
    assert first["status"] == "MEASURED" and second["status"] == "NOT_RUN"
    assert m["cloud_calls_actual"] == 1 and m["local_calls_actual"] == 1 and local["status"] == "MEASURED"
    assert calls.unknown_cost_calls == 1 and second["cost_usd"] == 0


def test_guard_stops_and_unloads_without_incrementing_call(tmp_path):
    stopped = []
    calls, m = calls_fixture(tmp_path, headroom=lambda: {"ram_available_gib": 1.9, "gpu_free_mib": 2000}, stop=lambda: stopped.append(True))
    out = final.measured_decision({"input": "Read"}, "local", calls.local, calls.cloud)
    assert out["status"] == "NOT_RUN" and out["local_calls"] == 0 and m["local_calls_actual"] == 0
    assert stopped == [True]


def test_unavailable_local_hybrid_uses_cloud_offline_gracefully_abstains():
    def unavailable(_): raise final.ProviderBlocked("local", {"type": "resource_guard"})
    request = {"input": "Read", "context": "supported OK"}
    hybrid = final.measured_decision(request, "hybrid", unavailable, lambda _: record(provider="cloud"))
    offline = final.measured_decision(request, "offline", unavailable, unavailable)
    assert hybrid["status"] == "MEASURED" and hybrid["local_calls"] == 0 and hybrid["cloud_calls"] == 1
    assert hybrid["degraded_provider"]["provider"] == "local"
    assert offline["status"] == "MEASURED" and offline["output"]["action"] == "ABSTAIN" and offline["trace"] == []


def test_completed_local_attempt_preserved_when_cloud_stage_blocked():
    def unavailable(_): raise final.ProviderBlocked("cloud", "auth")
    result = final.measured_decision({"input": "Read", "context": "not supporting the answer"}, "hybrid", lambda _: record(), unavailable)
    assert result["status"] == "NOT_RUN" and result["local_calls"] == 1 and result["cloud_calls"] == 0
    assert len(result["trace"]) == 1 and result["output"] is None


def test_pending_paid_attempt_is_unknown_on_interruption(tmp_path):
    def interrupt(_): raise KeyboardInterrupt()
    calls, m = calls_fixture(tmp_path, cloud=interrupt)
    with pytest.raises(KeyboardInterrupt): calls.cloud({"input": "Read"})
    assert m["cloud_calls_actual"] == 1 and m["cloud_unknown_cost_calls"] == 1
    events = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(events) == 1 and events[0]["event"] == "call_started"


def test_budget_guard_and_secret_redaction(tmp_path):
    calls, m = calls_fixture(tmp_path, cloud=lambda _: {**record(provider="cloud", cost=None), "raw": {"echo": "MOCK_SECRET"}})
    calls.cloud({"input": "Read"})
    calls.known_cost = .2499
    with pytest.raises(final.ProviderBlocked): calls.cloud({"input": "Read"})
    assert m["cloud_calls_actual"] == 1 and calls.unknown_cost_calls == 1
    assert "MOCK_SECRET" not in (tmp_path / "manifest.json").read_text(encoding="utf-8")


def test_not_run_excluded_from_quality_and_recorded_ids():
    sample = {"id": "h", "input": "Read", "context": "OK", "category": "extractive_qa", "language": "en"}
    def blocked(_): raise final.ProviderBlocked("cloud", "auth")
    r = final.measured_decision(sample, "cloud", blocked, blocked)
    out = final.summarize([{"sample": sample, "method": "cloud", "result": r, "score": None}], [sample])
    assert out["cloud"]["n"] == 0 and out["cloud"]["quality"] is None and out["cloud"]["unattempted_ids"] == ["h"]


def test_mocked_live_driver_journal_once_claim_and_independent_counts(frozen, monkeypatch):
    root, path, _, _ = frozen
    state = {"identifier": None, "local": 0, "cloud": 0}
    native = {"key": final.LOCAL["model"], "size_bytes": 16847892149, "quantization": {"name": "IQ4_NL_XL"},
              "capabilities": {"reasoning": {"allowed_options": ["off", "on"]}}, "loaded_instances": []}
    def catalog(*args):
        value = deepcopy(native)
        if state["identifier"]:
            value["loaded_instances"] = [{"id": state["identifier"], "config": {"context_length": 4096, "parallel": 1}}]
        return [value]
    def command(args, *rest):
        if "unload" in args: state["identifier"] = None
        return SimpleNamespace(returncode=0, stdout="safe", stderr="")
    def load(args, log, meta):
        state["identifier"] = args[args.index("--identifier") + 1]
        log.write_text("safe\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)
    def local_call(*args):
        state["local"] += 1
        return record()
    class Cloud:
        def __init__(self, *args, **kwargs): pass
        def call(self, request):
            assert set(request) <= {"input", "context", "inputs"}
            state["cloud"] += 1
            return {**record(provider="cloud", cost=.00001), "raw": {"choices": [{"finish_reason": "stop"}]},
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    class Monitor:
        rows = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def summary(self): return {"vram_mib_peak_sampled_total": 1, "ram_gib_peak_sampled_system_used": 1}
    monkeypatch.setattr(final, "resolve_api_key", lambda provider, **kw: ("MOCK_SECRET_"+provider, "mock:"+provider))
    monkeypatch.setattr(final, "hardware", lambda: {"mock": True})
    monkeypatch.setattr(final.api, "native_models", catalog)
    monkeypatch.setattr(final.api, "api_call", local_call)
    monkeypatch.setattr(final.home, "command", command)
    monkeypatch.setattr(final.home, "guarded_load", load)
    monkeypatch.setattr(final.home, "cli_json", lambda *args: [])
    monkeypatch.setattr(final.home, "Monitor", Monitor)
    monkeypatch.setattr(final.home, "resource_headroom", lambda: {"ram_available_gib": 10, "gpu_free_mib": 5000})
    monkeypatch.setattr(final, "Model", Cloud)
    directory = final.run(path, root=root, execute=True)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    lines = [json.loads(line) for line in (directory / "raw_decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 750 and state["local"] == 450 and state["cloud"] == 300
    assert manifest["state"] == "completed" and manifest["local_load_metadata"]["unload_success"]
    assert state["identifier"] is None and all(row["result"]["status"] == "MEASURED" for row in lines)
    with pytest.raises(RuntimeError, match="already has a final execution claim"):
        final.run(path, root=root, execute=True)

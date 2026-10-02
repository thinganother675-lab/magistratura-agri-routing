"""Storage-only manual recovery checks; all model/provider actions are mocks."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_home_final_recovery as recovery

final = recovery.final
SOURCE = final.ROOT / "results/20261002_043909Z_5d0044d9_final"


@pytest.fixture
def authorized(tmp_path):
    protocol = json.loads((SOURCE / "protocol_copy.json").read_text(encoding="utf-8"))
    for relative in [*protocol["code_sha256"], protocol["dataset_path"]]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(final.ROOT / relative, path)
    original = tmp_path / "results" / SOURCE.name
    shutil.copytree(SOURCE, original)
    protocol_path = tmp_path / "protocol.json"
    shutil.copyfile(SOURCE / "protocol_copy.json", protocol_path)
    # Freeze protocol SHA is the actual authored file, not the pretty run copy.
    protocol_path.write_bytes((final.ROOT / "experiments/HOME_PROTOCOL_2026-10-01.json").read_bytes())
    claim = final.ROOT / "results" / (".home_final_" + protocol["dataset_sha256"] + "_claim.json")
    shutil.copyfile(claim, tmp_path / "results" / claim.name)
    auth = {"status": "MANUAL_RECOVERY_AUTHORIZED", "interruption_reason": "windows_manifest_replace_failure",
            "original_run_id": original.name, "protocol_sha256": final.sha(protocol_path),
            "recovery_driver_sha256": final.sha(recovery.__file__), "authorized_utc": final.now(),
            "original_files_sha256": recovery.original_inventory(original),
            "resume_after_completed_cases": 6, "original_calls": {"local": 10, "cloud": 12}}
    auth_path = tmp_path / "authorization.json"
    final.write_new(auth_path, auth)
    return tmp_path, protocol_path, original, auth_path, auth


def test_recovery_plan_no_keys_http_or_claim(authorized, monkeypatch):
    root, protocol, original, auth, _ = authorized
    def forbidden(*args, **kwargs): raise AssertionError("Plan must not read keys or access providers")
    monkeypatch.setattr(final, "resolve_api_key", forbidden)
    monkeypatch.setattr(final.httpx, "Client", forbidden)
    plan = recovery.run(protocol, original, auth, root=root)
    assert plan["segment_start"] == 6 and plan["remaining_n"] == 144
    assert plan["target_segment_decisions"] == 720
    assert plan["original_call_baseline"] == {"local": 10, "cloud": 12}
    assert plan["original_known_cloud_cost_usd"] == pytest.approx(.00054914)
    assert plan["original_unknown_cost_calls"] == 1
    assert not list((root / "results").glob("*continuation*"))


@pytest.mark.parametrize("mutation", ["authorization", "source", "pending", "alignment"])
def test_rejects_unauthorized_or_unsafe_resume(authorized, mutation):
    root, protocol, original, auth_path, auth = authorized
    if mutation == "authorization":
        auth["status"] = "DRAFT"
    elif mutation == "source":
        (original / "manifest.tmp").write_text("changed", encoding="utf-8")
    elif mutation == "pending":
        event = {"event": "call_started", "provider": "local", "sample_id": "unstarted-case7", "method": "local", "attempt_number_provider": 11}
        with (original / "attempts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        auth["original_files_sha256"] = recovery.original_inventory(original)
    else:
        path = original / "raw_decisions.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0], rows[1] = rows[1], rows[0]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        auth["original_files_sha256"] = recovery.original_inventory(original)
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    with pytest.raises(ValueError):
        recovery.validate_recovery(protocol, original, auth_path, root=root)


def test_storage_retry_does_not_rewrite_or_repeat_generation(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text("old", encoding="utf-8")
    original_replace = Path.replace
    observed, sleeps = [], []
    def transient(self, target):
        observed.append(self.read_text(encoding="utf-8"))
        if len(observed) < 3: raise PermissionError("Windows reader lock")
        return original_replace(self, target)
    monkeypatch.setattr(Path, "replace", transient)
    recovery.atomic_update(path, {"state": "valid"}, sleeper=sleeps.append)
    assert len(observed) == 3 and len(set(observed)) == 1
    assert len(sleeps) == 2 and json.loads(path.read_text(encoding="utf-8")) == {"state": "valid"}
    assert not list(tmp_path.glob("*.tmp"))


def test_storage_retry_is_bounded(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text("old", encoding="utf-8")
    def locked(*args): raise PermissionError("Windows reader lock")
    monkeypatch.setattr(Path, "replace", locked)
    times = iter([0., .1, .1, .6])
    with pytest.raises(PermissionError):
        recovery.atomic_update(path, {"state": "new"}, deadline_s=.5, clock=lambda: next(times), sleeper=lambda _: None)
    assert path.read_text(encoding="utf-8") == "old"


def test_mock_live_recovery_exact720_new_decisions_cumulative_budget(authorized, monkeypatch):
    root, protocol, original, auth_path, auth = authorized
    hashes_before = recovery.original_inventory(original)
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
    def record(provider):
        return {"provider": provider, "output": {"action": "ANSWER", "answer": "OK", "numeric": None, "unit": None, "tool": None},
                "error": None, "raw": {}, "latency_ms": 1., "usage": {}, "timing": {}, "cost_usd": 0.}
    def local_call(*args):
        state["local"] += 1
        return record("local")
    class Cloud:
        def __init__(self, *args, **kwargs): pass
        def call(self, request):
            assert set(request) <= {"input", "context", "inputs"}
            state["cloud"] += 1
            return {**record("cloud"), "raw": {"choices": [{"finish_reason": "stop"}]},
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    class Monitor:
        rows = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def summary(self): return {"vram_mib_peak_sampled_total": 1, "ram_gib_peak_sampled_system_used": 1}
    monkeypatch.setattr(final, "resolve_api_key", lambda provider, **kw: ("MOCK_SECRET_"+provider, "mock:"+provider))
    monkeypatch.setattr(final, "hardware", lambda: {"mock": True})
    monkeypatch.setattr(final, "preflight_local", lambda *args: ([native], {"mock": True}, {"ram_available_gib": 10, "gpu_free_mib": 5000}, command([])))
    monkeypatch.setattr(final.api, "native_models", catalog)
    monkeypatch.setattr(final.api, "api_call", local_call)
    monkeypatch.setattr(final.home, "command", command)
    monkeypatch.setattr(final.home, "guarded_load", load)
    monkeypatch.setattr(final.home, "cli_json", lambda *args: [])
    monkeypatch.setattr(final.home, "Monitor", Monitor)
    monkeypatch.setattr(final.home, "resource_headroom", lambda: {"ram_available_gib": 10, "gpu_free_mib": 5000})
    monkeypatch.setattr(final, "Model", Cloud)
    previous_update = final.update
    directory = recovery.run(protocol, original, auth_path, root=root, execute=True)
    assert final.update is previous_update
    rows = [json.loads(line) for line in (directory / "raw_decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    old_rows = [json.loads(line) for line in (original / "raw_decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 720 and len(old_rows) == 30
    assert not ({r["sample"]["id"] for r in rows} & {r["sample"]["id"] for r in old_rows})
    assert len({(r["sample"]["id"], r["method"]) for r in rows + old_rows}) == 750
    ordering = json.loads((original / "schedule.json").read_text(encoding="utf-8"))
    assert [(r["sample"]["id"], r["method"]) for r in rows] == [(e["sample_id"], m) for e in ordering[6:] for m in e["methods"]]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["local_calls_actual"] == 10 + state["local"]
    assert manifest["cloud_calls_actual"] == 12 + state["cloud"]
    assert manifest["cloud_unknown_cost_calls"] == 1
    assert manifest["cloud_known_cost_estimate_usd"] == pytest.approx(.00054914 + state["cloud"] * .0000055)
    assert manifest["completed_segment_cases"] == 144 and manifest["completed_sample_groups"] == 150
    assert recovery.original_inventory(original) == hashes_before
    assert state["identifier"] is None
    with pytest.raises(RuntimeError, match="manual continuation claim"):
        recovery.run(protocol, original, auth_path, root=root, execute=True)

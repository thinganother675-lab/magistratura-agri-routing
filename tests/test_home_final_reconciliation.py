"""Mock-only checks of unrepeated, frozen HOME segment evidence and its union."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from agro_route.evaluation import score


REAL_ROOT = Path(__file__).resolve().parents[1]


def helper():
    spec = importlib.util.spec_from_file_location("home_final_reconcile_test", REAL_ROOT / "scripts/reconcile_home_final_segments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


@pytest.fixture
def segments(tmp_path, monkeypatch):
    module = helper(); monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/analyze_home_final.py").write_bytes((REAL_ROOT / "scripts/analyze_home_final.py").read_bytes())
    (tmp_path / "data").mkdir()
    samples = [{"id": str(i), "group": "family-" + str(i // 2), "category": "rule_interpretation",
                "language": "en", "input": "Supplied test rule", "scoring": "exact",
                "expected": {"action": "ANSWER", "answers": ["OK"]}} for i in range(4)]
    dataset = tmp_path / "data/synthetic.jsonl"; jsonl(dataset, samples)
    protocol = {"status": "FROZEN", "n": 4, "holdout_ids": [s["id"] for s in samples],
                "dataset_path": "data/synthetic.jsonl", "dataset_sha256": module.sha(dataset),
                "code_sha256": {"scripts/analyze_home_final.py": module.sha(tmp_path / "scripts/analyze_home_final.py")}}
    schedule = [{"sample_id": sample["id"], "methods": list(module.METHODS)} for sample in samples]
    directories = [tmp_path / "original", tmp_path / "continuation"]
    calls = {"local": 0, "cloud": 0}
    for i, directory in enumerate(directories):
        directory.mkdir(); module.write_new(directory / "protocol_copy.json", protocol)
        module.write_new(directory / "schedule.json", schedule)
        rows, events, baseline = [], [], calls.copy()
        for sample in samples[i * 2:i * 2 + 2]:
            for method in module.METHODS:
                provider = "cloud" if method in ("cloud", "tool_cloud") else "local"
                cost = .001 if provider == "cloud" else 0.
                trace = {"provider": provider, "usage": {}, "cost_usd": cost, "error": None}
                result = {"status": "MEASURED", "route": "CLOUD_MODEL" if provider == "cloud" else "LOCAL_MODEL",
                          "output": {"action": "ANSWER", "answer": "OK"}, "latency_ms": 10.,
                          "local_calls": int(provider == "local"), "cloud_calls": int(provider == "cloud"),
                          "tool_calls": 0, "trace": [trace]}
                rows.append({"sample": sample, "method": method, "result": result, "score": score(sample, result["output"])})
                calls[provider] += 1
                event = {"provider": provider, "sample_id": sample["id"], "method": method,
                         "attempt_number_provider": calls[provider], "utc": f"2026-10-02T04:{40+i}:01+00:00"}
                events.extend([{**event, "event": "call_started"}, {**event, "event": "call_finished", "error": None, "cost_usd": cost}])
        jsonl(directory / "raw_decisions.jsonl", rows); jsonl(directory / "attempts.jsonl", events)
        resources = [{"utc": f"2026-10-02T04:{40+i}:00+00:00", "vram_mib_total": 10. + i, "ram_gib_system_used": 2. + i}]
        module.write_new(directory / "resources.json", resources)
        manifest = {"state": "running" if i == 0 else "completed", "target_n": 4,
                    "holdout_ids": protocol["holdout_ids"], "protocol_sha256": module.sha(directory / "protocol_copy.json"),
                    "dataset_sha256": module.sha(dataset), "local_calls_actual": calls["local"], "cloud_calls_actual": calls["cloud"],
                    "local_load_metadata": {"cold_load_wall_s": 1. + i, "unload_success": True},
                    "started_utc": resources[0]["utc"], "finished_utc": f"2026-10-02T04:{40+i}:30+00:00"}
        if i:
            manifest.update(call_counter_scope="cumulative_original_plus_continuation", original_call_baseline=baseline,
                            resource_summary={"resource_poll_errors": []})
        module.write_new(directory / "manifest.json", manifest)
    return module, directories[0], directories[1], tmp_path / "analysis_input_reconciled"


def test_original_running_snapshot_audit_goes_outside_original_and_ignores_tmp_counter(segments):
    module, original, _, _ = segments
    stale = module.read(original / "manifest.json"); stale["local_calls_actual"] += 1
    module.write_new(original / "manifest.tmp", stale)
    before = {p.name: p.read_bytes() for p in original.iterdir()}
    output = module.write_audit(original)
    audited = module.read(output)
    assert output.parent == original.parent and audited["finished_calls"] == {"local": 6, "cloud": 4}
    assert audited["complete_sample_cases"] == 2 and audited["all_started_attempts_finished"]
    assert {p.name: p.read_bytes() for p in original.iterdir()} == before
    with pytest.raises(ValueError, match="outside immutable"):
        module.write_audit(original, original / "audit.json")


def test_combined_unique_union_preserves_source_bytes_and_cumulative_calls_once(segments):
    module, original, continuation, output = segments
    before = [{p.name: p.read_bytes() for p in directory.iterdir()} for directory in (original, continuation)]
    module.reconcile(original, continuation, output)
    manifest = module.read(output / "manifest.json")
    assert manifest["local_calls_actual"] == 12 and manifest["cloud_calls_actual"] == 8
    assert manifest["reconciliation"]["union_rows"] == 20 and manifest["reconciliation"]["scores_recomputed_and_matched"]
    assert manifest["resource_summary"]["vram_mib_peak_sampled_total"] == 11.
    assert manifest["resource_summary"]["resource_poll_errors"] is None
    assert manifest["interruption_gap_sampled_s"] == 60.
    assert (output / "protocol_copy.json").read_bytes() == (original / "protocol_copy.json").read_bytes()
    for directory, expected in zip((original, continuation), before):
        assert {p.name: p.read_bytes() for p in directory.iterdir()} == expected
    with pytest.raises(FileExistsError):
        module.reconcile(original, continuation, output)


def test_pending_http_attempt_prevents_safe_audit(segments):
    module, original, _, _ = segments
    events = module.jsonl(original / "attempts.jsonl"); events.pop()
    jsonl(original / "attempts.jsonl", events)
    with pytest.raises(ValueError, match="Unfinished"):
        module.inspect_segment(original)


def test_trace_cost_mismatch_and_score_tampering_rejected(segments):
    module, original, _, _ = segments
    events = module.jsonl(original / "attempts.jsonl"); events[-1]["cost_usd"] = .1
    jsonl(original / "attempts.jsonl", events)
    with pytest.raises(ValueError, match="errors/costs"):
        module.inspect_segment(original)
    events[-1]["cost_usd"] = 0.; jsonl(original / "attempts.jsonl", events)
    rows = module.jsonl(original / "raw_decisions.jsonl"); rows[-1]["score"]["correct"] = False
    jsonl(original / "raw_decisions.jsonl", rows)
    with pytest.raises(ValueError, match="score differs"):
        module.inspect_segment(original)


def test_phantom_counter_or_reordered_case_is_rejected(segments):
    module, original, _, _ = segments
    manifest = module.read(original / "manifest.json"); manifest["local_calls_actual"] += 1
    (original / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="counter differs"):
        module.inspect_segment(original)
    manifest["local_calls_actual"] -= 1; (original / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = module.jsonl(original / "raw_decisions.jsonl"); rows[0], rows[1] = rows[1], rows[0]
    jsonl(original / "raw_decisions.jsonl", rows)
    with pytest.raises(ValueError, match="interleaved order"):
        module.inspect_segment(original)


def test_terminal_state_and_exact_baseline_required_before_union(segments):
    module, original, continuation, output = segments
    manifest = module.read(continuation / "manifest.json"); manifest["state"] = "running"
    (continuation / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="terminal"):
        module.reconcile(original, continuation, output)
    assert not output.exists()


def test_protocol_hash_or_frozen_dataset_tampering_rejected(segments):
    module, original, _, _ = segments
    dataset = module.ROOT / "data/synthetic.jsonl"
    dataset.write_bytes(dataset.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="dataset hash"):
        module.inspect_segment(original)


def test_only_exact_crlf_lf_equivalence_is_accepted_and_reported(segments):
    module, original, continuation, output = segments
    original_copy = (original / "protocol_copy.json").read_bytes()
    frozen_lf = original_copy.replace(b"\r\n", b"\n")
    expected = __import__("hashlib").sha256(frozen_lf).hexdigest()
    for directory in (original, continuation):
        manifest = module.read(directory / "manifest.json"); manifest["protocol_sha256"] = expected
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (original / "protocol_copy.json").write_bytes(frozen_lf.replace(b"\n", b"\r\n"))
    module.reconcile(original, continuation, output)
    assert (output / "protocol_copy.json").read_bytes() == frozen_lf
    assert module.read(output / "manifest.json")["segment_metadata"][0]["protocol_serialization"]["exact_raw_copy"] is False
    (original / "protocol_copy.json").write_bytes((original / "protocol_copy.json").read_bytes() + b" ")
    with pytest.raises(ValueError, match="beyond CRLF/LF"):
        module.inspect_segment(original)

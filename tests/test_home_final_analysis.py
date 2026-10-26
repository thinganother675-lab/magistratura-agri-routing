"""Statistical journal invariants on synthetic fixtures; no provider/data calls."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from agro_route.evaluation import score


def analyzer():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("home_final_analysis_test", root / "scripts/analyze_home_final.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture():
    samples = [{"id": str(i), "group": f"source-{i // 2}", "category": "rule_interpretation",
                "language": "en", "input": "Use the supplied rule", "scoring": "exact",
                "expected": {"action": "ANSWER", "answers": ["OK"]}} for i in range(4)]
    rows = []
    for sample in samples:
        for method in ("local", "cloud", "tool_cloud", "hybrid", "offline"):
            cloud = method in ("cloud", "tool_cloud")
            result = {"status": "MEASURED", "route": "CLOUD_MODEL" if cloud else "LOCAL_MODEL",
                      "output": {"action": "ANSWER", "answer": "OK"}, "latency_ms": 10.,
                      "cloud_calls": int(cloud), "local_calls": int(not cloud), "tool_calls": 0,
                      "cost_usd": .001 if cloud else 0., "trace": [
                          {"provider": "cloud" if cloud else "local", "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                           "cost_usd": .001 if cloud else 0., "error": None, "latency_ms": 9.}]}
            rows.append({"sample": sample, "method": method, "result": result, "score": score(sample, result["output"])})
    manifest = {"target_n": 4, "holdout_ids": [s["id"] for s in samples],
                "state": "completed", "cloud_calls_actual": 8}
    protocol = {"status": "FROZEN", "statistic": {"bootstrap_seed": 20261001, "repeats": 5000, "unit": "sample.group"},
                "criteria": {"quality_margin": .05, "cloud_call_reduction_pp": .10,
                             "critical_error_increase_max": 0, "p95_max_s": 10}}
    return rows, samples, manifest, protocol


def test_paired_alignment_ignores_journal_order_and_uses_same_ids():
    rows, samples, manifest, protocol = fixture()
    for row in rows:
        if row["method"] == "hybrid" and row["sample"]["id"] == "0":
            row["result"]["output"]["answer"] = "WRONG"
            row["score"] = score(row["sample"], row["result"]["output"])
        if row["method"] == "tool_cloud" and row["sample"]["id"] == "1":
            row["result"]["output"]["answer"] = "WRONG"
            row["score"] = score(row["sample"], row["result"]["output"])
    report, _, _ = analyzer().compute_statistics(rows[::-1], samples, manifest, protocol)
    pair = report["paired"]["hybrid_minus_tool_cloud"]
    assert pair["quality_a_minus_b"]["estimate"] == 0
    assert pair["quality_a_minus_b"]["ci95"] == [0., 0.]
    assert pair["mcnemar_descriptive"]["wins"] == pair["mcnemar_descriptive"]["losses"] == 1
    assert pair["cloud_call_reduction_all_target"] == 1.


def test_not_run_and_missing_excluded_from_accuracy_but_preserve_coverage():
    rows, samples, manifest, protocol = fixture()
    target = next(row for row in rows if row["method"] == "hybrid")
    target["result"] = {"status": "NOT_RUN", "blocked_reason": "fixture_only"}
    target["score"] = None
    rows = [row for row in rows if not (row["method"] == "local" and row["sample"]["id"] == "0")]
    report, normalized, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    hybrid = report["summary"]["hybrid"]
    assert hybrid["measured_n"] == 3 and hybrid["quality"] == 1. and hybrid["measurement_coverage"] == .75
    assert hybrid["recorded_not_run_n"] == 1 and report["summary"]["local"]["missing_n"] == 1
    assert any(row["status"] == "MISSING" and row["correct"] is None for row in normalized)
    assert report["status"] == "PARTIAL_NOT_CONFIRMATORY"
    assert all(check["status"] == "UNCERTAIN" for check in report["hypothesis"]["criteria"].values())


def test_duplicate_and_score_tampering_rejected():
    rows, samples, _, _ = fixture()
    with pytest.raises(ValueError, match="duplicate"):
        analyzer().validate_records(rows + [rows[0]], samples)
    rows[0]["score"]["correct"] = False
    with pytest.raises(ValueError, match="score differs"):
        analyzer().validate_records(rows, samples)


def test_counter_mismatch_and_sample_tampering_rejected():
    rows, samples, _, _ = fixture()
    rows[0]["result"]["local_calls"] = 0
    with pytest.raises(ValueError, match="counters differ"):
        analyzer().validate_records(rows, samples)
    rows, samples, _, _ = fixture()
    rows[0] = copy.deepcopy(rows[0])
    rows[0]["sample"]["expected"]["answers"] = ["OTHER_GOLD"]
    with pytest.raises(ValueError, match="frozen dataset"):
        analyzer().validate_records(rows, samples)


def test_unknown_cloud_usage_cost_not_zero_or_complete_cost_per1000():
    rows, samples, manifest, protocol = fixture()
    cloud = next(row for row in rows if row["method"] == "cloud")
    cloud["result"]["cost_usd"] = None
    cloud["result"]["trace"][0]["usage"] = {}
    cloud["result"]["trace"][0]["cost_usd"] = None
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    summary = report["summary"]["cloud"]
    assert summary["providers"]["cloud"]["input_usage_coverage_n"] == 3
    assert summary["providers"]["cloud"]["unknown_cost_calls"] == 1
    assert summary["cloud_cost_per_1000_measured_usd"] is None
    assert summary["cloud_cost_per_1000_known_lower_bound_usd"] == pytest.approx(.75)
    assert report["summary"]["offline"]["correct_abstention_rate"] is None


def test_not_run_with_partial_trace_keeps_incurred_usage_and_actual_call_counts():
    rows, samples, manifest, protocol = fixture()
    blocked = next(row for row in rows if row["method"] == "hybrid")
    blocked["result"].update(status="NOT_RUN", output=None, blocked_reason={"provider": "cloud"})
    blocked["score"] = None
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    hybrid = report["summary"]["hybrid"]
    assert hybrid["measured_n"] == 3 and hybrid["providers"]["local"]["calls"] == 4
    assert hybrid["providers"]["local"]["input_tokens_known_sum"] == 400
    assert hybrid["cloud_cost_per_1000_measured_usd"] is None


def test_native_client_timing_fields_and_replay_latency_rejection():
    rows, samples, manifest, protocol = fixture()
    rows[0]["result"]["trace"][0]["timing"] = {
        "first_nonempty_delta_s_client": .2, "first_answer_delta_s_client": .3,
        "completion_tokens_per_second_client_approx": 10.}
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    local = report["summary"]["local"]["providers"]["local"]
    assert local["client_ttft_median_s"] == .2 and local["approx_tps_median"] == 10.
    rows[0]["result"]["latency_kind"] = "reconstructed_cli_trace"
    with pytest.raises(ValueError, match="replay or CLI"):
        analyzer().validate_records(rows, samples)


def test_unjournaled_started_attempt_disables_confirmatory_criteria():
    rows, samples, manifest, protocol = fixture()
    manifest["cloud_calls_actual"] += 1
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    assert report["unjournaled_cloud_attempts_unknown_usage_cost"] == 1
    assert report["hypothesis"]["supported_on_frozen_controlled_sample"] is None


def test_complete_four_criteria_reported_separately_and_latency_can_fail():
    rows, samples, manifest, protocol = fixture()
    for row in rows:
        if row["method"] == "hybrid":
            row["result"]["latency_ms"] = 11000.
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    checks = report["hypothesis"]["criteria"]
    assert checks["quality_noninferiority"]["status"] == "PASS"
    assert checks["additional_cloud_call_reduction"]["status"] == "PASS"
    assert checks["critical_error_difference"]["status"] == "PASS"
    assert checks["hybrid_p95_latency"]["status"] == "FAIL"
    assert not report["hypothesis"]["supported_on_frozen_controlled_sample"]


def test_zero_measured_primary_is_unknown_and_eligibility_never_uses_gold():
    rows, samples, manifest, protocol = fixture()
    rows = [row for row in rows if row["method"] not in ("hybrid", "tool_cloud")]
    manifest["cloud_calls_actual"] = 4
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    assert report["paired"]["hybrid_minus_tool_cloud"]["status"] == "NOT_RUN"
    assert all(check["status"] == "UNCERTAIN" for check in report["hypothesis"]["criteria"].values())
    other = copy.deepcopy(samples[0]); other["expected"]["action"] = "ABSTAIN"
    assert analyzer().eligibility(samples[0]) == analyzer().eligibility(other)


@pytest.mark.parametrize("field,value", [("policies", ["local", "cloud", "tool_cloud", "hybrid", "offline", "hybrid"]),
                                       ("holdout_ids", ["0", "1", "2", "3", "3"]),
                                       ("holdout_ids", ["3", "2", "1", "0"])])
def test_manifest_duplicate_or_reordered_controls_rejected(field, value):
    rows, samples, manifest, protocol = fixture()
    manifest[field] = value
    with pytest.raises(ValueError, match="frozen IDs"):
        analyzer().compute_statistics(rows, samples, manifest, protocol)


def test_complete_rows_with_unknown_latency_leave_overall_support_unknown():
    rows, samples, manifest, protocol = fixture()
    next(row for row in rows if row["method"] == "hybrid")["result"]["latency_ms"] = None
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    assert report["status"] == "COMPLETE_FROZEN_CONTROLLED_RUN"
    assert report["hypothesis"]["criteria"]["hybrid_p95_latency"]["status"] == "UNCERTAIN"
    assert report["hypothesis"]["supported_on_frozen_controlled_sample"] is None
    assert report["hypothesis"]["status"].startswith("UNCERTAIN")


def test_final_criteria_cannot_be_changed_at_analysis_time():
    rows, samples, manifest, protocol = fixture()
    protocol["criteria"]["quality_margin"] = .50
    with pytest.raises(ValueError, match="Frozen criteria"):
        analyzer().compute_statistics(rows, samples, manifest, protocol)


def test_reasoning_usage_is_reported_without_double_count_and_fallback_error_visible():
    rows, samples, manifest, protocol = fixture()
    hybrid = next(row for row in rows if row["method"] == "hybrid")
    hybrid["result"]["trace"][0].update(error={"type": "TimeoutException"}, usage={
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
        "completion_tokens_details": {"reasoning_tokens": 5}})
    report, _, _ = analyzer().compute_statistics(rows, samples, manifest, protocol)
    local = report["summary"]["hybrid"]["providers"]["local"]
    assert local["output_tokens_known_sum"] == 80
    assert local["reasoning_tokens_reported_known_sum"] == 5 and local["reasoning_usage_coverage_n"] == 1
    assert local["total_tokens_reported_known_sum"] == 120 and local["total_usage_coverage_n"] == 1
    assert report["summary"]["hybrid"]["call_errors"] == 1
    assert report["summary"]["hybrid"]["error_decisions"] == 0
    category = next(row for row in report["category"] if row["method"] == "hybrid")
    assert category["call_errors"] == 1 and category["route_counts"] == {"LOCAL_MODEL": 4}


def test_not_run_cannot_claim_untraced_provider_calls():
    rows, samples, _, _ = fixture()
    rows[0]["result"] = {"status": "NOT_RUN", "cloud_calls": 1, "local_calls": 0}
    rows[0]["score"] = None
    with pytest.raises(ValueError, match="counters differ"):
        analyzer().validate_records(rows, samples)


def test_export_uses_new_directory_and_keeps_unknown_costs_explicit(tmp_path, monkeypatch):
    module = analyzer()
    rows, samples, manifest, protocol = fixture()
    dataset = tmp_path / "synthetic.jsonl"
    dataset.write_text("\n".join(json.dumps(s) for s in samples) + "\n", encoding="utf-8")
    protocol.update(dataset_path=str(dataset), dataset_sha256=module.sha(dataset), n=len(samples),
                    holdout_ids=manifest["holdout_ids"])
    directory = tmp_path / "mock_final"
    directory.mkdir()
    protocol_path = directory / "protocol_copy.json"
    module.write_json_new(protocol_path, protocol)
    manifest.update(dataset_sha256=module.sha(dataset), protocol_sha256=module.sha(protocol_path))
    module.write_json_new(directory / "manifest.json", manifest)
    (directory / "raw_decisions.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(module, "plots", lambda *args: None)
    first = module.analyze(directory)
    second = module.analyze(directory)
    assert first != second
    expected = {"statistics.json", "summary.csv", "normalized.csv", "category.csv", "language.csv",
                "manual30.csv", "paired.csv", "hypothesis.csv"}
    assert {path.name for path in first.iterdir()} == expected
    assert "UNKNOWN" in (first / "summary.csv").read_text(encoding="utf-8-sig")
    exported = json.loads((first / "statistics.json").read_text(encoding="utf-8"))
    assert exported["provenance"]["raw_sha256"] == module.sha(directory / "raw_decisions.jsonl")

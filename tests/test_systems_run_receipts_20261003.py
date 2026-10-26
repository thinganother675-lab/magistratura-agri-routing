# SPDX-License-Identifier: Apache-2.0
"""Frozen V1 evidence integrity. No live model calls or source-text assertions.

Executed-source snapshots remain authoritative after the implementation moves
to V2. The original failed run cannot be silently replaced by later results.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/20261003_systems_study_c_v1"
AUDIT = ROOT / "results/20261003_resource_session/independent_systems_v1_correction.json"
ARCHIVE = ROOT / "experiments/system_telemetry_v1_code/manifest.json"
KEYS = ("qwen3.5-9b", "qwen3.8-27b")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def journal(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_v1_executed_code_matches_immutable_snapshots_after_working_code_advances():
    plan, archive, correction = read(RUN / "protocol_frozen.json"), read(ARCHIVE), read(AUDIT)
    assert correction["source_archive_manifest_sha256"] == digest(ARCHIVE)
    assert archive["protocol_sha256"] == digest(RUN / "protocol_frozen.json")
    for original, expected in plan["source_code_sha256"].items():
        entry = archive["files"][original]
        assert entry["plan_recorded"] and entry["sha256"] == expected
        assert digest(ROOT / entry["snapshot_path"]) == expected
    for entry in archive["files"].values():
        assert digest(ROOT / entry["snapshot_path"]) == entry["sha256"]


def test_v1_completion_does_not_claim_all_inference_success():
    completion, qa = read(RUN / "completion_receipt.json"), read(AUDIT)
    assert completion["state"] == "COMPLETE"  # attempt coverage only
    assert qa["all_integrity_checks_pass"] and all(qa["checks"].values())
    assert qa["models"][KEYS[0]]["telemetry_stream_success"] == 40
    assert qa["models"][KEYS[1]]["telemetry_stream_success"] == 21
    assert qa["models"][KEYS[1]]["telemetry_transport_or_guard_error"] == 19
    assert qa["models"][KEYS[1]]["study_c_stream_success"] == 0
    assert qa["models"][KEYS[1]]["numeric_quality_status"] == "RESOURCE_CONFOUNDED_NOT_MODEL_QUALITY"


def test_v1_journal_has_full_attempt_coverage_and_no_duplicates():
    metrics, plan = journal(RUN / "inference_metrics.jsonl"), read(RUN / "protocol_frozen.json")
    assert len(metrics) == 2 * (40 + 27 + 2)
    identities = [(r["model_key"], r["block"], r["kind"], r["task_id"]) for r in metrics]
    assert len(identities) == len(set(identities))
    for key in KEYS:
        rows = [r for r in metrics if r["model_key"] == key]
        assert Counter(r["kind"] for r in rows) == {"telemetry":40,"study_c":27,"warmup":2}
        assert {r["task_id"] for r in rows if r["kind"] == "telemetry"} == set(plan["telemetry_item_ids"])


def test_v1_components_never_promote_guard_failure_to_tool_selection_success():
    correction = read(AUDIT)["corrected_component_scores"]
    assert correction[KEYS[0]]["declared_real_tool_n"] == 26
    assert correction[KEYS[0]]["declared_real_tool_correct"] == 17
    assert correction[KEYS[1]]["declared_real_tool_correct"] == 0
    # Frozen original scorer credited None == None on unsupported empty output.
    original = journal(RUN / "study_c_scores.jsonl")
    q27 = [r for r in original if r["model_key"] == KEYS[1]]
    assert sum(r["tool_correct"] for r in q27) == 1
    assert all(r["error"] for r in q27)
    assert correction[KEYS[1]]["declared_real_tool_correct"] == sum(r["tool_correct"] and r["parse_success"] and not r["error"] for r in q27)


def test_v1_unit_correction_and_typed_task_disclosure_preserve_original_scores():
    correction, original = read(AUDIT), read(RUN / "study_c_summary.json")
    for key in KEYS:
        assert original["models"][key]["invalid_units_n"] == 0
        assert correction["corrected_component_scores"][key]["invalid_units_n"] == 3
    assert any("typed task supplied" in line for line in original["limitations"])
    assert any("not actual tool invocation" in line for line in original["limitations"])
    assert original["models"]["deterministic_tools"]["correct"] == 27


def test_v1_conditional_latency_has_shared_denominator_and_no_sparse_p99():
    qa = read(AUDIT)
    paired = qa["paired_success_latency"]
    assert paired["n_common_success"] == 21
    assert "CONDITIONAL_SUCCESS_BIASED_SUBSET" in paired["status"]
    for distribution in paired["models"].values():
        assert distribution["n_observed"] == 21 and distribution["p99"] is None
    assert paired["p50_ratio_q27_over_q9"] == pytest.approx(
        paired["models"][KEYS[1]]["p50"] / paired["models"][KEYS[0]]["p50"])
    assert paired["models"][KEYS[1]]["p50"] > read(RUN / "systems_summary.json")["models"][KEYS[1]]["latency_s"]["p50"]


def test_v1_resource_scope_unknown_layers_energy_and_finish_are_preserved():
    rows = journal(RUN / "inference_metrics.jsonl")
    for row in rows:
        assert "NOT per-model allocation" in row["resources"]["scope"]
        assert row["resources"]["energy_j"] is None
        assert row["finish_reason"] is None
        assert row["finish_reason_source"] == "UNKNOWN_NATIVE_API_DOES_NOT_EXPOSE_STOP_REASON"
    assert all(load["actual_gpu_layers"] is None for load in read(RUN / "load_receipts.json"))


def test_v1_safe_rows_exclude_prompts_responses_headers_and_secret_fields():
    forbidden = {"prompt","request","response_text","events","gold","expected","headers","authorization","api_key","secret"}
    def safe(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(str(k).lower() for k in value)
            for child in value.values(): safe(child)
        elif isinstance(value, list):
            for child in value: safe(child)
    safe(journal(RUN / "inference_metrics.jsonl"))
    qa = read(AUDIT)
    assert qa["checks"]["study_gold_not_in_public_payload"]
    assert qa["checks"]["tools_disabled_in_all_requests"]
    assert qa["checks"]["no_tools_in_response_events"]


def test_v1_append_only_correction_links_original_audit_and_sources():
    qa = read(AUDIT)
    assert qa["original_qa_sha256"] == digest(ROOT / qa["original_qa_path"])
    assert qa["protocol_sha256"] == digest(RUN / "protocol_frozen.json")
    assert qa["original_files_modified"] is False and qa["new_inference_calls"] == 0
    for relative, expected in qa["source_hashes"].items():
        path = ROOT / relative
        if relative == "scripts/verify_systems_receipts_20261003.py":
            entry = read(ARCHIVE)["files"][relative]
            path = ROOT / entry["snapshot_path"]
        if path.exists():
            assert digest(path) == expected
        else:
            assert relative.startswith(".runtime/")

# SPDX-License-Identifier: Apache-2.0
"""Meaningful score-gating and immutable V2 receipt/table verification."""
from collections import Counter
import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest
from agro_route.study_c_aggregate_20261003 import aggregate

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"results/20261003_systems_checkpoint0_v2"
QA=ROOT/"results/20261003_resource_session/independent_systems_v2_qa.json"
OUT=ROOT/"results/20261003_resource_analysis"
KEYS=("qwen3.5-9b","qwen3.8-27b")


def read(path):return json.loads(path.read_text("utf-8"))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def journal(path):return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x]


def measured(item="synthetic_1",**values):
    return {"model_key":"synthetic_model","source_run":"synthetic_v1","latency_s":1.,"error":None,
            "id":item,"group":"synthetic","category":"numeric","expected_action":"ANSWER",
            "parse_success":True,"correct":True,"action_correct":True,"tool_correct":True,
            "numeric_correct":True,"numeric_case":True,"numeric_rounding_1e4_correct":True,
            "output_unit_correct":True,"declared_selection_tool_replay_correct":True,
            "declared_selection_tool_replay_status":"SIMULATED",**values}


def metadata(item="synthetic_1",**values):
    return {"id":item,"expected_action":"ANSWER","tool_eligible":True,"unit_conversion_case":False,**values}


def test_failed_null_tool_agreement_never_earns_component_credit():
    row=measured(expected_action="ABSTAIN",numeric_case=False,error="ResourceGuard",parse_success=False,
                 correct=False,tool_correct=True,action_correct=True,numeric_correct=False)
    result=aggregate([row],[metadata(expected_action="ABSTAIN",tool_eligible=False)])["models"]["synthetic_model"]
    assert result["declared_real_tool_n"]==0 and result["declared_real_tool_correct"]==0
    assert result["unsupported_task_n"]==1 and result["unsupported_task_correct"]==0
    assert result["action_correct"]==0


def test_unparsed_output_cannot_receive_arithmetic_or_simulated_replay_credit():
    row=measured(parse_success=False,correct=False,numeric_correct=True,tool_correct=True)
    result=aggregate([row],[metadata()])["models"]["synthetic_model"]
    assert result["numeric_n"]==1 and result["numeric_correct"]==0
    assert result["declared_real_tool_correct"]==0 and result["declared_tool_executor_replay"]["correct"]==0
    assert result["declared_tool_executor_replay"]["live_model_tool_calls"]==0


def test_secondary_rounding_does_not_replace_primary_numerical_score():
    row=measured(correct=False,numeric_correct=False,numeric_rounding_1e4_correct=True)
    result=aggregate([row],[metadata()])["models"]["synthetic_model"]
    assert result["correct"]==0 and result["numeric_correct"]==0
    assert result["numeric_rounding_1e4_correct"]==1


@pytest.mark.parametrize("bad",["expected","gold","numeric_reference","prompt","request","api_key"])
def test_aggregate_rejects_source_content_and_secrets(bad):
    with pytest.raises(ValueError,match="whitelisted"):
        aggregate([measured(**{bad:"synthetic forbidden"})],[metadata()])
    with pytest.raises(ValueError,match="whitelisted"):
        aggregate([measured()],[metadata(**{bad:"synthetic forbidden"})])


def test_common_case_coverage_action_and_numerical_eligibility_fail_closed():
    with pytest.raises(ValueError,match="unique common"):
        aggregate([measured(),measured()],[metadata()])
    with pytest.raises(ValueError,match="unique common"):
        aggregate([measured()],[metadata(),metadata("synthetic_2")])
    with pytest.raises(ValueError,match="action metadata"):
        aggregate([measured()],[metadata(expected_action="ABSTAIN")])
    with pytest.raises(ValueError,match="Numerical eligibility"):
        aggregate([measured(numeric_case=False)],[metadata()])
    with pytest.raises(ValueError,match="complete credit"):
        aggregate([measured(error="ResourceGuard")],[metadata()])


def test_units_use_explicit_eligibility_and_reused_source_runs_remain_visible():
    row=measured(expected_action="ASK_FOR_DATA",numeric_case=False,numeric_correct=False)
    result=aggregate([row],[metadata(expected_action="ASK_FOR_DATA",unit_conversion_case=True)])
    model=result["models"]["synthetic_model"]
    assert model["unit_conversion_n"]==1 and model["unit_conversion_correct"]==1
    assert model["source_run_counts"]=={"synthetic_v1":1}
    assert result["status"]=="DEV" and result["private_test_run"] is False


def test_v2_qa_and_executed_source_archive_are_immutable_and_all_checks_pass():
    qa=read(QA);archive=read(ROOT/qa["source_archive_manifest_path"]);plan=read(RUN/"protocol_frozen.json")
    assert qa["all_integrity_checks_pass"] and len(qa["checks"])==27 and all(qa["checks"].values())
    assert digest(ROOT/qa["source_archive_manifest_path"])==qa["source_archive_manifest_sha256"]
    assert archive["protocol_sha256"]==digest(RUN/"protocol_frozen.json")
    for name,expected in plan["source_code_sha256"].items():
        snapshot=archive["files"][name]
        assert snapshot["sha256"]==expected and digest(ROOT/snapshot["snapshot_path"])==expected


def test_v2_exact_reuse_and_new_inference_counts_do_not_duplicate_q9_study():
    scores=journal(RUN/"study_c_scores.jsonl");metrics=journal(RUN/"inference_metrics.jsonl")
    assert len(metrics)==111
    assert Counter((r["model_key"],r["kind"]) for r in metrics)=={
        (KEYS[0],"telemetry"):40,(KEYS[1],"telemetry"):40,(KEYS[1],"study_c"):27,
        (KEYS[0],"warmup"):2,(KEYS[1],"warmup"):2}
    prior={(r["model_key"],r["id"]):r for r in journal(ROOT/"results/20261003_systems_study_c_v1/study_c_scores.jsonl")}
    for r in scores:
        if r["model_key"] in {KEYS[0],"deterministic_tools"}:
            assert r["source_run"]=="20261003_systems_study_c_v1"
            assert {k:v for k,v in r.items() if k!="source_run"}==prior[(r["model_key"],r["id"])]
        else:assert r["source_run"]=="20261003_systems_checkpoint0_v2"


def test_v2_corrected_study_components_have_valid_denominators_and_simulation_role():
    corrected=read(RUN/"study_c_corrected_aggregate.json")
    expected={KEYS[0]:(7,17,1,5,0),KEYS[1]:(15,25,6,8,1),"deterministic_tools":(27,26,16,10,3)}
    for model,m in corrected["models"].items():
        assert [m[x] for x in ["correct","declared_real_tool_correct","numeric_correct","missing_input_or_invalid_input_correct","unit_conversion_correct"]]==list(expected[model])
        assert [m[x] for x in ["n","declared_real_tool_n","numeric_n","missing_input_or_invalid_input_n","unit_conversion_n"]]==[27,26,16,10,3]
        assert m["declared_tool_executor_replay"]["status"]=="SIMULATED" and m["declared_tool_executor_replay"]["live_model_tool_calls"]==0
        assert m["latency_s"]["p99"] is None
    assert corrected["original_summary_sha256"]==digest(RUN/"study_c_summary.json")


def test_v2_systems_maxima_are_actual_samples_and_load_pairs_are_reported_exactly():
    corrected=read(RUN/"systems_corrected_aggregate.json");metrics=journal(RUN/"inference_metrics.jsonl");loads=read(RUN/"load_receipts.json")
    for model,m in corrected["models"].items():
        own=[r for r in metrics if r["model_key"]==model and r["kind"]=="telemetry"]
        assert m["n"]==40 and m["errors"]==0 and m["latency_s"]["p99"] is None
        for field in ["gpu_memory_used_mib","system_ram_used_gib","lmstudio_process_group_rss_mib"]:
            assert m["resources"][field+"_request_peaks"]["max"]==max(r["resources"][field+"_peak_sampled"] for r in own)
        mine=[r for r in loads if r["model_key"]==model]
        assert len(m["load_samples_s"])==2 and m["load_samples_s"]==[r["load_latency_s"] for r in mine]
        assert m["warmup_samples_s"]==[r["warmup_latency_s"] for r in mine]
        assert m["requested_gpu_offload"] is None and m["actual_gpu_layers"] is None and m["context_checkpoints"]==0
    assert corrected["quality_remeasured"] is False


def test_final_table_adds_explicit_status_without_changing_any_existing_number():
    revision=read(OUT/"final_model_table_status_revision.json")
    assert digest(ROOT/revision["original_table_path"])==revision["original_table_sha256"]
    assert digest(ROOT/revision["revised_table_path"])==revision["revised_table_sha256"]
    def csv_rows(path):
        with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
    old=csv_rows(ROOT/revision["original_table_path"]);new=csv_rows(ROOT/revision["revised_table_path"])
    assert [{k:v for k,v in row.items() if k not in revision["added_columns"]} for row in new]==old
    for row in new:
        assert row["quality_status"]=="DEV" and len(row["exact_gguf_sha256"])==64
        if row["model_key"] in KEYS:
            assert row["resource_status"]=="SYSTEMS_TELEMETRY" and "unrelated llama-server" in row["resource_scope"]
        else:
            assert row["resource_status"]=="HISTORICAL" and row["systems_status"]=="HISTORICAL_REFERENCE"


def test_v2_qa_hashes_resolve_append_only_table_revision():
    qa=read(QA);revision=read(OUT/"final_model_table_status_revision.json")
    assert digest(QA)==revision["prior_qa_sha256"]
    for relative,expected in qa["source_hashes"].items():
        path=ROOT/relative
        if relative==revision["revised_table_path"]:path=ROOT/revision["original_table_path"]
        if path.exists():assert digest(path)==expected
        else:assert relative.startswith(".runtime/")

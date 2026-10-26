"""Synthetic-only tests for the disclosed nonfrozen reporting label correction."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "scripts/correct_home_final_reporting.py"
    spec = importlib.util.spec_from_file_location("home_final_reporting_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    return {"status": "COMPLETE_FROZEN_CONTROLLED_RUN", "hypothesis": {"supported": True},
            "paired": {"quality_a_minus_b": {"estimate": .1, "ci95": [0, .2]}},
            "summary": {method: {"measured_n": 4, "ask_coverage": 0., "quality": .75,
                                 "critical_errors": 0,
                                 "action_counts": {"ANSWER": 2, "ASK_FOR_DATA": 1, "ABSTAIN": 1}}
                        for method in ("local", "cloud", "tool_cloud", "hybrid", "offline")}}


def test_only_exact_ask_fields_change_and_input_report_remains_immutable():
    report = fixture(); original = copy.deepcopy(report)
    corrected, changes = helper().correct_ask_reporting(report)
    assert report == original and len(changes) == 5
    assert all(change["path"].endswith(".ask_coverage") for change in changes)
    assert all(row["ask_coverage"] == .25 for row in corrected["summary"].values())
    for method in report["summary"]:
        corrected["summary"][method]["ask_coverage"] = report["summary"][method]["ask_coverage"]
    assert corrected == report


def test_no_measured_decisions_remain_unknown():
    report = fixture()
    report["summary"]["offline"].update(measured_n=0, action_counts={}, ask_coverage=None)
    corrected, changes = helper().correct_ask_reporting(report)
    assert corrected["summary"]["offline"]["ask_coverage"] is None
    assert all(change["path"] != "summary.offline.ask_coverage" for change in changes)


@pytest.mark.parametrize("counts", [{"ASK_FOR_DATA": True}, {"ASK_FOR_DATA": -1}, {"ANSWER": 3}, {"ANSWER": 5}])
def test_invalid_or_incomplete_action_counts_are_rejected(counts):
    report = fixture(); report["summary"]["local"]["action_counts"] = counts
    with pytest.raises(ValueError, match="Action counts"):
        helper().correct_ask_reporting(report)


def test_new_corrected_file_contains_parent_hash_diff_and_does_not_overwrite(tmp_path):
    module = helper(); source = tmp_path / "statistics.json"
    source.write_text(json.dumps(fixture()), encoding="utf-8")
    original = source.read_bytes()
    output = module.save_correction(source)
    corrected = json.loads(output.read_text(encoding="utf-8"))
    assert source.read_bytes() == original
    metadata = corrected["reporting_correction"]
    assert metadata["source_sha256"] == module.sha(source) and len(metadata["changed_fields"]) == 5
    with pytest.raises(FileExistsError):
        module.save_correction(source)

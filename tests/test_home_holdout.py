import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("build_home_holdout", Path(__file__).resolve().parents[1]/"scripts/build_home_holdout.py")
holdout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(holdout)


def test_new_set_balance_grouping_and_frozen_tools_compatibility():
    rows = holdout.build_rows()
    report = holdout.validate_rows(rows, historical_paths=[])
    assert report["cases"] == 150
    assert report["by_language"] == {"en":75,"ru":75}
    assert report["source_document_groups"] == 5
    assert report["groups_total"] == 25
    assert report["public_request_hard_gate_counts"] == {"NO_HARD_GATE":100,"DETERMINISTIC_TOOL":30,"ASK_FOR_DATA":20}
    assert report["independent_decimal_vs_frozen_tool_max_absolute_error"] < 1e-10
    assert report["labels"]["rule_interpretation"] == {"RISK":10,"NO_RISK":10}
    assert report["labels"]["compound_reasoning"] == {"ALERT":10,"OK":10}


def test_reference_published_saturation_example_and_explicit_boundary():
    assert float(holdout.saturation(24.5)) == pytest.approx(3.075,abs=.001)
    assert holdout.reference("gdd",{"tmin":[-2,12],"tmax":[4,22],"base":10}) == 7
    assert holdout.reference("rain_deficit",{"rain":[4,8],"target":10}) == 0


def test_exact_historical_duplicate_rejected_before_write(tmp_path):
    rows = holdout.build_rows()
    path = tmp_path/"history.jsonl"
    import json
    path.write_text(json.dumps(rows[0],ensure_ascii=False),encoding="utf-8")
    # validate_rows reports relative project paths, so use a real project path mock.
    original_root = holdout.ROOT
    holdout.ROOT = tmp_path
    try:
        with pytest.raises(ValueError,match="historical overlap"):
            holdout.validate_rows(rows,[path])
    finally:
        holdout.ROOT = original_root

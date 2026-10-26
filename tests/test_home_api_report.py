"""Reporting must preserve missing usage and exclude mutable journals."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("api_report", Path(__file__).parents[1] / "scripts/report_home_api.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def row(usage):
    return {"local": {"usage": usage}, "score": {"correct": True}}


def test_missing_tokens_not_zero_and_reasoning_not_double_counted():
    data = [row({"prompt_tokens": 10, "completion_tokens": 12,
                 "completion_tokens_details": {"reasoning_tokens": 8}}), row(None),
            row({"prompt_tokens": True, "completion_tokens": -1})]
    assert report.token_measure(data, "prompt_tokens") == {"total": 10, "coverage": 1, "n": 3}
    assert report.token_measure(data, "completion_tokens")["total"] == 12
    assert report.reasoning_measure(data) == {"total": 8, "coverage": 1, "n": 3}
    assert report.token_measure([row({})], "completion_tokens")["total"] is None


def test_partial_journal_cannot_be_silently_reported():
    with pytest.raises(ValueError, match="count mismatch"):
        report.table_row(Path("run"), {"dataset_split": "old_dev"}, "m", {"summary": {"n": 2}}, [row({})])


def test_representative_uses_size_and_date_without_quality_cherry_pick():
    base = {"model": "m", "split": "old_dev", "reasoning_profile": "off-or-low"}
    candidates = [{**base, "n": 12, "run": "20261001c", "quality": 1},
                  {**base, "n": 36, "run": "20261001a", "quality": .7},
                  {**base, "n": 36, "run": "20261001b", "quality": .6},
                  {**base, "n": 100, "run": "20261001d", "split": "bilingual_dev", "quality": .9}]
    assert report.representative(candidates) == [candidates[2]]


def test_collect_skips_running_manifest(tmp_path):
    run = tmp_path / "results/20261001T120000Z_deadbeef_lm_api"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"state": "running", "models": {"m": {}}}), encoding="utf-8")
    assert report.collect(tmp_path) == ([], {})

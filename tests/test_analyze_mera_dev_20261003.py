# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mera_dev_analysis", ROOT / "scripts/analyze_mera_dev_20261003.py")
analysis = importlib.util.module_from_spec(spec); spec.loader.exec_module(analysis)


def row(prediction, valid, latency, cost=0, confidence=None):
    return {"prediction": prediction, "valid_options": valid, "error": None,
            "latency_ms": latency, "cost_usd_estimate": cost, "option_token_confidence": confidence}


def test_replay_is_not_actual_saving_and_checks_full_answer():
    local = {1: row("B", True, 10), 2: row("?", False, 20)}
    cloud = {1: row("A", True, 30, .001), 2: row("C", True, 40, .002)}
    r = analysis.policy_replay(local, cloud, {1: "B", 2: "C"}, {1: "ABCD", 2: "ABCD"}, threshold=None)
    assert r["diagnostic_set_exact_match"] == 1
    assert r["cloud_generation_calls_if_deployed"] == 1
    assert r["actual_requests_saved_in_this_screen"] == 0
    assert r["simulated_mean_latency_ms"] == 35
    assert r["simulated_known_cost_usd"] == .002
    assert not r["quality_noninferiority_established"]


def test_unpaired_or_empty_screen_cannot_be_merged():
    with pytest.raises(ValueError): analysis.policy_replay({1: row("A", True, 1)}, {}, {1: "A"}, {1: "ABCD"}, threshold=None)
    with pytest.raises(ValueError): analysis.policy_replay({}, {}, {}, {}, threshold=None)


def test_missing_confidence_routes_to_cloud_without_reference_signal():
    r = analysis.policy_replay({1: row("A", True, 1)}, {1: row("B", True, 2)}, {1: "B"}, {1: "ABCD"}, threshold=.9)
    assert r["cloud_generation_calls_if_deployed"] == 1
    assert r["diagnostic_set_exact_match"] == 1

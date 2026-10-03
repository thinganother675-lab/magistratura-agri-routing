# SPDX-License-Identifier: Apache-2.0
"""Offline paired DEV analysis. No model calls, source text, or hidden TEST.

Intervals describe resampling sensitivity of the already selected DEV examples.
They neither establish equivalence/noninferiority nor repair selection bias.
Lexical token confidence is a ranking signal, not correctness probability.
"""
from __future__ import annotations

from collections import defaultdict
import math
import statistics

import numpy as np

from agro_route.mera_screen_analysis_20261003 import (
    assert_safe_measurements, paired_correctness, percentile,
    replay_cascade, summarize_measurements,
)

ROW_FIELDS = frozenset({
    "item_id", "split", "domain", "prompt_sha256", "gold_valid", "gold_cardinality",
    "gold_issue", "prediction_valid", "prediction_cardinality", "prediction_status",
    "json_contract", "strict_set_em", "strict_set_f1", "error", "response_received",
    "latency_s", "ttft_s", "first_answer_s", "client_tps", "backend_tps", "input_tokens",
    "output_tokens", "reasoning_observed", "option_token_confidence", "option_logprob_token_n",
    "published_compatible_em", "published_compatible_f1", "em", "f1", "pred_valid",
    "generation_span_s", "finish_reason", "abstain",
})
SECRET_FIELDS = frozenset({"api_key", "token", "authorization", "password", "secret",
                          "headers", "environment", "credentials"})
THRESHOLDS = (None, .5, .7, .8, .9, .95, .98, .99, 1.)


def _secret_guard(value):
    if isinstance(value, dict):
        if SECRET_FIELDS.intersection(str(k).lower() for k in value):
            raise ValueError("Secret fields cannot enter measurement analysis")
        for child in value.values():
            _secret_guard(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _secret_guard(child)


def validate_rows(rows, expected_ids):
    assert_safe_measurements(rows)
    _secret_guard(rows)
    if any(set(r) - ROW_FIELDS for r in rows):
        raise ValueError("Only explicitly whitelisted safe row fields are accepted")
    summary = summarize_measurements(rows, expected_ids)
    if not summary["attempted_coverage"]:
        raise ValueError("Full common DEV coverage is required")
    for row in rows:
        if row.get("gold_valid") is True and (isinstance(row.get("em"), bool) or not isinstance(row.get("em"), int)):
            raise ValueError("Strict EM requires integer 0 or 1, not boolean")
        for key in ("latency_s", "ttft_s", "generation_span_s", "client_tps", "backend_tps"):
            value = row.get(key)
            if value is not None and not _finite(value):
                raise ValueError("Timing and rate values must be finite nonnegative seconds or tokens/s")
        for key in ("ttft_s", "generation_span_s"):
            if row.get(key) is not None and row.get("latency_s") is not None and row[key] > row["latency_s"] + 1e-6:
                raise ValueError("Timing component exceeds end-to-end latency")
    return summary


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def distribution(values, *, unit):
    values = list(values)
    observed = [float(v) for v in values if _finite(v)]
    return {"n_observed": len(observed), "n_total": len(values), "unit": unit,
            "mean": statistics.mean(observed) if observed else None,
            "min": min(observed) if observed else None,
            "p50": percentile(observed, .5), "p90": percentile(observed, .9),
            "p95": percentile(observed, .95),
            "p99": percentile(observed, .99) if len(observed) >= 100 else None,
            "p99_status": "DESCRIPTIVE_TAIL_ONLY" if len(observed) >= 100 else "INSUFFICIENT_N_LT_100",
            "max": max(observed) if observed else None}


def align_pairs(left_rows, right_rows, expected_ids):
    expected_ids = list(expected_ids)
    validate_rows(left_rows, expected_ids); validate_rows(right_rows, expected_ids)
    paired_correctness(left_rows, right_rows, expected_ids)
    left, right = {r["item_id"]: r for r in left_rows}, {r["item_id"]: r for r in right_rows}
    for item in expected_ids:
        if left[item].get("prompt_sha256") != right[item].get("prompt_sha256"):
            raise ValueError("Paired prompts differ")
    return [(left[i], right[i]) for i in expected_ids if left[i]["gold_valid"]]


def paired_bootstrap(left_rows, right_rows, expected_ids, *, samples=10000, seed=20261003):
    """Fixed-domain-count paired bootstrap of left minus right EM and F1."""
    pairs = align_pairs(left_rows, right_rows, expected_ids)
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 100:
        raise ValueError("At least 100 bootstrap replicates required")
    groups = defaultdict(list)
    for a, b in pairs:
        groups[a["domain"]].append([a["em"] - b["em"], a["f1"] - b["f1"]])
    if not pairs:
        raise ValueError("At least one valid paired reference required")
    rng = np.random.default_rng(seed)
    draws = np.zeros((samples, 2))
    for domain in sorted(groups):
        differences = np.asarray(groups[domain], dtype=float)
        indexes = rng.integers(0, len(differences), size=(samples, len(differences)))
        draws += differences[indexes].sum(axis=1)
    draws /= len(pairs)
    observed = np.asarray([[a["em"] - b["em"], a["f1"] - b["f1"]] for a, b in pairs]).mean(axis=0)
    return {"status": "DEV", "method": "DOMAIN_STRATIFIED_PAIRED_PERCENTILE_BOOTSTRAP_95_DESCRIPTIVE",
            "n": len(pairs), "replicates": samples, "seed": seed,
            "em_left_minus_right": float(observed[0]), "f1_left_minus_right": float(observed[1]),
            "em_interval": [float(x) for x in np.quantile(draws[:, 0], [.025, .975])],
            "f1_interval": [float(x) for x in np.quantile(draws[:, 1], [.025, .975])],
            "domain_counts_fixed": True, "independent_confirmatory_inference": False,
            "equivalence_or_noninferiority_established": False, "p_value": None}


def grouped_pairs(left_rows, right_rows, expected_ids, *, field):
    if field not in ("domain", "answer_cardinality"):
        raise ValueError("Unsupported grouping")
    groups = defaultdict(list)
    for a, b in align_pairs(left_rows, right_rows, expected_ids):
        group = a["domain"] if field == "domain" else "single" if a["gold_cardinality"] == 1 else "multiple"
        groups[group].append((a, b))
    result = {}
    for group, pairs in sorted(groups.items()):
        left, right = [a for a, _ in pairs], [b for _, b in pairs]
        ids = [r["item_id"] for r in left]
        ls, rs = summarize_measurements(left, ids), summarize_measurements(right, ids)
        result[group] = {"n": len(pairs),
                         "left_em_count": ls["strict_em_count"], "right_em_count": rs["strict_em_count"],
                         "left_em": ls["strict_set_em"], "right_em": rs["strict_set_em"],
                         "em_left_minus_right": ls["strict_set_em"] - rs["strict_set_em"],
                         "left_f1": ls["strict_set_f1"], "right_f1": rs["strict_set_f1"],
                         "f1_left_minus_right": ls["strict_set_f1"] - rs["strict_set_f1"],
                         "discordance": paired_correctness(left, right, ids)}
    return result


def _auc(scores, labels):
    correct = np.asarray(scores)[np.asarray(labels) == 1]
    wrong = np.sort(np.asarray(scores)[np.asarray(labels) == 0])
    if not len(correct) or not len(wrong):
        return None
    strict = np.searchsorted(wrong, correct, side="left")
    weak = np.searchsorted(wrong, correct, side="right")
    return float(np.sum((strict + weak) / 2) / (len(correct) * len(wrong)))


def confidence_analysis(rows, expected_ids, *, samples=2000, seed=20261003):
    validate_rows(rows, expected_ids)
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 100:
        raise ValueError("At least 100 bootstrap replicates required")
    pairs = [(r["option_token_confidence"], r["em"]) for r in rows if r["gold_valid"] and r["pred_valid"]
             and not r.get("error") and _finite(r.get("option_token_confidence")) and r["option_token_confidence"] <= 1]
    scores = np.asarray([a for a, _ in pairs]); labels = np.asarray([b for _, b in pairs])
    auc = _auc(scores, labels)
    intervals = None
    if auc is not None:
        correct, wrong = scores[labels == 1], scores[labels == 0]
        rng = np.random.default_rng(seed)
        draws = []
        for _ in range(samples):
            c = rng.choice(correct, size=len(correct)); w = rng.choice(wrong, size=len(wrong))
            draws.append(_auc(np.concatenate((c, w)), np.concatenate((np.ones(len(c)), np.zeros(len(w))))))
        intervals = [float(x) for x in np.quantile(draws, [.025, .975])]
    bins = []
    for index in range(10):
        lower, upper = index / 10, (index + 1) / 10
        selected = [(s, y) for s, y in pairs if lower <= s and (s < upper or index == 9 and s <= upper)]
        bins.append({"lower": lower, "upper": upper, "n": len(selected),
                     "mean_lexical_confidence": statistics.mean(s for s, _ in selected) if selected else None,
                     "observed_accuracy": statistics.mean(y for _, y in selected) if selected else None})
    selective = []
    for threshold in THRESHOLDS[1:]:
        selected = [(s, y) for s, y in pairs if s >= threshold]
        selective.append({"threshold": threshold, "n_retained": len(selected),
                          "coverage_of_scored_observed": len(selected) / len(pairs) if pairs else None,
                          "retained_em": statistics.mean(y for _, y in selected) if selected else None,
                          "rejected_n": len(pairs) - len(selected)})
    return {"status": "DEV_LEXICAL_CONFIDENCE_DIAGNOSTIC", "n_total": len(rows), "n_observed_scored": len(pairs),
            "auc_correctness": auc, "auc_interval": intervals, "bootstrap_replicates": samples, "bootstrap_seed": seed,
            "auc_interval_method": "CLASS_STRATIFIED_PERCENTILE_BOOTSTRAP_95_DESCRIPTIVE",
            "calibrated_probability_of_correctness": False, "ece": None, "brier": None,
            "ece_brier_status": "NOT_APPLICABLE_UNCALIBRATED_LEXICAL_SIGNAL",
            "confidence_bins": bins, "selective_thresholds": selective,
            "primary_threshold_selected": False, "independent_holdout": False}


def fixed_threshold_replay(local, cloud, expected_ids):
    """No new threshold fitting or budget winner. Keep every existing fixed grid point."""
    validate_rows(local, expected_ids); validate_rows(cloud, expected_ids)
    align_pairs(local, cloud, expected_ids)
    results = []
    for threshold in THRESHOLDS:
        replay = replay_cascade(local, cloud, expected_ids, threshold=threshold)
        results.append({key: replay[key] for key in (
            "status", "threshold", "n_scored", "strict_em_count", "strict_set_em", "strict_set_f1",
            "cloud_calls_if_deployed", "cloud_fraction_if_deployed", "invalid_output", "errors",
            "actual_requests_saved", "live_latency_or_cost_savings_established")})
    return {"status": "SIMULATED", "fixed_grid": list(THRESHOLDS), "newly_fitted_threshold": False,
            "grid": results, "confidence_benefit_established": False, "actual_requests_saved": 0}

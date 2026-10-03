# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Reproduce frozen HOME150 numerical aggregates without inputs or inference."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from agro_route.home_stats import cluster_bootstrap_interval

ROOT = Path(__file__).resolve().parents[1]
FIELDS = frozenset(("id", "group", "category", "language", "method", "status", "route", "correct", "critical_error",
                    "qa_f1", "numeric_error", "cloud_calls", "local_calls", "tool_calls", "latency_ms", "cost_usd", "call_errors"))


def reproduce(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or any(set(row) != FIELDS for row in rows):
        raise ValueError("Measurements-only schema required")
    pairs = [(row["id"], row["method"]) for row in rows]
    if len(set(pairs)) != len(pairs) or any(row["status"] != "MEASURED" for row in rows):
        raise ValueError("Unique fully measured ID-method pairs required")
    report = {}
    for method in dict.fromkeys(row["method"] for row in rows):
        subset = [row for row in rows if row["method"] == method]
        qualities = [row["correct"] for row in subset]
        if any(type(value) is not bool for value in qualities):
            raise ValueError("Correctness must be frozen booleans")
        interval = cluster_bootstrap_interval(qualities, [row["group"] for row in subset], repeats=5000, seed=20261001)
        seconds = [row["latency_ms"] / 1000 for row in subset]
        if any(not math.isfinite(value) or value < 0 for value in seconds):
            raise ValueError("Finite nonnegative measured latencies required")
        report[method] = {"measured_n": len(subset), "correct": sum(qualities),
                          "quality": sum(qualities) / len(subset), "quality_ci95": interval["ci95"],
                          "critical_errors": sum(row["critical_error"] for row in subset),
                          "critical_error_rate": sum(row["critical_error"] for row in subset) / len(subset),
                          "cloud_calls": sum(row["cloud_calls"] for row in subset),
                          "local_calls": sum(row["local_calls"] for row in subset),
                          "tool_calls": sum(row["tool_calls"] for row in subset),
                          "latency_mean_s": float(np.mean(seconds)),
                          "latency_p50_s": float(np.quantile(seconds, .5)),
                          "latency_p95_s": float(np.quantile(seconds, .95)),
                          "cloud_cost_known_usd": sum(row["cost_usd"] for row in subset if row["cost_usd"] is not None)}
    return report


def compare(actual, expected):
    if set(actual) != set(expected):
        raise AssertionError("Policy set differs")
    for method in expected:
        for metric, value in expected[method].items():
            observed = actual[method][metric]
            if isinstance(value, list):
                match = len(value) == len(observed) and all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) for a, b in zip(value, observed))
            else:
                match = math.isclose(value, observed, rel_tol=1e-12, abs_tol=1e-12)
            if not match:
                raise AssertionError(f"Frozen aggregate differs: {method}/{metric}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/public_sample/home150_measurements.jsonl")
    parser.add_argument("--expected", type=Path, default=ROOT / "data/public_sample/home150_expected_aggregates.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = reproduce(args.data)
    compare(report, json.loads(args.expected.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    print(json.dumps({"policies": len(report), "decision_rows": sum(row["measured_n"] for row in report.values()),
                      "metrics_per_policy": len(next(iter(report.values()))), "all_retained_metrics_match": True,
                      "new_external_requests": 0, "gold_independently_validated": False}))


if __name__ == "__main__":
    main()

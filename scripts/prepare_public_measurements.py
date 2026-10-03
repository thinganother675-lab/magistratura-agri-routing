# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Create a new measurements-only projection; never modify research outputs."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/analysis_input_reconciled_20261002_052358Z_804ced2b/analysis_20261002_052438Z_2c0beea8"
FIELDS = ("id", "group", "category", "language", "method", "status", "route", "correct", "critical_error",
          "qa_f1", "numeric_error", "cloud_calls", "local_calls", "tool_calls", "latency_ms", "cost_usd", "call_errors")
METRICS = ("measured_n", "correct", "quality", "quality_ci95", "critical_errors", "critical_error_rate",
           "cloud_calls", "local_calls", "tool_calls", "latency_mean_s", "latency_p50_s", "latency_p95_s", "cloud_cost_known_usd")


def typed(value):
    if value == "UNKNOWN":
        return None
    if value in {"True", "False"}:
        return value == "True"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def prepare(destination):
    normalized = list(csv.DictReader((SOURCE / "normalized.csv").open(encoding="utf-8-sig", newline="")))
    ids = {name: f"case_{index:03d}" for index, name in enumerate(sorted({row["id"] for row in normalized}), 1)}
    groups = {name: f"group_{index:03d}" for index, name in enumerate(sorted({row["group"] for row in normalized}), 1)}
    projected = [{key: (ids[row[key]] if key == "id" else groups[row[key]] if key == "group" else typed(row[key]))
                  for key in FIELDS} for row in normalized]
    summaries = list(csv.DictReader((SOURCE / "summary.csv").open(encoding="utf-8-sig", newline="")))
    expected = {row["method"]: {key: typed(row[key]) for key in METRICS} for row in summaries}
    provenance = {"source": "Historical HOME150 measured decisions, 2026-10-02, frozen scorer v1",
                  "projection_fields": list(FIELDS), "cases": len(ids), "groups": len(groups), "rows": len(projected),
                  "source_normalized_csv_sha256": hashlib.sha256((SOURCE / "normalized.csv").read_bytes()).hexdigest(),
                  "source_summary_csv_sha256": hashlib.sha256((SOURCE / "summary.csv").read_bytes()).hexdigest(),
                  "license": "CC0-1.0 for original measurement facts/projection only",
                  "removed": ["input", "context", "inputs", "gold", "expected", "output", "error prose", "provider response", "account metadata"],
                  "limitation": "Reproduces historical quantitative aggregates, not independent scoring/gold validation; no new inference"}
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in [("home150_measurements.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in projected)),
                       ("home150_expected_aggregates.json", json.dumps(expected, indent=2) + "\n"),
                       ("home150_provenance.json", json.dumps(provenance, indent=2) + "\n")]:
        with (destination / name).open("x", encoding="utf-8") as handle:
            handle.write(data)
    return {"rows": len(projected), "cases": len(ids), "groups": len(groups), "methods": len(expected)}


if __name__ == "__main__":
    print(json.dumps(prepare(ROOT / "data/public_sample")))

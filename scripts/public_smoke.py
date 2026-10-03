# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Run original formal scenarios offline; no model or network requests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agro_route.evaluation import score
from agro_route.models import public_request
from agro_route.home_policy import offline

ROOT = Path(__file__).resolve().parents[1]


def forbidden(_):
    raise AssertionError("Public deterministic smoke must not dispatch inference")


def run(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    decisions = []
    for sample in rows:
        request = public_request(sample)
        if any(key in request for key in ("expected", "gold", "category", "scoring")):
            raise AssertionError("Gold leakage")
        result = offline(request, forbidden)
        decisions.append({"id": sample["id"], "route": result["route"], "output": result["output"],
                          "correct": score(sample, result["output"])["correct"]})
    return {"purpose": "SYNTHETIC SOFTWARE SMOKE; not confirmatory science", "cases": len(rows),
            "correct": sum(row["correct"] for row in decisions), "external_requests": 0,
            "local_model_requests": 0, "decisions": decisions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/public_sample/benchmark.jsonl")
    args = parser.parse_args()
    report = run(args.data)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if not report["cases"] or report["correct"] != report["cases"]:
        raise SystemExit(1)

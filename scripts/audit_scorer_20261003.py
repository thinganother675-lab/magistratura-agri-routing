# SPDX-License-Identifier: Apache-2.0
"""Read-only historical diagnostics; new run/output directory required."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/analysis_input_reconciled_20261002_052358Z_804ced2b/raw_decisions.jsonl"
CAUSES = ("arithmetic_or_formula", "unit", "schema_action", "formatting", "parsing", "incomplete_response", "evaluator_artifact")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_inventory(root=ROOT):
    """Protect old data, frozen sources/protocol and old experiment directories."""
    paths = set()
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0"))
    for folder in ("data", "experiments", "src/agro_route", "scripts", "tests"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and path.relative_to(root).as_posix() in tracked and path.suffix in {".py", ".json", ".jsonl", ".md"}:
                paths.add(path)
    for folder in (root / "results").iterdir():
        if folder.is_dir() and "20261003" not in folder.name:
            for path in folder.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    paths.add(path)
    return {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(paths)}


def independent_numeric(tool, inputs):
    """Decimal reference independent of tools.execute/evaluation.score.

    Uses the exact formula supplied by the historical task. For VPD, Decimal.exp
    removes the floating exp implementation shared with the old executor.
    """
    with localcontext() as ctx:
        ctx.prec = 50
        d = lambda key: Decimal(str(inputs[key]))
        if tool == "gdd":
            return sum(max(Decimal(0), (Decimal(str(a)) + Decimal(str(b))) / 2 - d("base")) for a, b in zip(inputs["tmin"], inputs["tmax"]))
        if tool == "rain_deficit":
            return max(Decimal(0), d("target") - sum(Decimal(str(x)) for x in inputs["rain"]))
        if tool == "vpd":
            return Decimal(".6108") * (Decimal("17.27") * d("temperature") / (d("temperature") + Decimal("237.3"))).exp() * (1 - d("rh") / 100)
        if tool == "et0":
            numerator = Decimal(".408") * d("delta") * (d("rn") - d("g")) + d("gamma") * 900 / (d("temperature") + 273) * d("u2") * (d("es") - d("ea"))
            denominator = d("delta") + d("gamma") * (1 + Decimal(".34") * d("u2"))
            return numerator / denominator
        raise ValueError("Unsupported historical formula")


def numeric_diagnostic(row):
    sample, result = row["sample"], row["result"]
    out = result.get("output") or {}
    trace = result.get("trace", [])
    raw = trace[-1].get("raw") or {} if trace else {}
    content = raw.get("final_content")
    parse_failure = False
    raw_matches_parsed = False
    try:
        parsed = json.loads(content)
        raw_matches_parsed = parsed == out
    except (ValueError, TypeError):
        parse_failure = True
    actual = out.get("numeric")
    valid = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
    expected = sample["expected"]["numeric"]
    independent = independent_numeric(sample["reference_tool"], sample["inputs"])
    ref_ok = math.isclose(float(independent), expected, rel_tol=1e-12, abs_tol=1e-12)
    within = valid and math.isclose(actual, expected, rel_tol=.01, abs_tol=.02)
    numeric_answer_matches_field = False
    try:
        numeric_answer_matches_field = Decimal(out.get("answer", "")) == Decimal(str(actual))
    except Exception:
        pass
    causes = {
        "arithmetic_or_formula": valid and not math.isclose(actual, float(independent), rel_tol=.01, abs_tol=.02),
        "unit": out.get("unit") != sample["expected"]["unit"],
        "schema_action": out.get("action") != "ANSWER" or not valid or not isinstance(out.get("answer"), str),
        "formatting": bool(isinstance(content, str) and content.strip().startswith("```")),
        "parsing": parse_failure or not raw_matches_parsed,
        "incomplete_response": not out or raw.get("finish_reason") != "stop" or raw.get("stream_done") is False,
        "evaluator_artifact": not ref_ok or (bool(within and out.get("unit") == sample["expected"]["unit"] and out.get("action") == "ANSWER") != row["score"]["correct"]),
    }
    return {
        "id": sample["id"], "method": row["method"], "reference_tool": sample["reference_tool"],
        "historical_correct_unchanged": row["score"]["correct"], "gold_numeric": expected,
        "independent_decimal_numeric": str(independent), "independent_gold_agreement": ref_ok,
        "output_numeric": actual, "expected_unit": sample["expected"]["unit"], "output_unit": out.get("unit"),
        "absolute_error": abs(actual - expected) if valid else None,
        "tolerance_limit": max(.02, .01 * max(abs(actual), abs(expected))) if valid else None,
        "raw_parse_matches_output": raw_matches_parsed, "answer_numeric_matches_field": numeric_answer_matches_field,
        "finish_reason": raw.get("finish_reason"), "failure_causes": [k for k, v in causes.items() if v],
        **causes,
        "causal_precision": "Wrong numerical result under the explicit supplied formula; raw contains no derivation, so exact arithmetic vs formula-selection error is unidentifiable.",
    }


def compound_diagnostic(row):
    s, r = row["sample"], row["result"]
    i, out = s["inputs"], r.get("output") or {}
    d = lambda v: Decimal(str(v))
    heat = sum(max(Decimal(0), (d(lo) + d(hi)) / 2 - d(i["base_c"])) for lo, hi in zip(i["daily_min"], i["daily_max"]))
    rain = sum(d(x) for x in i["daily_rain"])
    heat_condition, rain_condition = heat > d(i["heat_threshold"]), rain < d(i["rain_target_mm"])
    decision = "ALERT" if heat_condition and rain_condition else "OK"
    answer = out.get("answer", "")
    literal = bool(s["context"] and len(answer) >= 2 and answer.lower() in s["context"].lower() and out.get("action") == "ANSWER")
    return {"id": s["id"], "method": row["method"], "route": r["route"], "heat": str(heat), "rain": str(rain),
            "heat_condition": heat_condition, "rain_condition": rain_condition, "independent_decision": decision,
            "gold_decision_unchanged": s["expected"]["answers"][0], "output_answer": answer,
            "historical_correct_unchanged": row["score"]["correct"], "historical_literal_grounded": literal,
            "literal_would_accept_false_branch": literal and answer != decision,
            "verifier_governs_route": row["method"] in {"hybrid", "offline"},
            "false_branch_accepted": literal and answer != decision and r["route"] == "LOCAL_MODEL" and row["method"] in {"hybrid", "offline"},
            "independent_gold_agreement": decision in s["expected"]["answers"],
            "diagnostic_cause": "Both branch labels occur in public rule; lexical presence cannot establish conjunction truth."}


def write_table(path, rows):
    path.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with path.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)


def main(output=None):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ_") + uuid.uuid4().hex[:8] + "_scorer_audit"
    dest = output or ROOT / "results" / run_id
    if dest.exists():
        raise FileExistsError("Choose a new audit directory; historical diagnostics are immutable")
    before = frozen_inventory()
    rows = [json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines()]
    numeric = [numeric_diagnostic(row) for row in rows if row["method"] == "local" and row["sample"]["category"] == "numeric"]
    compound = [compound_diagnostic(row) for row in rows if row["sample"]["category"] == "compound_reasoning"]
    assert len(numeric) == 30 and len({r["id"] for r in numeric}) == 30
    assert len(compound) == 100
    dest.mkdir(parents=True, exist_ok=False)
    write_table(dest / "home150_local_numeric_diagnostics_v2", numeric)
    write_table(dest / "home150_compound_diagnostics_v2", compound)
    after = frozen_inventory()
    summary = {"run_id": dest.name, "diagnostic_version": 2, "actual_utc": datetime.now(timezone.utc).isoformat(), "role": "POST_HOC_DIAGNOSTIC_ONLY_NOT_RESCORING",
               "protected_inventory_scope": "Git-tracked historical data/protocol/source/test files plus all files in pre-20261003 results directories; concurrently authored untracked new scripts excluded",
               "new_generations": 0, "human_review": False, "numeric_n": len(numeric),
               "historic_local_numeric_correct": sum(r["historical_correct_unchanged"] for r in numeric),
               "numeric_cause_counts": {cause: sum(r[cause] for r in numeric) for cause in CAUSES},
               "cause_counts_can_overlap": True, "independent_numeric_gold_agreement": sum(r["independent_gold_agreement"] for r in numeric),
               "compound_false_acceptance_by_method": dict(Counter(r["method"] for r in compound if r["false_branch_accepted"])),
               "compound_false_literal_would_pass_by_method": dict(Counter(r["method"] for r in compound if r["literal_would_accept_false_branch"])),
               "interpretation_correction": "v2 distinguishes actual verifier acceptance (hybrid/offline) from fixed local outputs where literal grounding would have passed but was not applied. First diagnostic run preserved.",
               "independent_compound_gold_agreement": sum(r["independent_gold_agreement"] for r in compound),
               "protected_historical_files": len(before), "protected_hashes_unchanged": before == after,
               "historical_raw_path": RAW.relative_to(ROOT).as_posix(), "historical_raw_sha256": digest(RAW),
               "limitations": ["No model reasoning trace: result error cannot uniquely identify arithmetic operation vs formula selection", "No new scoring applied to HOME150", "No agronomist or human review performed"]}
    (dest / "frozen_historical_hashes.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if before != after:
        raise RuntimeError("Protected historical bytes changed during audit")
    print(json.dumps({"run_id": dest.name, "numeric_causes": summary["numeric_cause_counts"], "false_acceptance": summary["compound_false_acceptance_by_method"], "hashes_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    main(parser.parse_args().output)

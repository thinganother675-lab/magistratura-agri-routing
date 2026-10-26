# SPDX-License-Identifier: Apache-2.0
"""Safe append-only aggregation of typed Study C observed scores.

Expected numerical values are never needed here. Metadata records only which
cases are eligible for each metric. An empty/failed response cannot receive
component credit merely because an expected tool was absent.
"""
from __future__ import annotations

from collections import Counter
from agro_route.resource_analysis_20261003 import distribution

FIELDS = frozenset({"model_key", "source_run", "latency_s", "error", "id", "group", "category",
                    "expected_action", "parse_success", "correct", "action_correct", "tool_correct",
                    "numeric_correct", "numeric_case", "numeric_rounding_1e4_correct", "output_unit_correct",
                    "declared_selection_tool_replay_correct", "declared_selection_tool_replay_status"})
META_FIELDS = frozenset({"id", "expected_action", "tool_eligible", "unit_conversion_case"})


def aggregate(rows, case_metadata):
    if not rows or not case_metadata:
        raise ValueError("Complete Study C rows and safe metadata required")
    if any(set(r)-FIELDS for r in rows) or any(set(c)-META_FIELDS for c in case_metadata):
        raise ValueError("Only whitelisted score/eligibility fields; no gold or prompt content")
    expected = {c["id"]: c for c in case_metadata}
    if len(expected) != len(case_metadata):
        raise ValueError("Duplicate case metadata")
    models = {}
    for model in sorted({r["model_key"] for r in rows}):
        own = [r for r in rows if r["model_key"] == model]
        if len({r["id"] for r in own}) != len(own) or {r["id"] for r in own} != set(expected):
            raise ValueError("Each model requires full unique common case coverage")
        for r in own:
            if r["expected_action"] != expected[r["id"]]["expected_action"]:
                raise ValueError("Expected-action metadata mismatch")
            if r["numeric_case"] != (r["expected_action"] == "ANSWER"):
                raise ValueError("Numerical eligibility mismatch")
            if (r["error"] or not r["parse_success"]) and r["correct"]:
                raise ValueError("Failed/unparsed output cannot have complete credit")
        eligible = [r for r in own if expected[r["id"]]["tool_eligible"]]
        numeric = [r for r in own if r["numeric_case"]]
        missing = [r for r in own if r["expected_action"] == "ASK_FOR_DATA"]
        units = [r for r in own if expected[r["id"]]["unit_conversion_case"]]
        unsupported = [r for r in own if not expected[r["id"]]["tool_eligible"]]
        valid = lambda r: r["parse_success"] is True and not r["error"]
        count = lambda values, field: sum(valid(r) and r[field] is True for r in values)
        sources = dict(Counter(r.get("source_run", "UNKNOWN") for r in own))
        models[model] = {
            "n": len(own), "source_run_counts": sources, "source_runs": sorted(sources),
            "correct": count(own, "correct"), "action_correct": count(own, "action_correct"),
            "parse_invalid": sum(r["parse_success"] is not True for r in own), "errors": sum(bool(r["error"]) for r in own),
            "declared_real_tool_n": len(eligible), "declared_real_tool_correct": count(eligible, "tool_correct"),
            "unsupported_task_n": len(unsupported), "unsupported_task_correct": count(unsupported, "correct"),
            "numeric_n": len(numeric), "numeric_correct": count(numeric, "numeric_correct"),
            "numeric_rounding_1e4_correct": count(numeric, "numeric_rounding_1e4_correct"),
            "missing_input_or_invalid_input_n": len(missing), "missing_input_or_invalid_input_correct": count(missing, "correct"),
            "unit_conversion_n": len(units), "unit_conversion_correct": count(units, "correct"),
            "latency_s": distribution([r["latency_s"] for r in own], unit="s"),
            "declared_tool_executor_replay": {"status": "SIMULATED", "n_tool_eligible": len(eligible),
                "correct": count(eligible, "declared_selection_tool_replay_correct"),
                "live_model_tool_calls": 0, "typed_task_and_inputs_supplied": True},
        }
    return {"status": "DEV", "study": "C", "models": models,
            "tool_choice_denominator_excludes_unsupported_null_tool": True,
            "error_and_parse_gate_required_for_components": True,
            "unit_conversion_denominator_source": "expected.reason_code == EXPLICIT_CONVERSION_REQUIRED",
            "private_test_run": False, "live_model_tool_use_evaluated": False}

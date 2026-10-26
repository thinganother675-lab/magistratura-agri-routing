"""Run-result validation, separate frozen numerical and declared-tool metrics."""
import math
from .deterministic_study_20261003 import public_request, score_case, execute_request
from .lm_telemetry_20261003 import parse_json_presentation


def score_text(case, text, error=None):
    public_request(case)
    try:
        output = parse_json_presentation(text) if not error else {}
        parse_ok = bool(output) and output.get("action") in {"ANSWER", "ASK_FOR_DATA", "ABSTAIN"}
    except (ValueError, TypeError):
        output, parse_ok = {}, False
    scored = score_case(case, output)
    expected = case["expected"]
    answer = expected["action"] == "ANSWER"
    value = output.get("numeric")
    numeric_finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    # Fixed secondary rounding diagnostic; never replaces the frozen primary.
    rounded = answer and numeric_finite and output.get("unit") == expected.get("unit") and abs(value - expected["numeric"]) <= max(expected["abs_tolerance"], 1e-4)
    selected = output.get("tool")
    replay = execute_request(public_request(case), selected_tool=selected) if isinstance(selected, str) else None
    replay_score = score_case(case, replay) if replay is not None else None
    return {"id": case["id"], "group": case["group"], "category": case["category"],
            "expected_action": expected["action"], "parse_success": parse_ok,
            **scored, "numeric_case": answer, "numeric_rounding_1e4_correct": bool(rounded),
            "output_unit_correct": output.get("unit") == expected.get("unit") if answer else None,
            "declared_selection_tool_replay_correct": replay_score["correct"] if replay_score else False,
            "declared_selection_tool_replay_status": "SIMULATED_EXECUTOR_FROM_DECLARED_TOOL_NOT_LIVE_MODEL_TOOL_USE"}

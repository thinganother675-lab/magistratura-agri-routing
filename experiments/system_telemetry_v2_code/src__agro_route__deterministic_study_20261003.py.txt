"""Separate Study C reference tools; never imported by historical HOME150 routing.

Only explicit, typed computational requests are supported. This reference router
does not demonstrate general natural-language intent recognition or crop advice.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

VERSION = "study_c_technical_20261003_v1"
TASK_TO_TOOL = {
    "heat_sum_simple_daily": "gdd_simple_daily_v1",
    "vapour_deficit_single_observation": "vpd_single_observation_v1",
    "vapour_deficit_daily_extrema": "vpd_daily_extrema_v1",
    "reference_et_daily_precomputed": "et0_fao56_daily_v1",
    "experimental_rain_target_gap": "rain_target_gap_v1",
}
REQUIRED = {
    "gdd_simple_daily_v1": ("tmin", "tmax", "base"),
    "vpd_single_observation_v1": ("temperature", "rh"),
    "vpd_daily_extrema_v1": ("tmin", "tmax", "rhmin", "rhmax"),
    "et0_fao56_daily_v1": ("temperature", "rn", "g", "u2", "es", "ea", "delta", "gamma", "wind_height"),
    "rain_target_gap_v1": ("target", "rain"),
}
UNITS = {
    "gdd_simple_daily_v1": {"temperature": "C", "time_step": "day"},
    "vpd_single_observation_v1": {"temperature": "C", "humidity": "%"},
    "vpd_daily_extrema_v1": {"temperature": "C", "humidity": "%", "time_step": "day"},
    "et0_fao56_daily_v1": {
        "temperature": "C", "radiation": "MJ/m2/day", "wind": "m/s",
        "pressure": "kPa", "slope": "kPa/C", "height": "m", "time_step": "day",
    },
    "rain_target_gap_v1": {"precipitation": "mm"},
}
OUTPUT_UNITS = {
    "gdd_simple_daily_v1": "degC day", "vpd_single_observation_v1": "kPa",
    "vpd_daily_extrema_v1": "kPa", "et0_fao56_daily_v1": "mm/day", "rain_target_gap_v1": "mm",
}
PRIVATE_KEYS = frozenset({"gold", "expected", "expected_output", "reference_answer", "answers", "correct", "label", "labels", "tolerance"})


class ContractError(ValueError):
    """Input contract failure, including absent explicitly required data."""

    def __init__(self, reason: str, fields: list[str]):
        super().__init__(reason + ": " + ", ".join(fields))
        self.reason = reason
        self.fields = sorted(fields)


def _no_private_fields(value: Any) -> None:
    if isinstance(value, dict):
        if any(str(k).casefold() in PRIVATE_KEYS for k in value):
            raise ValueError("Private evaluation fields cannot enter a public request")
        for nested in value.values():
            _no_private_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _no_private_fields(nested)


def public_request(case: dict) -> dict:
    """Deep projection: sources, tolerances and expected answers stay evaluator-side."""
    if case.get("split") != "development_reference" or not str(case.get("id", "")).startswith("study_c_"):
        raise ValueError("Only this new development reference pack is supported")
    request = deepcopy(case["request"])
    _no_private_fields(request)
    return request


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ContractError("INVALID_INPUTS", [field])
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        raise ContractError("INVALID_INPUTS", [field]) from None
    if not math.isfinite(numeric):
        raise ContractError("INVALID_INPUTS", [field])
    return numeric


def _series(value: Any, field: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ContractError("INVALID_INPUTS", [field])
    return [_number(item, field) for item in value]


def _bounded(value: Any, field: str, lower: float, upper: float) -> float:
    numeric = _number(value, field)
    if not lower <= numeric <= upper:
        raise ContractError("INVALID_INPUTS", [field])
    return numeric


def _saturation(temperature: float) -> float:
    # FAO-56 Eq.11: saturation pressure over water; not an ice correction.
    return 0.6108 * math.exp(17.27 * temperature / (temperature + 237.3))


def _calculate(tool: str, inputs: dict) -> float:
    if tool == "gdd_simple_daily_v1":
        low, high = _series(inputs["tmin"], "tmin"), _series(inputs["tmax"], "tmax")
        base = _bounded(inputs["base"], "base", -20, 40)
        if len(low) != len(high) or any(a > b for a, b in zip(low, high)):
            raise ContractError("INVALID_INPUTS", ["tmin", "tmax"])
        if any(not -60 <= v <= 60 for v in low + high):
            raise ContractError("INVALID_INPUTS", ["tmin", "tmax"])
        return math.fsum(max(0., (a + b) / 2 - base) for a, b in zip(low, high))
    if tool == "vpd_single_observation_v1":
        temperature = _bounded(inputs["temperature"], "temperature", -40, 60)
        rh = _bounded(inputs["rh"], "rh", 0, 100)
        return _saturation(temperature) * (1 - rh / 100)
    if tool == "vpd_daily_extrema_v1":
        lo = _bounded(inputs["tmin"], "tmin", -40, 60)
        hi = _bounded(inputs["tmax"], "tmax", -40, 60)
        rhlo = _bounded(inputs["rhmin"], "rhmin", 0, 100)
        rhhi = _bounded(inputs["rhmax"], "rhmax", 0, 100)
        if lo > hi or rhlo > rhhi:
            raise ContractError("INVALID_INPUTS", ["tmin", "tmax", "rhmin", "rhmax"])
        # FAO-56 Eqs.12,17. No substitution with saturation at mean temperature.
        es = (_saturation(lo) + _saturation(hi)) / 2
        ea = (_saturation(lo) * rhhi / 100 + _saturation(hi) * rhlo / 100) / 2
        return es - ea
    if tool == "et0_fao56_daily_v1":
        temperature = _bounded(inputs["temperature"], "temperature", -40, 60)
        rn, soil = _number(inputs["rn"], "rn"), _number(inputs["g"], "g")
        wind = _bounded(inputs["u2"], "u2", 0, 30)
        es, ea = _bounded(inputs["es"], "es", 0, 15), _bounded(inputs["ea"], "ea", 0, 15)
        slope = _bounded(inputs["delta"], "delta", 1e-12, 2)
        gamma = _bounded(inputs["gamma"], "gamma", 1e-12, 1)
        if _number(inputs["wind_height"], "wind_height") != 2:
            raise ContractError("EXPLICIT_CONVERSION_REQUIRED", ["u2", "wind_height"])
        if ea > es:
            raise ContractError("INVALID_INPUTS", ["ea", "es"])
        # Eq.6 with explicit derived parameters. No default G=0 or inferred Rn.
        numerator = 0.408 * slope * (rn - soil) + gamma * 900 / (temperature + 273) * wind * (es - ea)
        denominator = slope + gamma * (1 + 0.34 * wind)
        return numerator / denominator
    target = _bounded(inputs["target"], "target", 0, 1e6)
    rain = _series(inputs["rain"], "rain")
    # Explicit technical input bound, not a crop/irrigation threshold. Finite
    # floats alone are insufficient: fsum([1e308, 1e308]) raises OverflowError.
    if any(not 0 <= v <= 1e6 for v in rain):
        raise ContractError("INVALID_INPUTS", ["rain"])
    return max(0., target - math.fsum(rain))


def execute_request(request: dict, *, selected_tool: str | None = None) -> dict:
    """No model/API invocation; optional selected_tool records an evaluated choice.

    Missing data/units produce ASK_FOR_DATA. Unknown tasks or incorrect tool
    choices abstain rather than silently calculating a different quantity.
    """
    _no_private_fields(request)
    if not isinstance(request, dict):
        raise ValueError("Request must be an object")
    if set(request) - {"question_ru", "task", "inputs", "units"}:
        raise ValueError("Unexpected public request field")
    task = request.get("task")
    tool = TASK_TO_TOOL.get(task) if isinstance(task, str) else None
    if tool is None:
        return {"action": "ABSTAIN", "reason_code": "UNSUPPORTED_TASK", "version": VERSION}
    if selected_tool is not None and selected_tool != tool:
        return {"action": "ABSTAIN", "reason_code": "TOOL_MISMATCH", "tool": selected_tool, "version": VERSION}
    try:
        inputs, units = request.get("inputs"), request.get("units")
        if not isinstance(inputs, dict) or not isinstance(units, dict):
            raise ContractError("INVALID_INPUTS", ["inputs", "units"])
        missing = [k for k in REQUIRED[tool] if k not in inputs or inputs[k] is None]
        missing += ["units." + k for k in UNITS[tool] if k not in units or units[k] is None]
        if missing:
            raise ContractError("MISSING_INPUTS", missing)
        unknown = [k for k in inputs if k not in REQUIRED[tool]]
        unknown += ["units." + k for k in units if k not in UNITS[tool]]
        if unknown:
            raise ContractError("UNSUPPORTED_FIELDS", unknown)
        wrong_units = ["units." + k for k, v in UNITS[tool].items() if units[k] != v]
        if wrong_units:
            raise ContractError("EXPLICIT_CONVERSION_REQUIRED", wrong_units)
        value = _calculate(tool, inputs)
        if not math.isfinite(value):
            raise ContractError("INVALID_INPUTS", ["computed_result"])
        return {"action": "ANSWER", "numeric": value, "unit": OUTPUT_UNITS[tool], "tool": tool, "version": VERSION}
    except ContractError as exc:
        return {"action": "ASK_FOR_DATA", "reason_code": exc.reason, "requested_fields": exc.fields, "tool": tool, "version": VERSION}


def score_case(case: dict, output: dict) -> dict:
    """Reference score separates action, tool choice and numerical agreement.

    Intended for this development pack only, never for historical rescoring.
    """
    public_request(case)  # checks pack/split isolation and leakage guard
    expected = case["expected"]
    action_ok = output.get("action") == expected["action"]
    tool_ok = output.get("tool") == expected.get("tool")
    numeric_ok = False
    if expected["action"] == "ANSWER":
        try:
            value = _number(output.get("numeric"), "numeric")
            numeric_ok = (output.get("unit") == expected["unit"]
                          and abs(value - expected["numeric"]) <= expected["abs_tolerance"])
        except ContractError:
            numeric_ok = False
        complete = action_ok and tool_ok and numeric_ok
    else:
        complete = (action_ok and tool_ok and output.get("reason_code") == expected["reason_code"]
                    and "numeric" not in output)
        if expected["action"] == "ASK_FOR_DATA":
            fields = output.get("requested_fields")
            complete = complete and isinstance(fields, list) and all(isinstance(f, str) for f in fields)
            complete = complete and len(fields) == len(set(fields)) and set(fields) == set(expected["requested_fields"])
    return {"correct": bool(complete), "action_correct": action_ok, "tool_correct": tool_ok, "numeric_correct": numeric_ok}

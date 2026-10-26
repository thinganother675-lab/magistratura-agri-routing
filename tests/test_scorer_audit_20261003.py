# SPDX-License-Identifier: Apache-2.0
"""Independent equation checks and overlapping diagnostic failures."""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

source = Path(__file__).resolve().parents[1] / "scripts/audit_scorer_20261003.py"
spec = importlib.util.spec_from_file_location("scorer_audit_test", source)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize("tool,inputs,answer", [
    ("gdd", {"tmin": [0, 10], "tmax": [10, 20], "base": 5}, "10"),
    ("rain_deficit", {"rain": [2.5, 7.5], "target": 8}, "0"),
    ("rain_deficit", {"rain": [2.5, 7.5], "target": 12}, "2"),
    ("vpd", {"temperature": 0, "rh": 0}, ".6108"),
    ("vpd", {"temperature": 30, "rh": 100}, "0"),
])
def test_independent_decimal_reference_boundary_cases(tool, inputs, answer):
    assert audit.independent_numeric(tool, inputs) == Decimal(answer)


def test_diagnostics_record_multiple_failures_without_rescoring():
    out = {"action": "ANSWER", "answer": "9", "numeric": 9, "unit": "cm"}
    record = {"method": "local", "sample": {"id": "synthetic_test_fixture", "reference_tool": "rain_deficit", "inputs": {"rain": [2, 3], "target": 4}, "expected": {"action": "ANSWER", "numeric": 0, "unit": "mm"}},
              "result": {"output": out, "trace": [{"raw": {"final_content": json.dumps(out), "finish_reason": "length", "stream_done": False}}]}, "score": {"correct": False}}
    before = json.dumps(record, sort_keys=True)
    diagnosed = audit.numeric_diagnostic(record)
    assert set(diagnosed["failure_causes"]) == {"arithmetic_or_formula", "unit", "incomplete_response"}
    assert json.dumps(record, sort_keys=True) == before

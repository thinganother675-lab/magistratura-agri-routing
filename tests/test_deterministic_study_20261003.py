"""Study C: published external controls, contract boundaries and split isolation."""
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from agro_route.deterministic_study_20261003 import (
    VERSION, execute_request, public_request, score_case,
)

PACK = json.loads((Path(__file__).resolve().parents[1] / "data/study_c_technical_20261003.json").read_text(encoding="utf-8"))
CASES = PACK["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_independent_expected_answers_and_contract_decisions(case):
    result = execute_request(public_request(case))
    assert result["version"] == VERSION
    assert score_case(case, result)["correct"]


def test_external_fao_example18_not_self_generated_numeric_truth():
    case = CASES[10]
    assert case["gold_method"] == "published rounded worked example"
    assert case["expected"]["numeric"] == 3.88
    # FAO-56 ch.4 Example 18: published rounded intermediate inputs.
    assert execute_request(public_request(case))["numeric"] == pytest.approx(3.88, abs=.01)


def test_external_fao_example6_extrema_not_saturation_at_mean_temperature():
    case = CASES[8]
    assert case["expected"]["numeric"] == .91
    correct = execute_request(public_request(case))["numeric"]
    assert correct == pytest.approx(.91, abs=.005)
    # The single-temperature approximation must not replace the daily-extrema method.
    request = deepcopy(CASES[6]["request"])
    request["inputs"] = {"temperature":21.5, "rh":68}
    approximated = execute_request(request)["numeric"]
    assert abs(correct - approximated) > .09


def test_gdd_no_implicit_crop_clipping_and_no_period_average_before_zero_floor():
    assert execute_request(public_request(CASES[3]))["numeric"] == 35
    request = public_request(CASES[0])
    request["inputs"] = {"tmin":[0, 10], "tmax":[0, 10], "base":5}
    assert execute_request(request)["numeric"] == 5  # not zero from a window-average


def test_supplied_et0_parameters_need_no_invented_rh_latitude_or_crop_coefficient():
    result = execute_request(public_request(CASES[10]))
    assert result["action"] == "ANSWER"
    assert result["unit"] == "mm/day"
    assert "rh" not in CASES[10]["request"]["inputs"]


def test_et0_never_defaults_missing_soil_heat_flux_to_zero():
    request = public_request(CASES[10])
    del request["inputs"]["g"]
    result = execute_request(request)
    assert result["action"] == "ASK_FOR_DATA"
    assert result["requested_fields"] == ["g"]


@pytest.mark.parametrize("units_key,bad_unit", [
    ("temperature","F"), ("radiation","W/m2"), ("wind","km/h"),
    ("pressure","Pa"), ("slope","Pa/C"), ("height","cm"), ("time_step","hour"),
])
def test_every_et0_unit_is_explicitly_validated(units_key, bad_unit):
    request = public_request(CASES[10])
    request["units"][units_key] = bad_unit
    result = execute_request(request)
    assert result["action"] == "ASK_FOR_DATA"
    assert result["reason_code"] == "EXPLICIT_CONVERSION_REQUIRED"
    assert result["requested_fields"] == ["units." + units_key]


@pytest.mark.parametrize("case_index,field,value", [
    (0,"base",True), (0,"base",math.nan), (0,"tmin",[]),
    (0,"tmin",[1,2]), (0,"tmax",[0]), (0,"tmax",[math.inf]),
    (6,"rh",101), (6,"temperature",None), (8,"rhmin",90),
    (10,"ea",3), (10,"gamma",0), (10,"delta",0), (10,"u2",-1),
    (10,"wind_height",True), (10,"rn",10**1000), (12,"rain",[-1]),
])
def test_malformed_physical_inputs_never_answer(case_index, field, value):
    request = public_request(CASES[case_index])
    request["inputs"][field] = value
    result = execute_request(request)
    assert result["action"] == "ASK_FOR_DATA"
    assert "numeric" not in result


def test_signed_et0_result_is_not_silently_clipped_into_irrigation_advice():
    request = public_request(CASES[10])
    request["inputs"].update(rn=-5, g=0, u2=0, es=1, ea=1)
    assert execute_request(request)["numeric"] < 0


def test_finite_but_unphysical_rain_values_cannot_overflow_series_sum():
    request = public_request(CASES[12])
    request["inputs"]["rain"] = [1e308, 1e308]
    result = execute_request(request)
    assert result["action"] == "ASK_FOR_DATA"
    assert result["reason_code"] == "INVALID_INPUTS"
    assert result["requested_fields"] == ["rain"]
    assert "numeric" not in result


def test_unknown_raw_et0_measurements_do_not_trigger_implicit_reconstruction():
    request = public_request(CASES[10])
    request["inputs"]["solar_radiation"] = 22.07
    result = execute_request(request)
    assert result["reason_code"] == "UNSUPPORTED_FIELDS"


def test_wrong_explicit_tool_selection_abstains_and_is_not_corrected():
    case = CASES[26]
    result = execute_request(public_request(case), selected_tool="gdd_simple_daily_v1")
    assert result["action"] == "ABSTAIN"
    assert result["reason_code"] == "TOOL_MISMATCH"
    assert not score_case(case, result)["tool_correct"]
    assert not score_case(case, result)["correct"]


def test_private_expected_mutation_cannot_change_inference_request():
    case = deepcopy(CASES[0])
    initial = public_request(case)
    case["expected"]["numeric"] = 123456
    case["source"]["formula"] = "private provenance changed"
    assert public_request(case) == initial
    public_request(case)["inputs"]["base"] = 100
    assert case["request"]["inputs"]["base"] == 10


@pytest.mark.parametrize("key", ["gold", "expected", "expected_output", "reference_answer", "labels", "tolerance"])
def test_private_nested_fields_rejected(key):
    request = public_request(CASES[0])
    request["inputs"]["nested"] = {key:8}
    with pytest.raises(ValueError, match="Private evaluation"):
        execute_request(request)


@pytest.mark.parametrize("split,id_value", [
    ("test","study_c_001"), ("dev","study_c_001"),
    ("development_reference","home150_001"), ("development_reference","review40_001"),
])
def test_historical_and_confirmatory_splits_never_rescored(split, id_value):
    case = deepcopy(CASES[0])
    case.update(split=split,id=id_value)
    with pytest.raises(ValueError):
        public_request(case)
    with pytest.raises(ValueError):
        score_case(case,{"action":"ANSWER","numeric":8,"unit":"degC day"})


@pytest.mark.parametrize("override", [
    {"numeric":True}, {"numeric":math.nan}, {"numeric":math.inf},
    {"numeric":9}, {"numeric":10**1000}, {"unit":"mm"}, {"tool":"rain_target_gap_v1"},
])
def test_wrong_number_unit_or_tool_is_not_semantically_repaired(override):
    case = CASES[0]
    output = execute_request(public_request(case))
    output.update(override)
    assert not score_case(case,output)["correct"]


def test_missing_input_score_requires_precise_fields_and_no_numeric_answer():
    case = CASES[19]
    output = execute_request(public_request(case))
    output["requested_fields"] = ["ea"]
    assert not score_case(case,output)["correct"]
    output = execute_request(public_request(case))
    output["numeric"] = 0
    assert not score_case(case,output)["correct"]


def test_pack_is_explicitly_development_and_grouped_not_agronomic_gold():
    assert PACK["study"] == "C"
    assert PACK["status"] == "DEVELOPMENT_REFERENCE_ONLY_NOT_CONFIRMATORY"
    assert len(CASES) == len({c["id"] for c in CASES}) == 27
    assert len({c["group"] for c in CASES}) < len(CASES)
    assert all(c["source"]["formula_version"] and c["gold_method"] for c in CASES)

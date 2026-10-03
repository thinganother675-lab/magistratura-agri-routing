# SPDX-License-Identifier: Apache-2.0
import copy
import json

import pytest

from agro_route.scoring_v2_dev import parse_output_v2, public_request_v2, score_dev, verify_public_dev


def output(answer="ALERT", action="ANSWER", **fields):
    return {"action": action, "answer": answer, "numeric": None, "unit": None, **fields}


def rule_request():
    return {"input": "Apply both supplied criteria for field A.", "context": "ALERT and OK both occur here; this sentence is not evidence of either branch.",
            "inputs": {"verification": {"kind": "rule", "entity": "field_A", "branches": {"true": "ALERT", "false": "OK"},
                "facts": [{"id": "Aheat", "entity": "field_A", "field": "heat", "value": 21, "unit": "degC day"},
                          {"id": "Arain", "entity": "field_A", "field": "rain", "value": 12, "unit": "mm"}],
                "rule": {"all": [{"field": "heat", "op": ">", "value": 20, "unit": "degC day"},
                                  {"field": "rain", "op": "<", "value": 10, "unit": "mm"}]}}}}


def test_conjunction_wrong_branch_rejected_despite_lexical_overlap():
    r = rule_request()
    assert not verify_public_dev(r, output(evidence_ids=["Aheat", "Arain"]))["accepted"]
    assert verify_public_dev(r, output("OK", evidence_ids=["Aheat", "Arain"]))["accepted"]


def test_negation_is_evaluated_not_token_erased():
    r = rule_request()
    contract = r["inputs"]["verification"]
    contract["rule"] = {"not": contract["rule"]["all"][1]}
    assert verify_public_dev(r, output(evidence_ids=["Arain"]))["accepted"]
    assert not verify_public_dev(r, output("OK", evidence_ids=["Arain"]))["accepted"]


@pytest.mark.parametrize("operator,value,wanted", [("<", 12, "OK"), ("<=", 12, "ALERT"), (">", 12, "OK"), (">=", 12, "ALERT")])
def test_strict_branch_boundary(operator, value, wanted):
    r = rule_request()
    r["inputs"]["verification"]["rule"] = {"field": "rain", "op": operator, "value": value, "unit": "mm"}
    assert verify_public_dev(r, output(wanted, evidence_ids=["Arain"]))["accepted"]


def test_wrong_entity_cannot_supply_a_missing_fact():
    r = rule_request()
    r["inputs"]["verification"]["facts"][1]["entity"] = "field_B"
    outcome = verify_public_dev(r, output("OK", evidence_ids=["Aheat", "Arain"]))
    assert not outcome["accepted"] and outcome["status"] == "UNKNOWN"


def test_all_predicates_require_evidence_even_after_false_first_condition():
    r = rule_request()
    r["inputs"]["verification"]["facts"][0]["value"] = 0
    r["inputs"]["verification"]["facts"].pop()
    assert verify_public_dev(r, output("OK", evidence_ids=["Aheat"]))["status"] == "UNKNOWN"


def test_incomplete_compound_evidence_rejected():
    assert not verify_public_dev(rule_request(), output("OK", evidence_ids=["Aheat"]))["accepted"]


def test_unit_mismatch_cannot_trigger_rule():
    r = rule_request()
    r["inputs"]["verification"]["facts"][1]["unit"] = "cm"
    assert verify_public_dev(r, output("OK", evidence_ids=["Aheat", "Arain"]))["status"] == "UNKNOWN"


def test_text_substring_alone_is_insufficient():
    result = verify_public_dev({"input": "Which branch?", "context": "ALERT OK", "inputs": {}}, output("OK"))
    assert not result["accepted"] and result["status"] == "UNKNOWN"


def test_fact_requires_full_entity_and_negation_preserved():
    r = {"input": "What is true for B?", "inputs": {"verification": {"kind": "fact", "entity": "B", "field": "treatment",
        "facts": [{"id": "fact_A", "entity": "A", "field": "treatment", "text": "Apply irrigation"},
                  {"id": "fact_B", "entity": "B", "field": "treatment", "text": "Do not apply irrigation"}]}}}
    assert not verify_public_dev(r, output("Apply irrigation", evidence_ids=["fact_A"]))["accepted"]
    assert verify_public_dev(r, output("Do not apply irrigation", evidence_ids=["fact_B"]))["accepted"]


def test_public_projection_removes_hidden_gold_and_recursive_leak_rejected():
    sample = {**rule_request(), "id": "dev_001", "expected_v2": {"action": "ANSWER", "answers": ["OK"]}, "category": "compound", "split": "dev"}
    public = public_request_v2(sample)
    assert set(public) == {"input", "context", "inputs"}
    assert "expected_v2" not in json.dumps(public)
    public["inputs"]["verification"]["facts"][0]["gold"] = "OK"
    with pytest.raises(ValueError, match="Private"):
        verify_public_dev(public, output("OK"))
    assert "gold" not in sample["inputs"]["verification"]["facts"][0]
    with pytest.raises(ValueError, match="projection"):
        verify_public_dev(sample, output("OK"))


@pytest.mark.parametrize("identifier,split", [("home_final_20261001_001", "dev"), ("review20261002_weather_01_en", "dev"), ("fresh", "test"), ("fresh", "home_final")])
def test_historical_or_final_scoring_prohibited(identifier, split):
    with pytest.raises(ValueError, match="DEV only"):
        score_dev({"id": identifier, "split": split, "expected_v2": {"action": "ANSWER", "answers": ["OK"]}}, output("OK"))


@pytest.mark.parametrize("text", ['{"action":"ANSWER","action":"ABSTAIN"}', '{"action":"ANSWER","answer":"x","numeric":NaN,"unit":"mm"}', '```json\n{}\n```', '{"action":[],"answer":"x","numeric":null,"unit":null}', '{"action":"ANSWER","answer":"x","numeric":true,"unit":"mm"}'])
def test_schema_and_parser_fail_closed(text):
    with pytest.raises(ValueError):
        parse_output_v2(text)


def test_complete_compound_score_requires_every_component():
    sample = {"id": "new_dev", "split": "dev", "expected_v2": {"action": "ANSWER", "answers": ["OK"], "components": {"heat": {"numeric": 21, "unit": "degC day"}, "rain": {"numeric": 12, "unit": "mm"}}}}
    incomplete = output("OK", components={"heat": {"answer": "21", "numeric": 21, "unit": "degC day"}})
    assert not score_dev(sample, incomplete)["correct"]
    full = copy.deepcopy(incomplete)
    full["components"]["rain"] = {"answer": "12", "numeric": 12, "unit": "mm"}
    assert score_dev(sample, full)["correct"]


def test_numeric_units_and_display_consistency():
    sample = {"id": "new_dev", "split": "dev", "expected_v2": {"action": "ANSWER", "numeric": 2, "unit": "mm"}}
    assert score_dev(sample, output("2 мм", numeric=2, unit="мм"))["correct"]
    assert not score_dev(sample, output("2 cm", numeric=2, unit="cm"))["correct"]
    assert not score_dev(sample, output("20 mm", numeric=2, unit="mm"))["correct"]
    assert not score_dev(sample, output("2 kPa", numeric=2, unit="mm"))["correct"]


def test_ask_requires_correct_missing_inputs_and_no_fabrication():
    request = {"input": "Calculate VPD; RH missing", "inputs": {"measurements": {"temperature": 20}, "verification": {"kind": "calculation", "required_fields": ["temperature", "rh"]}}}
    sample = {"id": "new_dev_ask", "split": "dev", "expected_v2": {"action": "ASK_FOR_DATA", "required_fields": ["rh"]}}
    good = output("Relative humidity is needed", "ASK_FOR_DATA", requested_fields=["rh"], reason_code="MISSING_INPUTS")
    assert verify_public_dev(request, good)["accepted"]
    assert score_dev(sample, good)["correct"]
    assert not score_dev(sample, {**good, "numeric": 1.2})["correct"]
    assert not verify_public_dev(request, {**good, "requested_fields": ["crop"]})["accepted"]
    assert not verify_public_dev(request, output("1.2", numeric=1.2, unit="kPa"))["accepted"]


def test_abstain_insufficient_reference_not_arbitrary_refusal():
    request = {"input": "Only the supplied facts may support the confirmed pathogen identity", "inputs": {"verification": {"kind": "fact", "entity": "field_A", "field": "confirmed_pathogen_species", "scope": "closed_world_supplied_facts", "facts": []}}}
    sample = {"id": "new_dev_abstain", "split": "dev", "expected_v2": {"action": "ABSTAIN", "reason_code": "INSUFFICIENT_REFERENCE", "answers": ["Cannot confirm a pathogen from weather"]}}
    good = output("Cannot confirm a pathogen from weather", "ABSTAIN", reason_code="INSUFFICIENT_REFERENCE")
    assert score_dev(sample, good)["correct"] and verify_public_dev(request, good)["accepted"]
    assert not verify_public_dev(request, output("Fusarium"))["accepted"]
    assert not score_dev(sample, {**good, "answer": "Fusarium is confirmed"})["correct"]


def test_ask_reference_can_reject_a_contradictory_explanation():
    sample = {"id": "new_dev_ask_text", "split": "dev", "expected_v2": {"action": "ASK_FOR_DATA", "required_fields": ["rh"], "answers": ["Relative humidity is required"]}}
    result = output("Relative humidity is required", "ASK_FOR_DATA", requested_fields=["rh"], reason_code="MISSING_INPUTS")
    assert score_dev(sample, result)["correct"]
    assert not score_dev(sample, {**result, "answer": "Relative humidity is not required"})["correct"]


def test_changing_hidden_gold_never_changes_router_payload():
    base = {**rule_request(), "expected_v2": {"action": "ANSWER", "answers": ["ALERT"]}, "category": "compound", "split": "dev"}
    changed = copy.deepcopy(base)
    changed["expected_v2"] = {"action": "ABSTAIN", "reason_code": "INSUFFICIENT_REFERENCE"}
    changed["category"] = "insufficient_data"
    assert public_request_v2(base) == public_request_v2(changed)


@pytest.mark.parametrize("alias", ["expected_answer", "ExpectedAction", "gold_answer", "reference_gold", "provisional_gold", "correct_answer", "answer_key"])
def test_recursive_expected_aliases_cannot_enter_router_payload(alias):
    sample = rule_request()
    sample["inputs"]["verification"]["facts"][0][alias] = "oracle"
    with pytest.raises(ValueError, match="Private"):
        public_request_v2(sample)


def test_gold_derived_unsupported_marker_is_not_a_verification_oracle():
    request = {"input": "Natural QA without typed facts", "inputs": {"verification": {"kind": "unsupported"}}}
    outcome = verify_public_dev(request, output("I cannot answer", "ABSTAIN", reason_code="INSUFFICIENT_REFERENCE"))
    assert not outcome["accepted"] and outcome["status"] == "UNKNOWN"


def test_public_calculation_uses_measurements_without_gold():
    request = {"input": "Calculate GDD", "inputs": {"measurements": {"tmin": [0, 6], "tmax": [10, 14], "base": 5, "temperature_unit": "C"},
                "verification": {"kind": "calculation", "tool": "gdd", "required_fields": ["tmin", "tmax", "base", "temperature_unit"]}}}
    assert verify_public_dev(request, output("5 degC day", numeric=5, unit="degC day"))["accepted"]
    assert not verify_public_dev(request, output("15 degC day", numeric=15, unit="degC day"))["accepted"]

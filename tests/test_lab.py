import json
from pathlib import Path
from unittest.mock import patch
import httpx
import pytest
from agro_route.tools import execute, InputError
from agro_route.models import Model, parse_output, public_request
from agro_route.routing import decide, hard_gate, grounded
from agro_route.evaluation import score

def test_gdd_clipping_known_values():
    result = execute("gdd", {"tmin": [-2,10], "tmax": [4,20], "base":10,"temperature_unit":"C"})
    assert result["numeric"] == 5

def test_vpd_known_saturation_and_half_humidity():
    assert execute("vpd", {"temperature":25,"rh":100,"temperature_unit":"C"})["numeric"] == 0
    assert execute("vpd", {"temperature":25,"rh":50,"temperature_unit":"C"})["numeric"] == pytest.approx(1.58388885875)

def test_et0_radiative_only_analytic_limit():
    args={"temperature":20,"rn":10,"g":0,"u2":0,"es":2.4,"ea":2.4,"delta":.2,"gamma":.066,"temperature_unit":"C"}
    assert execute("et0",args)["numeric"] == pytest.approx(3.0676691729323307)

@pytest.mark.parametrize("data", [{"temperature":25,"rh":101,"temperature_unit":"C"},{"temperature":25,"rh":-1,"temperature_unit":"C"},{"temperature":float('nan'),"rh":50,"temperature_unit":"C"},{"temperature":25,"rh":True,"temperature_unit":"C"},{"temperature":77,"rh":50,"temperature_unit":"F"}])
def test_bad_inputs_rejected(data):
    with pytest.raises(InputError): execute("vpd",data)

def test_missing_radiation_clarifies():
    r=hard_gate({"input":"Посчитай ET0.","inputs":{"temperature":20,"temperature_unit":"C"}})
    assert r["route"] == "ASK_FOR_DATA"
    assert r["tool_calls"] == 0

def test_definition_does_not_execute():
    assert hard_gate({"input":"Что такое ET0?","inputs":{}}) is None

def test_negated_execution_does_not_execute():
    assert hard_gate({"input":"Только выбери gdd; не рассчитывай.","inputs":{}}) is None

def test_rain_deficit_is_not_irrigation():
    assert execute("rain_deficit",{"rain":[10,20],"target":25,"precipitation_unit":"mm"})["numeric"] == 0

def test_gold_fields_never_reach_model_or_policy():
    sample={"input":"Question", "context":"context", "inputs":{},"expected":{"answer":"secret"},"category":"cloud","split":"test"}
    assert set(public_request(sample)) == {"input","context","inputs"}

def test_network_failure_abstains():
    def call(_): return {"output":None,"error":{"type":"Timeout"},"latency_ms":10,"cost_usd":None}
    r=decide({"input":"Interpret conditions","inputs":{}},"cascade",call,call)
    assert r["route"] == "ABSTAIN" and r["cloud_calls"] == 1

def test_offline_never_calls_cloud():
    def local(_): return {"output":{"action":"ANSWER","answer":"invented"},"latency_ms":1,"cost_usd":0}
    def cloud(_): raise AssertionError("Cloud must not run")
    r=decide({"input":"What is the risk?","context":""},"offline",local,cloud,False)
    assert r["route"] == "ABSTAIN"

def test_support_checker_can_accept_wrong_substring():
    # Document the verifier's limitation; no gold-informed escalation.
    assert grounded({"context":"wheat and potato"},{"output":{"action":"ANSWER","answer":"potato"}})

@pytest.mark.parametrize("text",['{"action":"ANSWER"}', '{"action":"EXECUTE","answer":"x"}', 'oops', '{"action":"ANSWER","answer":"x","numeric":NaN}'])
def test_malformed_model_output(text):
    with pytest.raises(ValueError): parse_output(text)

def test_http_timeout_is_persisted_without_secret():
    with patch("httpx.Client.post",side_effect=httpx.ReadTimeout("sensitive endpoint")):
        r=Model("https://example.invalid/v1","fake",key="invalid-test-only").call({"input":"test"})
    assert r["error"]["type"]=="ReadTimeout" and "sensitive" not in json.dumps(r)

def test_disjoint_groups_and_ids():
    root=Path(__file__).resolve().parents[1]
    data=[json.loads(l) for l in (root/"data/benchmark.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len({s["id"] for s in data})==len(data)
    groups={split:{s["group"] for s in data if s["split"]==split} for split in ['train','dev','test']}
    assert not groups['train']&groups['dev'] and not groups['train']&groups['test'] and not groups['dev']&groups['test']

def test_numeric_unit_mismatch_fails():
    s={"expected":{"action":"ANSWER","numeric":10,"unit":"mm"},"scoring":"numeric_tolerance","category":"numeric"}
    assert not score(s,{"action":"ANSWER","numeric":10,"unit":"inches"})["correct"]

def test_absent_answer_is_incorrect_but_not_false_numerical_advice():
    s={"expected":{"action":"ANSWER","numeric":10,"unit":"mm"},"scoring":"numeric_tolerance","category":"numeric"}
    assert score(s,None)=={"correct":False,"qa_f1":None,"critical_error":False,"numeric_error":None}
    assert score(s,{"action":"ANSWER","numeric":9,"unit":"mm"})['critical_error']

import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from agro_route.prerouting import public_state, decide_pre, rule_route, ambiguity_flags, SharedBudget, BeforeRequestBlocked

def forbidden(_): raise AssertionError('Unexpected generator request')
def sample(question='Which soil?', context='loam', inputs=None):
    return {'input':question,'context':context,'inputs':inputs or {},'gold':{'answer':'SECRET_GOLD'},'category':'SECRET_LABEL'}

def test_gold_and_nested_label_allowlist():
    s=sample(inputs={'temperature':25,'gold_route':'SECRET_ROUTE'})
    state=public_state(s)
    assert 'SECRET' not in json.dumps(state)
    assert state['numeric_inputs']=={'temperature':25}
    with pytest.raises(ValueError): public_state(sample(inputs={'temperature':{'gold':42}}))
    with pytest.raises(ValueError): public_state(sample(inputs={'daily_min':[{'gold':42}]}))

def test_public_scenario_measurements_are_preserved_without_category_labels():
    inputs={'daily_min':[5,8],'daily_max':[20,22],'daily_rain':[1,0],
            'base_c':5,'heat_threshold':20,'rain_target_mm':10,
            'minimum_temperature':4,'scenario_threshold':3}
    assert public_state(sample(inputs=inputs))['numeric_inputs']==inputs

def test_offline_insufficient_evidence_cannot_generate_an_unsupported_answer():
    r=decide_pre(sample(context=''),rule_route,forbidden,forbidden,cloud_available=False)
    assert r['route']=='ABSTAIN' and r['local_calls']==r['total_external_requests']==0

def test_hosted_router_is_counted_even_for_local_answer():
    r=decide_pre(sample(),lambda *_:{'route':'LOCAL','router_external_calls':1,'cost_usd':.001},
                 lambda _:{'output':{'action':'ANSWER','answer':'loam'},'cost_usd':0},forbidden,hosted_router=True)
    assert r['local_calls']==1 and r['cloud_calls']==0
    assert r['total_external_requests']==r['router_external_calls']==1
    assert r['cost_usd']==.001

def test_offline_bypasses_hosted_router_and_cloud():
    def bad_selector(*_): raise AssertionError('Hosted router leaked offline')
    r=decide_pre(sample(context=''),bad_selector,forbidden,forbidden,cloud_available=False,hosted_router=True)
    assert r['route']=='ABSTAIN' and r['total_external_requests']==0

def test_deterministic_gate_after_router_and_no_llm():
    events=[]
    def selector(*_): events.append('router');return {'route':'CLOUD','router_external_calls':1,'cost_usd':0}
    r=decide_pre(sample('Calculate GDD.','',{'tmin':12,'tmax':24,'base':10,'temperature_unit':'C'}),selector,forbidden,forbidden)
    assert events==['router'] and r['output']['numeric']==8
    assert r['tool_calls']==1 and r['local_calls']==r['cloud_calls']==0
    assert r['guard_override']=='shared_deterministic_input_gate'

@pytest.mark.parametrize('inputs',[{}, {'temperature':25,'rh':60,'temperature_unit':'F'}, {'temperature':25,'rh':101,'temperature_unit':'C'}])
def test_invalid_units_or_missing_inputs_never_reach_generator(inputs):
    r=decide_pre(sample('Calculate VPD.','',inputs),rule_route,forbidden,forbidden)
    assert r['route']=='ASK_FOR_DATA'

@pytest.mark.parametrize('context',[
    'Wheat: 3 tonnes. Maize: 7 tonnes.',
    'Alert only if rain is low AND temperature is high.',
    'This soil is not saline.',
    'The sources conflict about the value.' ])
def test_adversarial_public_cues_force_cloud_before_local(context):
    assert ambiguity_flags(sample(context=context))
    calls=[]
    r=decide_pre(sample(context=context),lambda *_:{'route':'LOCAL','cost_usd':0},forbidden,
                 lambda _:(calls.append('cloud') or {'output':{'action':'ABSTAIN','answer':'Unclear'},'cost_usd':0}))
    assert calls==['cloud'] and r['local_calls']==0
    assert r['guard_override']=='shared_prerouting_ambiguity_guard'

def test_router_failure_falls_back_without_retry():
    n=[]
    def bad(*_): n.append(1);return {'route':None,'error':{'type':'HTTP429'},'router_external_calls':1,'cost_usd':None}
    r=decide_pre(sample(context=''),bad,forbidden,lambda _:{'output':{'action':'ABSTAIN','answer':'No evidence'},'cost_usd':0},hosted_router=True)
    assert len(n)==1 and r['total_external_requests']==2
    assert r['unknown_cost_events']==1 and r['cost_usd'] is None

def test_shared_budget_does_not_reset_and_unknown_keeps_reservation(tmp_path):
    path=tmp_path/'budget.sqlite3'
    a=SharedBudget(path,.01);identifier=a.reserve('jev',.008);a.finish(identifier,None)
    b=SharedBudget(path,.01)
    with pytest.raises(RuntimeError): b.reserve('mercury',.003)
    assert b.snapshot()['reserved_unknown_usd']==.008
    with pytest.raises(ValueError): SharedBudget(path,.02)

def test_shared_budget_is_atomic_between_workers(tmp_path):
    path=tmp_path/'budget.sqlite3';SharedBudget(path,.01)
    def reserve(_):
        try: return SharedBudget(path,.01).reserve('jev',.006)
        except RuntimeError: return None
    with ThreadPoolExecutor(max_workers=2) as ex: values=list(ex.map(reserve,range(2)))
    assert sum(v is not None for v in values)==1

def test_blocked_before_dispatch_is_not_a_remote_call_or_unknown_charge():
    def blocked(_):raise BeforeRequestBlocked('cloud','budget_guard')
    r=decide_pre(sample(context=''),rule_route,forbidden,blocked)
    assert r['route']=='ABSTAIN' and r['cloud_calls']==r['total_external_requests']==0
    assert r['unknown_cost_events']==0 and r['cost_usd']==0
    assert r['trace'][0]['attempted'] is False

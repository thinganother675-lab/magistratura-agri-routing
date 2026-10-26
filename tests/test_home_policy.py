from agro_route.home_policy import offline, escalation_plan

def forbidden(_):
    raise AssertionError('A local call cannot help without verifier context')

def test_no_context_offline_skips_unresolvable_local_attempt():
    r=offline({'input':'Apply the supplied rule','context':'','inputs':{}},forbidden)
    assert r['route']=='ABSTAIN' and r['local_calls']==r['cloud_calls']==0

def test_deterministic_gate_resolves_before_any_model():
    r=offline({'input':'Calculate GDD','inputs':{'tmin':[10],'tmax':[20],'base':10,'temperature_unit':'C'}},forbidden)
    assert r['output']['numeric']==5 and r['route']=='DETERMINISTIC_TOOL'

def test_context_acceptance_and_error_rejection():
    q={'input':'What crop?','context':'wheat is mentioned','inputs':{}}
    result={'output':{'action':'ANSWER','answer':'wheat'},'error':None}
    assert offline(q,lambda _:result)['route']=='LOCAL_MODEL'
    assert escalation_plan(q,result)['cloud_calls_planned']==0
    result['error']={'type':'CLIError'}
    assert offline(q,lambda _:result)['route']=='ABSTAIN'
    assert escalation_plan(q,result)['cloud_calls_planned']==1

def test_plan_does_not_invent_cloud_correctness_or_output():
    r=escalation_plan({'input':'Assess supplied rule','context':'','inputs':{}},{'output':None})
    assert r['cloud_calls_planned']==1 and 'output' not in r and 'correct' not in r

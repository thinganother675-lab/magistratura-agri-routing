import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('prerouting_analysis',Path(__file__).parents[1]/'scripts/analyze_prerouting_dev.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)

def test_missing_cloud_usage_and_cost_remain_unknown_in_operational_denominator():
    row={'sample':{'category':'extractive_qa','language':'en','expected':{'action':'ANSWER'}},
         'score':{'correct':False},'result':{'status':'MEASURED','route':'CLOUD_MODEL','output':None,
         'trace':[{'provider':'cloud','cost_usd':None,'error':{'type':'ReadTimeout'},'usage':{}}],
         'cloud_calls':1,'latency_ms':60000,'cost_usd':None,'error':{'type':'ReadTimeout'}}}
    s=analysis.summarize([row],2)
    assert s['quality_intended']==0 and s['missing_n']==1
    assert s['unknown_cost_events']==1 and s['cost_complete'] is False
    assert s['cloud_tokens']['prompt_tokens']['coverage']==0
    assert s['cloud_provider_failure_rate']==1 and s['latency_s']['p95']==60

def test_no_gold_abstention_cannot_be_reported_as_correct_abstention_accuracy():
    row={'sample':{'category':'compound_reasoning','language':'ru','expected':{'action':'ANSWER'}},
         'score':{'correct':False},'result':{'status':'MEASURED','route':'ABSTAIN',
         'output':{'action':'ABSTAIN'},'trace':[],'cost_usd':0,'latency_ms':1}}
    assert analysis.summarize([row],1)['correct_abstention']=='NOT_IDENTIFIABLE'

def test_hosted_router_usage_and_fee_count_when_generator_is_local():
    row={'sample':{'category':'extractive_qa','language':'en','expected':{'action':'ANSWER'}},
         'score':{'correct':True},'result':{'status':'MEASURED','route':'LOCAL_MODEL','output':{'action':'ANSWER'},
         'local_calls':1,'cloud_calls':0,'router_external_calls':1,'total_external_requests':1,
         'router_trace':{'router_external_calls':1,'raw':{'usage':{'input_tokens':500,'output_tokens':90}}},
         'trace':[{'provider':'local','cost_usd':0,'usage':{'prompt_tokens':400,'completion_tokens':20}}],
         'cost_usd':.000021,'known_remote_cost_usd':.000021,'unknown_cost_events':0,'latency_ms':1500}}
    s=analysis.summarize([row],1)
    assert s['generative_cloud_calls']==0 and s['total_external_requests']==s['hosted_router_calls']==1
    assert s['hosted_router_tokens']['input_tokens']['known_total']==500
    assert s['known_cost_per_success_usd']==.000021

def test_operational_latency_treats_pre_dispatch_blocking_identically_across_statuses():
    def row(status,latency):return {'sample':{'category':'numeric','language':'en','expected':{'action':'ANSWER'}},
        'score':{'correct':False},'result':{'status':status,'route':'NOT_RUN' if status=='NOT_RUN' else 'ABSTAIN',
        'output':None,'trace':[],'blocked_reason':{'provider':'cloud'},'cost_usd':0,'latency_ms':latency}}
    s=analysis.summarize([row('NOT_RUN',2000),row('MEASURED',1000)],2)
    assert s['latency_s']['n']==2 and s['latency_s']['mean']==1.5
    assert s['blocked_before_dispatch_decisions']==2

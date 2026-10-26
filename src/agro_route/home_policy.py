"""Development policy v2; the September frozen policy remains unchanged.

The original verifier can only accept answers supported by context. Therefore a
local attempt without any context can never resolve an escalation. Skip those
attempts, preserving the same deterministic gate and substring verifier.
"""
import time
from .routing import hard_gate, grounded


def offline(request, local):
    start=time.perf_counter()
    gate=hard_gate(request)
    if gate:
        return {**gate,'cloud_calls':0,'local_calls':0,'trace':[],
                'latency_ms':(time.perf_counter()-start)*1000,'latency_kind':'measured_tool'}
    if request.get('context','').strip():
        result=local(request)
        if not result.get('error') and grounded(request,result):
            return {'route':'LOCAL_MODEL','output':result['output'],'local_calls':1,'cloud_calls':0,
                    'tool_calls':0,'trace':[result],'latency_ms':(time.perf_counter()-start)*1000,
                    'latency_kind':'measured_live'}
        traces=[result]
    else:
        traces=[]
    return {'route':'ABSTAIN','output':{'action':'ABSTAIN','answer':'Нет проверяемой локальной опоры; облако недоступно','numeric':None},
            'local_calls':len(traces),'cloud_calls':0,'tool_calls':0,'trace':traces,
            'latency_ms':(time.perf_counter()-start)*1000,'latency_kind':'measured_live'}


def escalation_plan(request, local_result):
    """Routing decision only. This neither calls cloud nor scores a cloud answer."""
    gate=hard_gate(request)
    if gate:
        return {'route':gate['route'],'local_calls_planned':0,'cloud_calls_planned':0,'tool_calls':gate['tool_calls']}
    if request.get('context','').strip() and not local_result.get('error') and grounded(request,local_result):
        return {'route':'LOCAL_MODEL','local_calls_planned':1,'cloud_calls_planned':0,'tool_calls':0}
    return {'route':'LOCAL_TO_CLOUD' if request.get('context','').strip() else 'CLOUD_MODEL',
            'local_calls_planned':int(bool(request.get('context','').strip())),'cloud_calls_planned':1,'tool_calls':0}

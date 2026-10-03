"""Behavior checks for public argument isolation and blocked-I/O cancellation."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/study_c_live_20261004.py'
spec = importlib.util.spec_from_file_location('study_c_live_20261004', PATH)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def request():
    return {'task':'heat_sum_simple_daily','question_ru':'synthetic',
            'inputs':{'tmin':[10],'tmax':[26],'base':10},
            'units':{'temperature':'C','time_step':'day'}}


def selection(req):
    return {'action':'CALL_TOOL','tool':'gdd_simple_daily_v1',
            'arguments':{key:req[key] for key in ('inputs','units')}}


def test_actual_execution_uses_only_model_arguments():
    req=request(); result=live.dispatch(req,selection(req))
    assert result['executed_numeric']
    assert result['tool_result']['numeric']==8


def test_model_missing_argument_is_never_filled_from_public_or_gold():
    req=request(); chosen=json.loads(json.dumps(selection(req)))
    del chosen['arguments']['inputs']['base']
    with pytest.raises(ValueError,match='PublicArgumentsChanged'):
        live.dispatch(req,chosen)


def test_missing_public_data_and_wrong_units_remain_missing_and_wrong():
    req=request();del req['inputs']['base']
    result=live.dispatch(req,selection(req))
    assert not result['executed_numeric']
    assert result['tool_result']['reason_code']=='MISSING_INPUTS'
    assert result['tool_result']['requested_fields']==['base']
    req=request();req['units']['temperature']='F'
    result=live.dispatch(req,selection(req))
    assert result['tool_result']['reason_code']=='EXPLICIT_CONVERSION_REQUIRED'
    assert result['tool_result']['requested_fields']==['units.temperature']


@pytest.mark.parametrize('change',['changed','extra','bool','unknown_tool','wrong_tool','gold'])
def test_public_argument_and_allowlist_guards(change):
    req=request();chosen=json.loads(json.dumps(selection(req)))
    if change=='changed': chosen['arguments']['inputs']['base']=11
    if change=='extra': chosen['arguments']['inputs']['hidden']=1
    if change=='bool': chosen['arguments']['inputs']['base']=True
    if change=='unknown_tool': chosen['tool']='shell'
    if change=='wrong_tool': chosen['tool']='rain_target_gap_v1'
    if change=='gold': chosen['arguments']['gold']=8
    if change=='wrong_tool':
        assert live.dispatch(req,chosen)['tool_result']['reason_code']=='TOOL_MISMATCH'
    else:
        with pytest.raises(ValueError): live.dispatch(req,chosen)


@pytest.mark.parametrize('text',['{"action":"CALL_TOOL","action":"ANSWER"}',
    '{"numeric":NaN}', '{"gold":2}', '[]'])
def test_strict_selection_parser(text):
    with pytest.raises(ValueError): live.strict_json(text)


def test_blocked_io_is_cancelled_before_any_data_arrives():
    async def scenario():
        cancelled=asyncio.Event()
        async def never_returns():
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        samples=iter([{'system_ram_available_gib':5,'gpu_memory_free_mib':2000},
                      {'system_ram_available_gib':1,'gpu_memory_free_mib':2000}])
        result=await live.guarded(never_returns,deadline_s=10,sample=lambda:next(samples),interval=.005)
        assert result['error']=='RESOURCE_GUARD'
        assert result['latency_s']<1
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_blocked_io_has_independent_wall_deadline():
    async def scenario():
        async def blocked(): await asyncio.Event().wait()
        result=await live.guarded(blocked,deadline_s=.025,
            sample=lambda:{'system_ram_available_gib':5,'gpu_memory_free_mib':2000},interval=.005)
        assert result['error']=='WALL_DEADLINE'
        assert result['latency_s']<1
    asyncio.run(scenario())


def test_monitor_failure_fails_closed():
    async def scenario():
        async def blocked(): await asyncio.Event().wait()
        def failure(): raise OSError('SyntheticObservationFailure')
        result=await live.guarded(blocked,deadline_s=10,sample=failure)
        assert result['error']=='RESOURCE_OBSERVATION_FAILED'
    asyncio.run(scenario())


def test_all_existing_cases_remain_public_and_reference_separate():
    cases=json.loads(live.old.STUDY.read_text(encoding='utf-8'))['cases']
    assert len(cases)==27
    for case in cases:
        req=live.public_request(case)
        assert 'expected' not in req and 'gold' not in req
        tool=live.TASK_TO_TOOL.get(req.get('task'))
        if tool:
            chosen={'action':'CALL_TOOL','tool':tool,'arguments':{key:req[key] for key in ('inputs','units')}}
            assert live.dispatch(req,chosen)['tool_result']==live.execute_request(req)


def test_missing_end_token_count_never_crashes_failure_trace(monkeypatch):
    original_guarded=live.guarded
    async def safe_guard(operation, **kwargs):
        return await original_guarded(operation, sample=lambda:{
            'system_ram_available_gib':5,'gpu_memory_free_mib':2000}, **kwargs)
    monkeypatch.setattr(live,'guarded',safe_guard)
    async def scenario():
        transport=live.httpx.MockTransport(lambda req:live.httpx.Response(
            200,text='data: {"type":"chat.start"}\n\n'))
        async with live.httpx.AsyncClient(transport=transport) as client:
            record=await live.call(client,'mock','system','prompt','')
        assert record['error']=='MissingChatEnd'
        assert record['stats']['total_output_tokens'] is None
    asyncio.run(scenario())


def test_output_budget_guard_handles_none_and_invalid_stats():
    for value in (None, {}, {'total_output_tokens':None}, {'total_output_tokens':True},
                  {'total_output_tokens':float('nan')}):
        assert not live.output_budget_reached(value)
    assert live.output_budget_reached({'total_output_tokens':512})


def test_load_failure_before_warmup_has_zero_journal_calls(tmp_path):
    path=tmp_path/'calls.jsonl'
    assert live.journal_call_count(path)==0
    path.write_text('{}\n{}\n',encoding='utf-8')
    assert live.journal_call_count(path)==2

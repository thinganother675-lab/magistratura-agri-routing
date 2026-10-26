import json
import math
import pytest
from agro_route.lm_telemetry_20261003 import (native_payload, parse_native_sse, normalized_stats,
    safe_record, redact, summarize_resources, number_or_none, parse_json_presentation, ResourceSampler)
from agro_route.study_c_run_20261003 import score_text


def event(kind, **kwargs):
    return 'data: ' + json.dumps({'type':kind, **kwargs})


def test_native_stream_records_real_client_spans_and_backend_separately():
    lines = [event('chat.start'),event('prompt_processing.start'),event('prompt_processing.end'),
             event('message.delta',content='{"a":'),event('message.delta',content='1}'),
             event('chat.end',result={'output':[{'type':'message','content':'{"a":1}'}],
                 'stats':{'input_tokens':100,'total_output_tokens':5,'tokens_per_second':10,'time_to_first_token_seconds':.15}})]
    clocks = iter([10.01,10.03,10.13,10.2,10.3,10.32])
    result = parse_native_sse(lines,10,clock=lambda:next(clocks))
    assert result['stream_complete'] and result['error'] is None
    assert result['timing']['client_ttft_answer_s'] == pytest.approx(.2)
    assert result['timing']['client_generation_span_s'] == pytest.approx(.1)
    assert result['timing']['client_prompt_token_equivalent_tps'] == pytest.approx(1000)
    assert result['stats']['time_to_first_token_seconds'] == .15
    assert result['stats']['tokens_per_second'] == 10


@pytest.mark.parametrize('value',[None,True,-1,float('nan'),float('inf'),'3'])
def test_invalid_backend_units_not_fabricated(value):
    assert normalized_stats({'tokens_per_second':value})['tokens_per_second'] is None


def test_missing_end_and_malformed_stream_are_failures():
    assert parse_native_sse([event('message.delta',content='x')],0,clock=lambda:1)['error']=='MissingChatEnd'
    assert parse_native_sse(['data: bad'],0,clock=lambda:1)['error']=='MalformedSSE'


def test_tool_events_or_aggregated_tool_output_rejected():
    result = parse_native_sse([event('tool_call.start',tool='web'),event('chat.end',result={'output':[]})],0,clock=lambda:1)
    assert result['error']=='UnexpectedToolCall'
    result = parse_native_sse([event('chat.end',result={'output':[{'type':'tool_call','tool':'web'}]})],0,clock=lambda:1)
    assert result['error']=='UnexpectedToolCall'


def test_monotonic_time_required():
    clocks = iter([1,.5])
    with pytest.raises(ValueError,match='Nonmonotonic'):
        parse_native_sse([event('chat.start'),event('message.start')],0,clock=lambda:next(clocks))


def test_native_request_no_tools_storage_or_history():
    body = native_payload('own','system','supplied')
    assert body['integrations']==[] and body['store'] is False
    assert 'previous_response_id' not in body and 'seed' not in body
    assert body['reasoning']=='off' and body['context_length']==2048


def test_safe_projection_and_secret_redaction():
    record={'request':{'headers':{'Authorization':'secret_value'},'input':'benchmark content'},
            'response_text':'benchmark text','events':[{'content':'benchmark text'}],
            'task_id':'dev_id','latency_s':1,'error':None}
    safe=safe_record(record)
    assert 'benchmark' not in json.dumps(safe) and 'secret_value' not in json.dumps(safe)
    assert redact({'nested':['secret_value reflected']},'secret_value')=={'nested':['[REDACTED] reflected']}


def test_resource_values_keep_whole_scope_and_no_energy():
    summary=summarize_resources([{'gpu_memory_used_mib':1024,'system_ram_used_gib':2},{'gpu_memory_used_mib':2048,'system_ram_used_gib':3}])
    assert summary['gpu_memory_used_mib_peak_sampled']==2048
    assert summary['system_ram_used_gib_peak_sampled']==3
    assert 'NOT per-model' in summary['scope'] and summary['energy_j'] is None
    assert number_or_none('[N/A]') is None


def test_resource_guard_missing_measurement_stops():
    sampler=ResourceSampler(sample=lambda: {'system_ram_available_gib':1,'gpu_memory_free_mib':1000})
    sampler.sample()
    assert sampler.tripped.is_set()


def test_parse_only_presentation_no_semantic_repair():
    assert parse_json_presentation('```json\n{"choices":["A"]}\n```')=={'choices':['A']}
    with pytest.raises(ValueError):parse_json_presentation('Answer: {"choices":["A"]}')


def test_study_c_separates_tool_choice_arithmetic_and_rounding():
    case={'id':'study_c_x','split':'development_reference','request':{'task':'experimental_rain_target_gap','inputs':{'target':2,'rain':[1]},'units':{'precipitation':'mm'}},
          'expected':{'action':'ANSWER','tool':'rain_target_gap_v1','numeric':1,'unit':'mm','abs_tolerance':1e-8},'category':'numeric','group':'rain_target_gap_v1'}
    score=score_text(case,'{"action":"ANSWER","tool":"rain_target_gap_v1","numeric":1.00001,"unit":"mm"}')
    assert score['tool_correct'] and not score['numeric_correct'] and not score['correct']
    assert score['numeric_rounding_1e4_correct'] and score['declared_selection_tool_replay_correct']
    assert 'SIMULATED' in score['declared_selection_tool_replay_status']


def test_study_c_gold_never_enters_public_request():
    case={'id':'study_c_x','split':'development_reference','request':{'task':'x','gold':42},'expected':{},'category':'x','group':'x'}
    with pytest.raises(ValueError,match='Private'):
        score_text(case,'{}')


def test_study_c_ask_numeric_null_is_not_complete():
    case={'id':'study_c_x','split':'development_reference','request':{'task':'heat_sum_simple_daily','inputs':{},'units':{}},
          'expected':{'action':'ASK_FOR_DATA','tool':'gdd_simple_daily_v1','reason_code':'MISSING_INPUTS','requested_fields':['base','tmin','tmax','units.temperature','units.time_step']},'category':'missing','group':'gdd_simple_daily_v1'}
    score=score_text(case,json.dumps({**case['expected'],'numeric':None}))
    assert not score['correct'] and score['action_correct'] and score['tool_correct']

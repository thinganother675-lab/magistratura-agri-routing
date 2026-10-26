from __future__ import annotations
import importlib.util
import json
import copy
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('or_screen_new',ROOT/'scripts/openrouter_screen_20261002.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_only_new_exact_key_is_allowed(tmp_path):
    (tmp_path/'.env').write_text('openrouter_api_key=old-invalid\nOPENROUTER_API_KEY=also-old\nopenrouter_api_key_2="new-synthetic-key"\n',encoding='utf-8')
    assert m.read_key(tmp_path)==('new-synthetic-key','project_env:openrouter_api_key_2')
    (tmp_path/'.env').write_text('openrouter_api_key=old-invalid\n',encoding='utf-8')
    assert m.read_key(tmp_path)==('',None)

def test_zero_child_requires_explicit_selection_and_never_rotates(tmp_path):
    (tmp_path/'.env').write_text('openrouter_api_key_2=synthetic-management\nOPENROUTER_INFERENCE_KEY_ZERO_20261002=synthetic-child\n',encoding='utf-8')
    assert m.read_key(tmp_path)==('synthetic-management','project_env:openrouter_api_key_2')
    assert m.read_key(tmp_path,source_name='OPENROUTER_INFERENCE_KEY_ZERO_20261002')==('synthetic-child','project_env:OPENROUTER_INFERENCE_KEY_ZERO_20261002')
    (tmp_path/'.env').write_text('openrouter_api_key_2=synthetic-management\n',encoding='utf-8')
    assert m.read_key(tmp_path,source_name='OPENROUTER_INFERENCE_KEY_ZERO_20261002')==('',None)
    with pytest.raises(ValueError):m.read_key(tmp_path,source_name='OPENROUTER_API_KEY')

def test_management_type_preflight_blocks_inference_before_claim(tmp_path,monkeypatch):
    metadata_dir=tmp_path/'metadata';metadata_dir.mkdir()
    output=tmp_path/'output';output.mkdir()
    candidate=row();candidate.update(resolved_model_id='vendor/model:free',status='NOT_RUN',reason='eligible')
    source={'rows':[candidate],'metadata_requests_n':3}
    (metadata_dir/'manifest.json').write_text(json.dumps(source),encoding='utf-8')
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m,'metadata',lambda *args:(copy.deepcopy(source),{'http_status':200,'is_management_key':True,'free_model_daily_requests':{'remaining':50}}))
    class Client:
        def post(self,*args,**kwargs):raise AssertionError('Management keys cannot call inference')
    m.run_screen(Client(),'synthetic-key',metadata_dir,output,'isolated-mock-window')
    summary=json.loads((output/'summary.json').read_text())
    assert summary['status']=='AUTH_BLOCKED' and summary['generation_attempts']==0
    assert not (metadata_dir/'execution_claim.json').exists()

@pytest.mark.parametrize('field,value',[('request','0.01'),('input_cache_write','0.001'),
 ('image','1'),('audio','0.2'),('internal_reasoning','NaN'),('unknown_fee',None),('prompt',False)])
def test_every_present_price_component_fails_closed(field,value):
    prices={'prompt':'0','completion':'0','request':'0'};prices[field]=value
    assert not m.all_prices_zero(prices)

def test_model_resolution_never_substitutes_paid_sibling():
    cat=[{'id':'qwen/same-model','name':'Qwen: Same Model','pricing':{'prompt':'1','completion':'1'}}]
    assert m.resolve_requested(0,'Qwen: Same Model (free)',cat)==(None,[])
    cat.append({'id':'qwen/same-model:free','name':'Qwen: Same Model (free)','pricing':{'prompt':'0','completion':'0'}})
    assert m.resolve_requested(0,'Qwen: Same Model (free)',cat)[0]['id']=='qwen/same-model:free'

def test_ambiguous_match_is_not_executed():
    cat=[{'id':'x/m:free','name':'M (free)'},{'id':'y/m:free','name':'M (free)'}]
    model,ids=m.resolve_requested(0,'M (free)',cat)
    assert model is None and len(ids)==2

def row():
    ep={'tag':'provider/fixed-endpoint','pricing':{'prompt':'0','completion':'0','request':'0'},
      'supported_parameters':['temperature','max_tokens','response_format','structured_outputs','reasoning','seed']}
    return {'eligible':True,'model':{'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0'}},'selected_endpoint':ep}

def test_request_is_fixed_free_endpoint_and_gold_is_excluded():
    sample={'id':'dev_test','input':'Compute deficit','context':'Public context','inputs':{'rain':3},
      'expected':{'answer':'secret-gold'},'category':'hidden-category','expected_route':'cloud','correct':True}
    body=m.payload(row(),sample)
    provider=body['provider']
    assert provider['only']==provider['order']==['provider/fixed-endpoint']
    assert provider['allow_fallbacks'] is False and provider['require_parameters'] is True
    assert all(x==0 for x in provider['max_price'].values())
    assert 'models' not in body and 'plugins' not in body
    message=json.loads(body['messages'][1]['content'])
    assert set(message)=={'input','context','inputs'}
    assert 'secret-gold' not in str(body) and 'hidden-category' not in str(body)
    assert body['reasoning']['enabled'] is False

def test_payload_rechecks_nonzero_provider_fee():
    bad=row();bad['selected_endpoint']['pricing']['request']='0.001'
    with pytest.raises(ValueError):m.payload(bad,{'input':'hello','context':'','inputs':{}})

def test_ancillary_media_fee_is_blocked_even_when_token_fields_zero():
    bad=row();bad['model']['description']='Full-length songs are priced at $0.08 per song.'
    assert m.ancillary_charge(bad['model'])
    with pytest.raises(ValueError):m.payload(bad,{'input':'hello','context':'','inputs':{}})

def test_key_metadata_excludes_label_hash_and_creator_id():
    class Response:
        status_code=200
        def json(self):return {'data':{'label':'synthetic-private-key-label','hash':'private-hash','creator_user_id':'private-account','limit_remaining':1,'free_model_daily_requests':{'remaining':50}}}
    class Client:
        def get(self,*args,**kwargs):return Response()
    snapshot=m.key_snapshot(Client(),'synthetic-key')
    assert snapshot['http_status']==200
    assert not {'label','hash','creator_user_id'} & set(snapshot)
    assert snapshot['free_model_daily_requests']['remaining']==50

def test_all_twenty_one_requested_names_have_a_row_contract():
    assert len(m.REQUESTED)==21 and len(set(m.REQUESTED))==21

@pytest.mark.parametrize('content',[ '{"action":"ANSWER","answer":"right"}',
 '```json\n{"action":"ANSWER","answer":"right","numeric":null,"unit":null,"tool":null}\n```',
 '{"action":"ANSWER","answer":"right","numeric":true,"unit":null,"tool":null}',
 '{"action":"ANSWER","answer":"right","numeric":null,"unit":null,"tool":null,"extra":"x"}'])
def test_schema_failures_do_not_disappear_through_tolerant_parser(content):
    assert m.schema_failure(content) is not None
    assert m.schema_failure('{"action":"ANSWER","answer":"right","numeric":null,"unit":null,"tool":null}') is None

@pytest.mark.parametrize('http_status,expected_status',[(429,'RATE_LIMITED'),(402,'ZERO_CAP_CREDIT_BLOCKED')])
def test_rate_or_zero_credit_cap_stops_without_retry_or_paid_provider_fallback(tmp_path,monkeypatch,http_status,expected_status):
    metadata_dir=tmp_path/'metadata';metadata_dir.mkdir()
    output=tmp_path/'output';output.mkdir()
    candidate=row()
    candidate.update(resolved_model_id='vendor/model:free',requested_display_name='Vendor: Model (free)',
                     status='NOT_RUN',reason='eligible',scope='GENERAL_TEXT_DEV')
    source={'rows':[candidate],'metadata_requests_n':3}
    (metadata_dir/'manifest.json').write_text(json.dumps(source),encoding='utf-8')
    (tmp_path/'data').mkdir();(tmp_path/'data/benchmark.jsonl').write_text('public synthetic fixture',encoding='utf-8')
    monkeypatch.setattr(m,'ROOT',tmp_path)
    quota={'http_status':200,'free_model_daily_requests':{'remaining':50}}
    monkeypatch.setattr(m,'metadata',lambda *args:(copy.deepcopy(source),copy.deepcopy(quota)))
    monkeypatch.setattr(m,'read_dev_samples',lambda:[{'id':f'dev{i}','input':'Public question','context':'','inputs':{},'language':'en','category':'extractive_qa','split':'dev','expected':{'answers':['gold'],'action':'ANSWER'},'scoring':'span_em_f1'} for i in range(12)])
    class KeyResponse:
        status_code=200
        def json(self):return {'data':{'free_model_daily_requests':{'remaining':49}}}
    class RateResponse:
        status_code=http_status
        headers={'retry-after':'60','x-ratelimit-remaining':'0'}
    class Client:
        calls=0
        def get(self,*args,**kwargs):return KeyResponse()
        def post(self,*args,**kwargs):
            self.calls+=1
            assert kwargs['json']['provider']['allow_fallbacks'] is False
            assert 'gold' not in json.dumps(kwargs['json'])
            return RateResponse()
    client=Client();m.run_screen(client,'synthetic-key',metadata_dir,output,'isolated-mock-window')
    report=json.loads((output/'summary.json').read_text())
    assert client.calls==1 and report['generation_attempts']==1 and report['retries']==0
    assert report['status']=='PARTIAL' and expected_status in report['stop_reason']
    assert report['rows'][0]['status']==expected_status
    assert report['rows'][0]['unknown_cost_events']==1
    assert report['rows'][0]['known_input_tokens']['known_sum'] is None
    raw=json.loads((output/'raw.jsonl').read_text())
    assert raw['rate_limit_headers']['retry-after']=='60'

def test_rejected_key_preflight_makes_no_inference_calls(tmp_path,monkeypatch):
    metadata_dir=tmp_path/'metadata';metadata_dir.mkdir()
    output=tmp_path/'output';output.mkdir()
    candidate=row();candidate.update(resolved_model_id='vendor/model:free',requested_display_name='Model',status='NOT_RUN',reason='eligible')
    source={'rows':[candidate],'metadata_requests_n':3}
    (metadata_dir/'manifest.json').write_text(json.dumps(source),encoding='utf-8')
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m,'metadata',lambda *args:(copy.deepcopy(source),{'http_status':401}))
    class Client:
        def post(self,*args,**kwargs):raise AssertionError('No inference after rejected key')
    m.run_screen(Client(),'synthetic-key',metadata_dir,output,'isolated-mock-window')
    summary=json.loads((output/'summary.json').read_text())
    assert summary['status']=='AUTH_BLOCKED' and summary['generation_attempts']==0
    assert summary['rows'][0]['status']=='AUTH_BLOCKED'
    assert not (metadata_dir/'execution_claim.json').exists()

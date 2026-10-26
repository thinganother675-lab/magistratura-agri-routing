import importlib.util
from pathlib import Path
import sys
import pytest
from agro_route.prerouting import SharedBudget

script_dir=Path(__file__).parents[1]/'scripts'
sys.path.insert(0,str(script_dir))
try:
    spec=importlib.util.spec_from_file_location('prerouting_driver',script_dir/'run_prerouting_dev.py')
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
finally:sys.path.pop(0)

def test_offline_socket_guard_covers_clients_beyond_the_jev_http_hook():
    with pytest.raises(RuntimeError):driver.offline_socket_guard(['offline_laya'],'socket.connect',(object(),('203.0.113.1',443)))
    driver.offline_socket_guard(['offline_laya'],'socket.connect',(object(),('127.0.0.1',1234)))
    driver.offline_socket_guard(['jev_first'],'socket.connect',(object(),('203.0.113.1',443)))

def test_jev_version_mismatch_keeps_reported_fee_and_stops_further_dispatch(tmp_path):
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'model':'different-version','usage':{'input_tokens':500,'output_tokens':90}}
    class Client:
        calls=0
        def post(self,*a,**kw):self.calls+=1;return Response()
    client=Client();budget=SharedBudget(tmp_path/'budget.sqlite3',.01)
    router=driver.Jev('synthetic-test-key',client,budget,tmp_path)
    first=router({'input':'Which soil?','context':'loam','inputs':{}},True)
    second=router({'input':'Which soil?','context':'loam','inputs':{}},True)
    assert first['router_external_calls']==1 and first['cost_usd']==pytest.approx(.000021)
    assert second['router_external_calls']==0 and second['cost_usd']==0 and client.calls==1
    assert router.stop=='PinnedModelMismatch'
    assert budget.snapshot()['reserved_unknown_usd']==0

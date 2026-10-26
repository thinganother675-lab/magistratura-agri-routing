import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('home_demo_tests', ROOT / 'scripts/serve_home_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def prohibited(_):
    raise AssertionError('Unexpected provider call')


def test_offline_cloud_selection_never_calls_cloud():
    result = demo.demo_decide({'input': 'A question with no context', 'context': '', 'inputs': {}},
                              'cloud', prohibited, prohibited, False, 900)
    assert result['route'] == 'ABSTAIN'
    assert result['cloud_calls'] == result['local_calls'] == 0
    assert not result['experiment_record']


def test_missing_numeric_gate_never_calls_provider():
    result = demo.demo_decide({'input': 'Calculate ET0.', 'context': '', 'inputs': {}},
                              'cascade', prohibited, prohibited, True, 900)
    assert result['output']['action'] == 'ASK_FOR_DATA'
    assert result['cloud_calls'] == result['local_calls'] == 0


def test_supported_local_reader_does_not_escalate():
    calls = []
    def local(_):
        calls.append('local')
        return {'provider': 'local', 'output': {'action': 'ANSWER', 'answer': 'soil moisture', 'numeric': None},
                'error': None, 'cost_usd': 0}
    result = demo.demo_decide({'input': 'Which variable?', 'context': 'The variable is soil moisture.', 'inputs': {}},
                              'cascade', local, prohibited, True, 900)
    assert result['route'] == 'LOCAL_MODEL'
    assert calls == ['local']


def test_absent_local_credential_blocks_before_http(monkeypatch):
    def forbidden_client(*_, **__):
        raise AssertionError('Unexpected HTTP connection')
    monkeypatch.setattr(demo.httpx, 'Client', forbidden_client)
    try:
        demo.HomeLocal('', 'home-demo-gemma26').call({'input': 'Example'})
    except demo.final.ProviderBlocked as exc:
        assert exc.provider == 'local'
    else:
        raise AssertionError('Expected explicit provider blocking')


def test_low_resource_headroom_blocks_before_http(monkeypatch):
    def forbidden_client(*_, **__):
        raise AssertionError('Resource guard must prevent HTTP/inference')
    monkeypatch.setattr(demo.final.home, 'resource_headroom', lambda: {'ram_available_gib': 1.9, 'gpu_free_mib': 4000})
    monkeypatch.setattr(demo.httpx, 'Client', forbidden_client)
    try:
        demo.HomeLocal('MOCK_SECRET', 'home-demo-gemma26').call({'input': 'Example'})
    except demo.final.ProviderBlocked as exc:
        assert exc.provider == 'local' and exc.reason['type'] == 'resource_guard'
    else:
        raise AssertionError('Expected resource guard blocking')

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    'public_scan', Path(__file__).resolve().parents[1] / 'scripts/scan_public_artifacts.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_secret_findings_exclude_values(tmp_path):
    secret = 'test-only-secret-1234567890'
    path = tmp_path / 'config.json'
    path.write_text('{"token":"' + secret + '"}', encoding='utf-8')
    findings = scanner.inspect_file(tmp_path, path, {secret})
    assert findings == [{'path': 'config.json', 'rule': 'configured_secret_exact_match', 'line': 1}]
    assert secret not in str(findings)


def test_token_pattern_detects_without_persisting_token(tmp_path):
    token = 'hf_' + 'A' * 28
    path = tmp_path / 'output.txt'
    path.write_text('metadata\n' + token, encoding='utf-8')
    findings = scanner.inspect_file(tmp_path, path, set())
    assert findings == [{'path': 'output.txt', 'rule': 'huggingface_token', 'line': 2}]
    assert token not in str(findings)


def test_secret_filename_rejected_but_empty_example_allowed(tmp_path):
    actual = tmp_path / '.env'
    actual.write_text('CLOUD_API_KEY=\n', encoding='utf-8')
    example = tmp_path / '.env.example'
    example.write_text('CLOUD_API_KEY=\n', encoding='utf-8')
    assert scanner.inspect_file(tmp_path, actual, set())[0]['rule'] == 'sensitive_filename'
    assert scanner.inspect_file(tmp_path, example, set()) == []


def test_opaque_literal_credential_detected_without_known_format(tmp_path):
    secret = 'unrecognized-secret-format-987654321'
    path = tmp_path / 'mistaken-config.txt'
    path.write_text('CLOUD_API_KEY=' + secret, encoding='utf-8')
    findings = scanner.inspect_file(tmp_path, path, set())
    assert findings == [{'path': 'mistaken-config.txt', 'rule': 'literal_credential_assignment', 'line': 1}]
    assert secret not in str(findings)


def test_binary_plot_allowed_and_unreadable_text_flagged(tmp_path):
    binary = tmp_path / 'plot.png'
    binary.write_bytes(b'\x89PNG\x00\xff')
    assert scanner.inspect_file(tmp_path, binary, set()) == []
    text = tmp_path / 'unknown.txt'
    text.write_bytes(b'\xffbroken')
    assert scanner.inspect_file(tmp_path, text, set())[0]['rule'] == 'unreadable_text_requires_review'


def test_lowercase_provider_keys_are_used_for_exact_leak_detection(tmp_path, monkeypatch):
    names = ('mercury_api_key', 'openrouter_api_key', 'jev_api_key', 'LM_API_TOKEN')
    secrets = {name: 'synthetic-value-' + str(i) for i, name in enumerate(names)}
    for name in scanner.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / '.env').write_text('\n'.join(name + '=' + value for name, value in secrets.items()), encoding='utf-8')
    assert scanner.configured_secret_values(tmp_path) == set(secrets.values())
    public = tmp_path / 'raw.txt'
    public.write_text(secrets['jev_api_key'], encoding='utf-8')
    findings = scanner.inspect_file(tmp_path, public, scanner.configured_secret_values(tmp_path))
    assert findings == [{'path': 'raw.txt', 'rule': 'configured_secret_exact_match', 'line': 1}]
    assert secrets['jev_api_key'] not in str(findings)

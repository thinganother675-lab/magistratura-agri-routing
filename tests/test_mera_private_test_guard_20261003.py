# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import pytest
from agro_route.mera_private_test_guard_20261003 import GATES, readiness

def invented():
    return {'dataset': 'MERA-evaluation/ruTXTAgroBench',
            'protocol_status': 'FROZEN_BEFORE_TEST', 'test_gold_dependency': False,
            'private_test_run': False, 'primary_local': {'id': 'invented'},
            'primary_cloud': {'id': 'invented'}, 'routing_rule': {'id': 'invented'},
            'gates': {name: {'approved': True, 'evidence_path': 'receipt.json',
                            'evidence_sha256': hashlib.sha256(b'real receipt bytes').hexdigest()}
                      for name in GATES}}

@pytest.fixture
def receipts(monkeypatch):
    monkeypatch.setattr(Path, 'is_file', lambda path: True)
    monkeypatch.setattr(Path, 'read_bytes', lambda path: b'real receipt bytes')
    return Path(__file__).resolve().parents[1]

def test_ready_flags_do_not_replace_missing_evidence(receipts):
    doc = invented()
    for gate in doc['gates'].values():
        gate.pop('evidence_sha256')
    result = readiness(doc, receipts)
    assert not result['MERA_PRIVATE_TEST_READY']
    assert len(result['blockers']) == len(GATES)
    assert not result['submission_permitted']

@pytest.mark.parametrize('name', GATES)
def test_each_required_gate_independently_blocks_test(name, receipts):
    doc = invented()
    doc['gates'][name]['approved'] = False
    assert name.upper() in readiness(doc, receipts)['blockers']

def test_changed_or_external_receipt_never_approves(receipts):
    doc = invented()
    doc['gates']['antoniy_approval']['evidence_sha256'] = '0' * 64
    assert 'ANTONIY_APPROVAL_EVIDENCE_CHANGED' in readiness(doc, receipts)['blockers']
    doc['gates']['denis_approval']['evidence_path'] = str(receipts.parent / 'unrelated.json')
    assert 'DENIS_APPROVAL_EVIDENCE_UNAVAILABLE' in readiness(doc, receipts)['blockers']

def test_hidden_gold_dependency_and_prior_test_state_fail_closed(receipts):
    doc = invented()
    doc['test_gold_dependency'] = True
    doc['private_test_run'] = None
    result = readiness(doc, receipts)
    assert 'HIDDEN_TEST_GOLD_DEPENDENCY_NOT_EXCLUDED' in result['blockers']
    assert 'TEST_ALREADY_RUN_OR_STATE_UNKNOWN' in result['blockers']

def test_even_all_verified_gates_do_not_execute_or_submit(receipts):
    result = readiness(invented(), receipts)
    assert result['MERA_PRIVATE_TEST_READY']
    assert result['inference_permitted'] is False
    assert result['submission_permitted'] is False
    assert result['human_identity_verified_by_code'] is False

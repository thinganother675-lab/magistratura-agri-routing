# SPDX-License-Identifier: Apache-2.0
"""Fail-closed readiness inspection only; never runs inference or submits data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

GATES = (
    'primary_local_selected', 'primary_cloud_selected', 'routing_rule_frozen',
    'server_scoring_resolved', 'official_workflow_verified', 'content_rights_understood',
    'antoniy_approval', 'denis_approval', 'explicit_submission_authorization',
)

def readiness(protocol, root):
    """Flag edits alone cannot approve TEST: every gate needs a verified receipt.

    Receipt hashes establish artifact integrity, not the identity or authority of
    a reviewer. Human approvals and permission must come from actual human input.
    This inspector never grants execution permission, even when all gates pass.
    """
    root = Path(root).resolve()
    blockers = []
    if protocol.get('dataset') != 'MERA-evaluation/ruTXTAgroBench':
        blockers.append('DATASET_UNIDENTIFIED')
    if protocol.get('protocol_status') != 'FROZEN_BEFORE_TEST':
        blockers.append('PROTOCOL_NOT_FROZEN')
    if protocol.get('test_gold_dependency') is not False:
        blockers.append('HIDDEN_TEST_GOLD_DEPENDENCY_NOT_EXCLUDED')
    if protocol.get('private_test_run') is not False:
        blockers.append('TEST_ALREADY_RUN_OR_STATE_UNKNOWN')
    gates = protocol.get('gates')
    if not isinstance(gates, dict):
        gates = {}
    for name in GATES:
        entry = gates.get(name)
        if not isinstance(entry, dict) or entry.get('approved') is not True:
            blockers.append(name.upper())
            continue
        path, expected = entry.get('evidence_path'), entry.get('evidence_sha256')
        if not isinstance(path, str) or not isinstance(expected, str) or len(expected) != 64:
            blockers.append(name.upper() + '_EVIDENCE_MISSING')
            continue
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            blockers.append(name.upper() + '_EVIDENCE_UNAVAILABLE')
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            blockers.append(name.upper() + '_EVIDENCE_CHANGED')
    for name in ('primary_local', 'primary_cloud', 'routing_rule'):
        if not isinstance(protocol.get(name), dict) or not protocol[name]:
            blockers.append(name.upper() + '_CONFIG_MISSING')
    return {'MERA_PRIVATE_TEST_READY': not blockers, 'blockers': blockers,
            'inference_permitted': False, 'submission_permitted': False,
            'inspection_only': True, 'human_identity_verified_by_code': False}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('protocol', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = args.protocol.resolve()
    if not target.is_relative_to(root):
        raise ValueError('Only workspace protocols may be inspected')
    report = readiness(json.loads(target.read_text(encoding='utf-8')), root)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['MERA_PRIVATE_TEST_READY'] else 2

if __name__ == '__main__':
    raise SystemExit(main())

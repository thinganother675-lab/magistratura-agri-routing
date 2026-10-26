# SPDX-License-Identifier: Apache-2.0
"""Write delivery records after checking immutable sources; no inference or upload."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/20261003_mera_agro_routing_3de88b82'
CODE_COMMIT = '72b0c32ebc1eb1b514adc3489a2e87231d299250'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_new(name, value):
    with (STUDY / name).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    historical = load(ROOT / 'docs/historical_integrity_20261003.json')['sha256']
    failures = [name for name, digest in historical.items()
                if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    assert not failures, 'Protected historical material changed: ' + repr(failures)
    archives = load(ROOT / 'experiments/mera_code_archive_20261003/source_index.json')
    archive_count = 0
    for profile, description in archives.items():
        manifest = load(STUDY / (profile + '_dev_manifest.json'))
        raw = ROOT / '.runtime/mera' / STUDY.name / (profile + '_raw.jsonl')
        assert sha(raw) == manifest['raw_sha256']
        for original, source in description['sources'].items():
            assert sha(ROOT / source['archive_file']) == source['sha256']
            assert manifest['uncommitted_source_hashes'][original] == source['sha256']
            blob = subprocess.check_output(['git', 'show', CODE_COMMIT + ':' + source['archive_file']], cwd=ROOT)
            assert hashlib.sha256(blob).hexdigest() == source['sha256']
            archive_count += 1
        assert manifest['private_test_run'] is False
        if manifest['provider'] == 'local':
            assert manifest['own_instance_cleanup_success'] is True
    analysis = load(STUDY / 'dev_analysis.json')
    assert analysis['analysis_code_commit'] == CODE_COMMIT
    analyzer_blob = subprocess.check_output(['git', 'show', CODE_COMMIT + ':scripts/analyze_mera_dev_20261003.py'], cwd=ROOT)
    assert hashlib.sha256(analyzer_blob).hexdigest() == analysis['analysis_source_sha256']
    dataset = load(ROOT / 'data/study_c_technical_20261003.json')
    assert len(dataset['cases']) == 27
    remote = load(STUDY / 'private_remote_before_delivery.json')
    assert remote['private'] is True and remote['identity'] == 'Apartman36'
    now = datetime.now(timezone.utc).isoformat()
    write_new('replay_profile_provenance.json', {
        'utc': now, 'analysis_file': str((STUDY / 'dev_analysis.json').relative_to(ROOT)).replace('\\', '/'),
        'analysis_sha256': sha(STUDY / 'dev_analysis.json'), 'analysis_code_commit': CODE_COMMIT,
        'scope': 'All counterfactual_grid entries; attribution annotation, no metric recomputation',
        'counterfactual_local_profile': 'gemma-4-26b-a4b-it',
        'counterfactual_cloud_profile': 'mercury-2_instant-256',
        'cloud_parameters': load(STUDY / 'cloud_compatibility_revision_before_calls.json'),
        'original_medium128_profile_in_counterfactual': False,
        'source_archives': 'experiments/mera_code_archive_20261003/source_index.json',
        'status': 'COUNTERFACTUAL_CACHED_DEV_REPLAY_NOT_ACTUAL_REQUEST_SAVINGS'
    })
    write_new('decision_gate.json', {
        'utc': now, 'MERA_PRIVATE_TEST_READY': 'NO', 'protocol_freeze': 'NOT_FROZEN',
        'selected_local_candidate': 'gemma-4-26b-a4b-it IQ4_NL_XL',
        'selected_cloud_primary': None, 'selected_routing_policy': None,
        'tested_cloud_candidate': 'mercury-2 instant256; weak small-DEV reference, not primary selection',
        'future_primary_comparison': 'one local-cloud cascade versus one cloud-only baseline',
        'blockers': analysis['blockers'], 'data_rights': analysis['data_rights'],
        'private_test_run': False, 'official_remote_scores': None, 'external_submission': 'NOT_RUN',
        'public_leaderboard': 'NOT_AUTHORIZED_OR_RUN',
        'planning_only_not_selected_budget': {
            'test_n': 2642, 'cloud_only_calls': 2642, 'cascade_cloud_calls_min': 0,
            'cascade_cloud_calls_max': 2642, 'hosted_router_calls': 0,
            'input_tokens_assumed_per_call': 1000, 'output_tokens_limit_assumed': 256,
            'prices_usd_per_m_input_output': [0.25, 0.75],
            'cloud_only_usd': 2642 * (1000 * .25 + 256 * .75) / 1e6,
            'two_full_cloud_branches_usd': 5284 * (1000 * .25 + 256 * .75) / 1e6,
            'cloud_only_minutes_at_pilot_mean_without_overhead': 2642 * analysis['model_profiles']['mercury-2_instant-256']['summary']['mean_latency_ms'] / 60000,
            'requires_new_estimate_after_model_selection': True
        },
        'next_smallest_step': 'Human review of synthetic A-scoring defect and unsent maintainer questions; no automated contact',
        'historical_HOME150': 'FROZEN_UNCHANGED', 'review40': 'PRESERVED_INTERNAL_METHODOLOGY_PACK_NOT_AGRONOMIC_GOLD_GATE'
    })
    write_new('validation_final.json', {
        'utc': now, 'status': 'PASS', 'development_code_commit': CODE_COMMIT,
        'tests_observed_in_this_session': {
            'baseline_passed': 392, 'final_passed': 509, 'final_duration_seconds': 26.56,
            'command': '.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider --basetemp .runtime/mera/pytest_final_20261003_01',
            'scope': 'Full project suite; recorded from completed tool execution, not rerun by this writer',
            'test_source_commit': CODE_COMMIT,
            'areas': ['adapter', 'normalization', 'gold isolation', 'split isolation', 'official-schema packaging with synthetic logs',
                      'remote aggregate ingestion with synthetic fixtures', 'restricted redistribution paths', 'usage accounting', 'deterministic formula contracts']
        },
        'protected_historical_files_rechecked': len(historical), 'historical_sha256_failures': failures,
        'review40_files_in_protected_manifest': sum('review40' in name for name in historical),
        'executed_source_archives_verified_against_git': archive_count,
        'restricted_raw_run_hashes_verified': len(archives),
        'analysis_code_blob_hash_verified': True,
        'study_c_development_cases': len(dataset['cases']), 'study_c_model_experiment_run': False,
        'generative_models_downloaded': 0, 'private_test_inputs_downloaded': False, 'private_gold_obtained': False,
        'external_submissions': 0, 'leaderboard_publications': 0, 'messages_to_maintainers': 0,
        'current_private_remote_verified': {'repository': remote['destination'], 'identity': remote['identity'],
                                            'private': remote['private'], 'main_sha': remote['remote_main_sha']},
        'delivery_push_status': 'NOT_PUSHED', 'safe_source_exclusion_scope': 'MERA questions, DEV gold and full generation text remain ignored under .runtime/mera',
        'human_design_claim_and_authorship_reviews': 'PENDING',
        'code_review_note': 'Independent agent review performed; human authors retain final responsibility'
    })
    print(json.dumps({'historical_files': len(historical), 'archive_sources': archive_count, 'status': 'PASS', 'gate': 'NO'}))


if __name__ == '__main__':
    main()

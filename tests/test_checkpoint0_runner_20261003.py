import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checkpoint0_runner',ROOT/'scripts/run_systems_study_c_checkpoint0_20261003.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def test_recovery_load_explicit_checkpoints_parallel_and_speculation():
    body=runner.native_load_body('qwen3.8-27b')
    assert body['context_checkpoints']==0 and body['parallel']==1
    assert body['speculative_draft_mtp'] is False
    assert 'gpu_offload_ratio' not in body
    runner.verify_load_config(body)


@pytest.mark.parametrize('field,value',[('context_length',4096),('eval_batch_size',512),('parallel',4),('speculative_draft_mtp',True),('context_checkpoints',32),('flash_attention',False)])
def test_load_response_must_confirm_all_controls(field,value):
    config=runner.native_load_body('x');config[field]=value
    with pytest.raises(RuntimeError,match='not confirmed'):runner.verify_load_config(config)

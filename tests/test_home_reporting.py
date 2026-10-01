"""Preserve measured token usage even when a structured answer is invalid."""
import importlib.util
from pathlib import Path

def report_module():
    path=Path(__file__).resolve().parents[1]/'scripts/report_local_inventory.py'
    spec=importlib.util.spec_from_file_location('inventory_report_under_test',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def test_token_stats_from_parser_failure_are_counted_without_imputation():
    data=[{'local':{'usage':{'prompt_tokens':100,'completion_tokens':20},'stats':{}}},
          {'local':{'error':{'type':'JSONDecodeError'},'stats':{'prompt_tokens':50,'completion_tokens':7}}},
          {'local':{'error':{'type':'CLIError'},'stats':{}}}]
    totals=report_module().token_totals(data)
    assert totals['input_tokens_known_sum']==150 and totals['output_tokens_known_sum']==27
    assert totals['input_usage_coverage_n']==2 and totals['usage_n']==3
    assert not totals['usage_complete']

def test_absent_token_usage_is_unknown_not_zero():
    totals=report_module().token_totals([])
    assert totals['input_tokens_known_sum'] is None and totals['output_tokens_known_sum'] is None
    assert not totals['usage_complete']

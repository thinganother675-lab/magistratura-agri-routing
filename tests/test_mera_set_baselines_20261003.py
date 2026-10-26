import itertools
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from agro_route.mera_set_baselines_20261003 import baseline_expectations
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mera_trivial_baselines_20261003 import aggregate


@pytest.mark.parametrize('k,m', [(1, 1), (2, 1), (4, 2), (5, 5), (8, 3)])
def test_analytic_expectation_matches_exhaustive_nonempty_sets(k, m):
    gold = set(range(m))
    subsets = [set(c) for r in range(1, k + 1) for c in itertools.combinations(range(k), r)]
    expected_f1 = sum(2 * len(gold & p) / (m + len(p)) for p in subsets) / len(subsets)
    expected_em = sum(gold == p for p in subsets) / len(subsets)
    got = baseline_expectations(k, m)['uniform_nonempty_subset']
    assert got['em'] == pytest.approx(expected_em)
    assert got['f1'] == pytest.approx(expected_f1)
    single = baseline_expectations(k, m)['uniform_single_option']
    assert single['em'] == pytest.approx(sum(gold == {a} for a in range(k)) / k)
    assert single['f1'] == pytest.approx(sum(2 * len(gold & {a}) / (m + 1) for a in range(k)) / k)


@pytest.mark.parametrize('k,m', [(0, 0), (2, 0), (2, 3), (9, 1), (True, 1)])
def test_invalid_original_cardinality_is_not_repaired(k, m):
    with pytest.raises(ValueError):
        baseline_expectations(k, m)


def test_reference_parser_status_string_is_not_mistaken_for_validity():
    items = [SimpleNamespace(item_id=1, options=('A', 'B')),
             SimpleNamespace(item_id=2, options=('A', 'B'))]
    refs = {1: 'A', 2: '\u0410'}
    original = dict(refs)
    got = aggregate(items, refs)
    assert got['n_expected'] == 2 and got['n_scored'] == 1
    assert got['reference_issues'] == 1 and got['unresolved_ids'] == [2]
    assert got['methods']['all_available_options']['f1'] == pytest.approx(2 / 3)
    assert refs == original

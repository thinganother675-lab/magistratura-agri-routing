"""Independent numerical references, boundary validation and new HOME-PC statistics."""
import math

import numpy as np
import pytest

from agro_route.evaluation import score
from agro_route.home_stats import cluster_bootstrap_interval, mcnemar_exact, paired_cluster_bootstrap, wilson_interval
from agro_route.routing import hard_gate
from agro_route.tools import InputError, execute


def et0_inputs():
    # FAO-56 ch.4 Example 18, Uccle: published rounded inputs; ET0=3.88 mm/day.
    # https://www.fao.org/4/x0490e/x0490e08.htm
    return dict(temperature=16.9, rn=13.28, g=0, u2=2.078, es=1.997, ea=1.409,
                delta=.122, gamma=.0666, temperature_unit="C")


def test_et0_independent_fao56_worked_example_18():
    assert execute("et0", et0_inputs())["numeric"] == pytest.approx(3.88, abs=.01)


@pytest.mark.parametrize("temperature,saturation", [(24.5, 3.075), (15, 1.705)])
def test_saturation_independent_fao56_example_3(temperature, saturation):
    # RH=0 => VPD equals saturation pressure, FAO-56 ch.3 Example 3.
    assert execute("vpd", dict(temperature=temperature, rh=0, temperature_unit="C"))["numeric"] == pytest.approx(saturation, abs=.001)


@pytest.mark.parametrize("override", [
    {"tmin": []}, {"tmin": [1, 2]}, {"tmax": [0]}, {"base": True},
    {"tmin": [math.inf]}, {"tmax": [61]}, {"base": 41}, {"temperature_unit": "F"},
])
def test_gdd_boundary_rejections(override):
    data = dict(tmin=[1], tmax=[10], base=5, temperature_unit="C")
    data.update(override)
    with pytest.raises(InputError):
        execute("gdd", data)


@pytest.mark.parametrize("override", [{"u2": -1}, {"u2": 31}, {"ea": 3}, {"gamma": 0}, {"delta": 0}, {"rn": math.inf}, {"g": True}])
def test_et0_boundary_rejections(override):
    data = et0_inputs()
    data.update(override)
    with pytest.raises(InputError):
        execute("et0", data)


@pytest.mark.parametrize("override", [{"target": -1}, {"rain": [-1]}, {"rain": []}, {"rain": [True]}, {"precipitation_unit": "inch"}])
def test_rain_deficit_boundary_rejections(override):
    data = dict(target=10, rain=[3], precipitation_unit="mm")
    data.update(override)
    with pytest.raises(InputError):
        execute("rain_deficit", data)


def test_multiple_tools_are_not_silently_single_executed():
    assert hard_gate({"input": "Calculate GDD and VPD.", "inputs": {}}) is None


def test_score_nonfinite_or_boolean_numeric_cannot_be_correct():
    sample = {"expected": {"action": "ANSWER", "numeric": 1, "unit": "mm"}, "scoring": "numeric_tolerance", "category": "numeric"}
    for numeric in (True, math.inf, math.nan, "1"):
        result = score(sample, {"action": "ANSWER", "numeric": numeric, "unit": "mm"})
        assert not result["correct"] and result["critical_error"]


def test_wilson_known_midpoint_and_extremes():
    assert wilson_interval(5, 10) == pytest.approx([.2365930905, .7634069095])
    assert wilson_interval(0, 10) == pytest.approx([0, .2775327999])
    assert wilson_interval(10, 10) == pytest.approx([.7224672001, 1])


@pytest.mark.parametrize("counts", [(0, 0), (11, 10), (-1, 10), (True, 10), (1.5, 10)])
def test_wilson_rejects_missing_or_invalid_counts(counts):
    with pytest.raises(ValueError):
        wilson_interval(*counts)


def test_paired_bootstrap_identity_and_direction():
    a = [1, 1, 0, 0]
    groups = ["family_a", "family_a", "family_b", "family_b"]
    identical = paired_cluster_bootstrap(a, a, groups, repeats=100)
    assert identical["estimate"] == 0 and identical["ci95"] == [0, 0]
    plus_one = paired_cluster_bootstrap(np.asarray(a) + 1, a, groups, repeats=100)
    assert plus_one["estimate"] == 1 and plus_one["ci95"] == [1, 1]


def test_whole_group_bootstrap_matches_exact_sampling_reference():
    # Unequal cluster sizes distinguish whole-group, per-row weighted bootstrap
    # from incorrectly averaging cluster means or resampling individual rows.
    values, groups = [0, 0, 1], ["a", "a", "b"]
    selected = np.random.default_rng(7).integers(0, 2, (100, 2))
    draws = np.asarray([0., 1.])[selected].sum(axis=1) / np.asarray([2, 1])[selected].sum(axis=1)
    result = cluster_bootstrap_interval(values, groups, repeats=100, seed=7)
    assert result["estimate"] == pytest.approx(1 / 3)
    assert result["ci95"] == pytest.approx(np.quantile(draws, [.025, .975]))
    assert result == cluster_bootstrap_interval(values, groups, repeats=100, seed=7)


def test_one_cluster_is_explicitly_warned():
    result = cluster_bootstrap_interval([1, 0], ["one", "one"], repeats=100)
    assert result["ci95"] == [.5, .5] and "one cluster" in result["warning"]


@pytest.mark.parametrize("values,groups", [([], []), ([1], []), ([math.nan], ["a"]), ([1], [None]), ([1], [["a"]])])
def test_bootstrap_rejects_invalid_or_missing_data(values, groups):
    with pytest.raises(ValueError):
        cluster_bootstrap_interval(values, groups, repeats=100)


def test_mcnemar_exact_known_discordance_and_swap():
    # Six wins and no losses => 2*(1/2)^6=.03125; exact small sample test.
    a, b = [1] * 6 + [1, 0], [0] * 6 + [1, 0]
    result = mcnemar_exact(a, b)
    assert (result["wins"], result["losses"], result["pvalue"]) == (6, 0, .03125)
    swapped = mcnemar_exact(b, a)
    assert swapped["pvalue"] == result["pvalue"]
    assert swapped["quality_difference"] == -result["quality_difference"]
    assert mcnemar_exact(a, a)["pvalue"] == 1


@pytest.mark.parametrize("a,b", [([1], [0, 1]), ([.5], [0]), ([], []), ([math.nan], [0])])
def test_mcnemar_rejects_nonbinary_or_unpaired_data(a, b):
    with pytest.raises(ValueError):
        mcnemar_exact(a, b)

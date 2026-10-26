"""Statistics for new HOME-PC runs; frozen historical analysis is unchanged.

Cluster resampling keeps all rows from a source/family together and uses the
same sampled clusters for a paired difference. The estimand is the per-row mean,
not a mean giving each unequal-size cluster equal weight. Stable input order,
seed and dependency versions are part of reproducibility metadata.
"""
from numbers import Integral, Real
from statistics import NormalDist

import numpy as np
from scipy.stats import binomtest


def _confidence(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not 0 < value < 1:
        raise ValueError("confidence must lie strictly between 0 and 1")
    return float(value)


def wilson_interval(successes, total, confidence=0.95):
    """Two-sided Wilson score interval; empty/missing data are not zero accuracy."""
    confidence = _confidence(confidence)
    if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (successes, total)):
        raise ValueError("successes and total must be integer counts")
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("require total > 0 and 0 <= successes <= total")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [float(max(0, center - radius)), float(min(1, center + radius))]


def _values(values):
    try:
        raw = list(values)
    except TypeError as exc:
        raise ValueError("values must be a nonempty numeric sequence") from exc
    if not raw or any(not isinstance(v, (Real, np.bool_)) for v in raw):
        raise ValueError("values must be a nonempty numeric sequence without missing values")
    array = np.asarray(raw, dtype=float)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError("values must be finite and one-dimensional")
    return array


def cluster_bootstrap_interval(values, groups, *, repeats=5000, seed=20261001, confidence=0.95):
    """Percentile CI for a per-row mean by resampling whole source/family groups.

    A one-cluster CI is emitted as degenerate and explicitly warned about; it
    cannot support a population claim. Fewer than 20 clusters also gets a warning.
    Missing values are rejected, never silently dropped or replaced by zeros.
    """
    confidence = _confidence(confidence)
    array = _values(values)
    labels = list(groups)
    if len(labels) != len(array):
        raise ValueError("values and groups must have equal length")
    if isinstance(repeats, bool) or not isinstance(repeats, Integral) or repeats < 100:
        raise ValueError("repeats must be an integer >= 100")
    clusters = {}
    for index, label in enumerate(labels):
        if label is None or (isinstance(label, Real) and not np.isfinite(label)):
            raise ValueError("group labels cannot be missing or nonfinite")
        try:
            clusters.setdefault(label, []).append(index)
        except TypeError as exc:
            raise ValueError("group labels must be hashable") from exc
    sums = np.asarray([array[indexes].sum() for indexes in clusters.values()])
    sizes = np.asarray([len(indexes) for indexes in clusters.values()])
    rng = np.random.default_rng(seed)
    statistics = np.empty(repeats)
    # Chunking bounds transient memory even on larger research datasets.
    for start in range(0, repeats, 256):
        count = min(256, repeats - start)
        selected = rng.integers(0, len(clusters), (count, len(clusters)))
        statistics[start:start + count] = sums[selected].sum(axis=1) / sizes[selected].sum(axis=1)
    alpha = (1 - confidence) / 2
    interval = np.quantile(statistics, [alpha, 1 - alpha])
    warning = "one cluster: interval is degenerate; independent-source uncertainty is unidentifiable" if len(clusters) == 1 else "fewer than 20 clusters: percentile interval may be unstable" if len(clusters) < 20 else None
    return {
        "estimate": float(array.mean()), "ci95": [float(v) for v in interval],
        "n": len(array), "n_groups": len(clusters), "confidence": confidence,
        "repeats": int(repeats), "seed": seed,
        "estimand": "per-row mean, whole-group resampling", "warning": warning,
    }


def paired_cluster_bootstrap(a, b, groups, *, repeats=5000, seed=20261001, confidence=0.95):
    """CI for mean(a-b); callers must align both methods by the same unique IDs."""
    left, right = _values(a), _values(b)
    if len(left) != len(right):
        raise ValueError("paired vectors must have equal length")
    report = cluster_bootstrap_interval(left - right, groups, repeats=repeats, seed=seed, confidence=confidence)
    report["contrast"] = "a minus b, pairs aligned by caller"
    return report


def mcnemar_exact(a, b):
    """Exact two-sided McNemar via binomial discordant pairs; descriptive if clustered."""
    left, right = _values(a), _values(b)
    if len(left) != len(right):
        raise ValueError("paired binary vectors must have equal length")
    if not np.isin(left, [0, 1]).all() or not np.isin(right, [0, 1]).all():
        raise ValueError("McNemar requires binary correctness values")
    wins = int(np.sum((left == 1) & (right == 0)))
    losses = int(np.sum((left == 0) & (right == 1)))
    return {
        "n": len(left), "both_correct": int(np.sum((left == 1) & (right == 1))),
        "both_wrong": int(np.sum((left == 0) & (right == 0))),
        "wins": wins, "losses": losses, "discordant": wins + losses,
        "quality_difference": float((left - right).mean()),
        "pvalue": float(binomtest(wins, wins + losses, 0.5).pvalue) if wins + losses else 1.0,
        "limitation": "independent pairs required; descriptive unadjusted p for correlated variants or multiple comparisons",
    }

# SPDX-License-Identifier: Apache-2.0
"""Uninformed set baselines, analytically exact without sampling or tuning."""
from __future__ import annotations
import math


def baseline_expectations(k, m):
    if isinstance(k, bool) or isinstance(m, bool) or not isinstance(k, int) or not isinstance(m, int) or not 1 <= m <= k <= 8:
        raise ValueError('Require valid original reference cardinality and1..8 options')
    subsets = 2 ** k - 1
    return {
        'all_available_options': {'em': float(m == k), 'f1': 2 * m / (m + k)},
        'uniform_single_option': {'em': 1 / k if m == 1 else 0., 'f1': 2 * m / (k * (m + 1))},
        'uniform_nonempty_subset': {'em': 1 / subsets,
            'f1': sum(math.comb(k, r) * 2 * r * m / (k * (m + r)) for r in range(1, k + 1)) / subsets},
    }

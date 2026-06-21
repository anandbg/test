"""Combining probability forecasts (opinion pooling).

  - ``linear_pool``: weighted arithmetic mean  (sum w_i * p_i)
  - ``log_pool``:    weighted geometric mean, renormalized  (prod p_i ** w_i)

Logarithmic pooling takes confident forecasts more seriously and is sharper for
well-calibrated experts (Ranjan & Gneiting). We use it to blend the de-vigged
market with the Elo/Poisson model, weighting the market ~0.65 by default.

See RESEARCH.md section 5.
"""

from __future__ import annotations

import math
from typing import List, Sequence

__all__ = ["normalize", "linear_pool", "log_pool"]

_EPS = 1e-12


def normalize(probs: Sequence[float]) -> List[float]:
    s = sum(probs)
    if s <= 0:
        n = len(probs)
        return [1.0 / n] * n
    return [p / s for p in probs]


def _prep_weights(weights: Sequence[float], k: int) -> List[float]:
    if len(weights) != k:
        raise ValueError("number of weights must match number of forecasts")
    s = sum(weights)
    if s <= 0:
        raise ValueError("weights must sum to a positive number")
    return [w / s for w in weights]


def linear_pool(forecasts: Sequence[Sequence[float]], weights: Sequence[float]) -> List[float]:
    """Weighted arithmetic mean of several probability vectors."""
    if not forecasts:
        raise ValueError("need at least one forecast")
    k = len(forecasts)
    m = len(forecasts[0])
    w = _prep_weights(weights, k)
    out = [0.0] * m
    for wi, f in zip(w, forecasts):
        if len(f) != m:
            raise ValueError("all forecasts must have the same length")
        for idx in range(m):
            out[idx] += wi * f[idx]
    return normalize(out)


def log_pool(forecasts: Sequence[Sequence[float]], weights: Sequence[float]) -> List[float]:
    """Weighted geometric mean (log-odds pool), renormalized.

    ``p_j proportional to prod_i f_ij ** w_i``. Computed in log space for
    numerical stability; zero probabilities are floored to ``_EPS``.
    """
    if not forecasts:
        raise ValueError("need at least one forecast")
    k = len(forecasts)
    m = len(forecasts[0])
    w = _prep_weights(weights, k)
    log_acc = [0.0] * m
    for wi, f in zip(w, forecasts):
        if len(f) != m:
            raise ValueError("all forecasts must have the same length")
        for idx in range(m):
            log_acc[idx] += wi * math.log(max(f[idx], _EPS))
    mx = max(log_acc)
    out = [math.exp(v - mx) for v in log_acc]
    return normalize(out)

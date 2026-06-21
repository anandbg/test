"""Proper scoring rules for evaluating probabilistic forecasts.

Outcomes are ordered [home, draw, away] (so RPS treats them ordinally).
Lower is better for all three metrics.

  - Brier (multi-class): sum_i (p_i - y_i)^2
  - Ranked Probability Score: mean over thresholds of (cumP - cumY)^2  -- the
    field standard for ordinal W/D/L football forecasts.
  - Log loss: -log(p_outcome)

See RESEARCH.md sections 2 & 5.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

__all__ = ["brier", "rps", "log_loss", "evaluate"]

_EPS = 1e-15

# canonical ordinal order for a 1X2 market
OUTCOME_ORDER = ("home", "draw", "away")


def _onehot(outcome_index: int, n: int) -> List[float]:
    y = [0.0] * n
    y[outcome_index] = 1.0
    return y


def brier(probs: Sequence[float], outcome_index: int) -> float:
    """Multi-class Brier score for one forecast."""
    y = _onehot(outcome_index, len(probs))
    return sum((p - t) ** 2 for p, t in zip(probs, y))


def rps(probs: Sequence[float], outcome_index: int) -> float:
    """Ranked Probability Score for one ordinal forecast."""
    n = len(probs)
    y = _onehot(outcome_index, n)
    cum_p = 0.0
    cum_y = 0.0
    total = 0.0
    for i in range(n - 1):  # RPS uses the first n-1 cumulative thresholds
        cum_p += probs[i]
        cum_y += y[i]
        total += (cum_p - cum_y) ** 2
    return total / (n - 1)


def log_loss(probs: Sequence[float], outcome_index: int) -> float:
    """Negative log-likelihood of the realized outcome."""
    p = max(_EPS, min(1.0, probs[outcome_index]))
    return -math.log(p)


def evaluate(
    forecasts: Sequence[Sequence[float]],
    outcomes: Sequence[int],
) -> dict:
    """Mean Brier / RPS / log-loss + hit rate over a set of matches.

    ``forecasts[k]`` is a [home, draw, away] vector; ``outcomes[k]`` is the
    realized outcome index (0 home, 1 draw, 2 away).
    """
    if len(forecasts) != len(outcomes):
        raise ValueError("forecasts and outcomes must be the same length")
    if not forecasts:
        return {"n": 0, "brier": float("nan"), "rps": float("nan"),
                "log_loss": float("nan"), "hit_rate": float("nan")}

    n = len(forecasts)
    b = s = l = 0.0
    hits = 0
    for f, o in zip(forecasts, outcomes):
        b += brier(f, o)
        s += rps(f, o)
        l += log_loss(f, o)
        if max(range(len(f)), key=lambda i: f[i]) == o:
            hits += 1
    return {
        "n": n,
        "brier": b / n,
        "rps": s / n,
        "log_loss": l / n,
        "hit_rate": hits / n,
    }

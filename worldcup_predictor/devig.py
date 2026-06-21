"""De-vigging: convert bookmaker decimal odds into fair probabilities.

Every method takes a list of decimal odds (e.g. ``[2.10, 3.40, 3.60]`` for a
home / draw / away market) and returns a list of probabilities that sum to 1.

Methods (see RESEARCH.md section 1):
  - ``multiplicative``  proportional normalization (default fallback)
  - ``additive``        equal-margin subtraction (can go negative)
  - ``power``           solve exponent e so that sum(r_i ** e) == 1
  - ``odds_ratio``      Cheung's odds-ratio transform
  - ``shin``            Shin (1992/93) insider-trading model (recommended)

References: Strumbelj (2014); R ``implied`` package.
"""

from __future__ import annotations

import math
from typing import List, Sequence

__all__ = [
    "implied_raw",
    "overround",
    "margin",
    "multiplicative",
    "additive",
    "power",
    "odds_ratio",
    "shin",
    "devig",
    "METHODS",
]


def _check(odds: Sequence[float]) -> List[float]:
    odds = list(odds)
    if len(odds) < 2:
        raise ValueError("need at least two outcomes to de-vig")
    if any(o <= 1.0 for o in odds):
        raise ValueError("decimal odds must all be > 1.0")
    return odds


def implied_raw(odds: Sequence[float]) -> List[float]:
    """Raw implied probabilities ``r_i = 1 / o_i`` (these sum to the overround)."""
    odds = _check(odds)
    return [1.0 / o for o in odds]


def overround(odds: Sequence[float]) -> float:
    """Booksum ``M = sum(1 / o_i)``. > 1 for a real (margin-bearing) book."""
    return sum(implied_raw(odds))


def margin(odds: Sequence[float]) -> float:
    """Bookmaker margin ``M - 1`` as a fraction (0.06 == 6%)."""
    return overround(odds) - 1.0


def _bisect(f, lo: float, hi: float, tol: float = 1e-12, maxit: int = 200) -> float:
    """Find a root of monotone ``f`` on [lo, hi] by bisection."""
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        # Not bracketed; return the endpoint nearest zero so callers degrade gracefully.
        return lo if abs(flo) < abs(fhi) else hi
    for _ in range(maxit):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < tol or (hi - lo) < tol:
            return mid
        if (fmid > 0) == (flo > 0):
            lo, flo = mid, fmid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def multiplicative(odds: Sequence[float]) -> List[float]:
    """Proportional normalization: ``p_i = r_i / sum(r)``."""
    r = implied_raw(odds)
    s = sum(r)
    return [x / s for x in r]


def additive(odds: Sequence[float]) -> List[float]:
    """Equal-margin subtraction. May yield negatives on lopsided books;
    we clamp to >= 0 and renormalize so output is always a valid distribution."""
    r = implied_raw(odds)
    n = len(r)
    excess = sum(r) - 1.0
    p = [max(0.0, x - excess / n) for x in r]
    s = sum(p)
    if s <= 0:  # degenerate; fall back to multiplicative
        return multiplicative(odds)
    return [x / s for x in p]


def power(odds: Sequence[float]) -> List[float]:
    """Power method: find exponent ``e`` so ``sum(r_i ** e) == 1`` and return
    ``p_i = r_i ** e``. Always stays in [0, 1]."""
    r = implied_raw(odds)

    def f(e: float) -> float:
        return sum(x ** e for x in r) - 1.0

    # r_i in (0,1); sum(r) = M > 1 at e=1, decreasing in e -> root e >= 1.
    e = _bisect(f, 1.0, 100.0)
    p = [x ** e for x in r]
    s = sum(p)
    return [x / s for x in p]


def odds_ratio(odds: Sequence[float]) -> List[float]:
    """Cheung odds-ratio method: find ``c`` so probabilities
    ``p_i = r_i / (c + r_i - c*r_i)`` sum to 1."""
    r = implied_raw(odds)

    def probs(c: float) -> List[float]:
        return [x / (c + x - c * x) for x in r]

    def f(c: float) -> float:
        return sum(probs(c)) - 1.0

    c = _bisect(f, 1e-6, 1000.0)
    p = probs(c)
    s = sum(p)
    return [x / s for x in p]


def shin(odds: Sequence[float]) -> List[float]:
    """Shin's method. Solve for the insider-money fraction ``z`` so that the
    fair probabilities sum to 1.

    ``p_i = (sqrt(z^2 + 4(1-z) * r_i^2 / M) - z) / (2(1-z))`` with ``M = sum(r)``.
    """
    r = implied_raw(odds)
    M = sum(r)

    def probs(z: float) -> List[float]:
        if z >= 1.0:
            z = 1.0 - 1e-9
        out = []
        for x in r:
            val = math.sqrt(z * z + 4.0 * (1.0 - z) * x * x / M)
            out.append((val - z) / (2.0 * (1.0 - z)))
        return out

    def f(z: float) -> float:
        return sum(probs(z)) - 1.0

    # At z=0, sum == sqrt(M) > 1; decreasing in z -> root in [0, 1).
    z = _bisect(f, 0.0, 0.999)
    p = probs(z)
    s = sum(p)
    return [x / s for x in p]


METHODS = {
    "multiplicative": multiplicative,
    "additive": additive,
    "power": power,
    "odds_ratio": odds_ratio,
    "shin": shin,
}


def devig(odds: Sequence[float], method: str = "shin") -> List[float]:
    """Dispatch to a named de-vig method. Default ``shin`` (academically favoured)."""
    if method not in METHODS:
        raise ValueError(
            f"unknown de-vig method {method!r}; choose from {sorted(METHODS)}"
        )
    return METHODS[method](odds)

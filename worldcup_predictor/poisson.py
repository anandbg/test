"""Dixon-Coles Poisson scoreline model.

Build a matrix ``P(i, j)`` = probability the home team scores ``i`` and the away
team scores ``j``, then read off any market as a sum of cells:

    P(home win) = sum_{i > j}        P(draw) = sum_{i == j}
    P(away win) = sum_{i < j}        each cell P(i, j) is a correct-score prob.

The Dixon-Coles (1997) low-score correction multiplies the four lowest cells by
``tau`` (parameter ``rho``, a small negative number) to fix the well-known
under-prediction of 0-0 and 1-1 draws by independent Poisson.

See RESEARCH.md section 4.
"""

from __future__ import annotations

import math
from typing import List, Tuple

__all__ = [
    "poisson_pmf",
    "dc_tau",
    "score_matrix",
    "outcome_probs",
    "correct_scores",
    "over_under",
    "btts",
    "rescale_to_1x2",
]

Matrix = List[List[float]]


def poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass ``P(X = k)`` for rate ``lam``."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def dc_tau(i: int, j: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles correction factor for the four lowest scorelines."""
    if i == 0 and j == 0:
        return 1.0 - lam * mu * rho
    if i == 0 and j == 1:
        return 1.0 + lam * rho
    if i == 1 and j == 0:
        return 1.0 + mu * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(
    lam_home: float,
    lam_away: float,
    rho: float = -0.13,
    max_goals: int = 10,
) -> Matrix:
    """Return a normalized ``(max_goals+1) x (max_goals+1)`` scoreline matrix.

    ``lam_home`` / ``lam_away`` are the teams' expected goals. ``rho`` is the
    Dixon-Coles dependence parameter (small negative; original ~= -0.13).
    """
    lam_home = max(1e-6, lam_home)
    lam_away = max(1e-6, lam_away)
    home_pmf = [poisson_pmf(i, lam_home) for i in range(max_goals + 1)]
    away_pmf = [poisson_pmf(j, lam_away) for j in range(max_goals + 1)]

    matrix: Matrix = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    total = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = home_pmf[i] * away_pmf[j] * dc_tau(i, j, lam_home, lam_away, rho)
            p = max(0.0, p)  # tau can in principle push a cell slightly negative
            matrix[i][j] = p
            total += p
    if total > 0:
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                matrix[i][j] /= total
    return matrix


def outcome_probs(matrix: Matrix) -> Tuple[float, float, float]:
    """Collapse a scoreline matrix into ``(home_win, draw, away_win)``."""
    home = draw = away = 0.0
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            p = matrix[i][j]
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
    return home, draw, away


def correct_scores(matrix: Matrix, top_n: int = 8) -> List[Tuple[Tuple[int, int], float]]:
    """Most likely exact scorelines as ``((home, away), prob)``, descending."""
    scores = []
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            scores.append(((i, j), matrix[i][j]))
    scores.sort(key=lambda kv: kv[1], reverse=True)
    return scores[:top_n]


def over_under(matrix: Matrix, line: float = 2.5) -> Tuple[float, float]:
    """Return ``(P(total goals > line), P(total goals < line))``.

    Lines are normally half-integers (2.5), so there is no push.
    """
    over = under = 0.0
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            if i + j > line:
                over += matrix[i][j]
            else:
                under += matrix[i][j]
    return over, under


def btts(matrix: Matrix) -> Tuple[float, float]:
    """Both-teams-to-score: ``(P(yes), P(no))``."""
    yes = 0.0
    n = len(matrix)
    for i in range(n):
        for j in range(n):
            if i > 0 and j > 0:
                yes += matrix[i][j]
    return yes, 1.0 - yes


def rescale_to_1x2(
    matrix: Matrix,
    target_home: float,
    target_draw: float,
    target_away: float,
) -> Matrix:
    """Rescale a scoreline matrix so its 1X2 marginals match a target
    (e.g. the ensemble 1X2), keeping the *within-outcome* score shape.

    Lets us anchor correct-score / over-under output to the blended 1X2 result.
    """
    cur_h, cur_d, cur_a = outcome_probs(matrix)
    sh = target_home / cur_h if cur_h > 0 else 0.0
    sd = target_draw / cur_d if cur_d > 0 else 0.0
    sa = target_away / cur_a if cur_a > 0 else 0.0
    n = len(matrix)
    out: Matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i > j:
                out[i][j] = matrix[i][j] * sh
            elif i == j:
                out[i][j] = matrix[i][j] * sd
            else:
                out[i][j] = matrix[i][j] * sa
    total = sum(sum(row) for row in out)
    if total > 0:
        out = [[v / total for v in row] for row in out]
    return out

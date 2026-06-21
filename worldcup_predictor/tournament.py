"""Full-tournament prediction: predict every match + Monte-Carlo the bracket.

Two layers:

1. **Deterministic per-match predictions** for the 72 group-stage games (every
   match has a fixed pairing), via the same ensemble engine.

2. **Monte-Carlo simulation** of the whole tournament to estimate, per team:
   P(win group), P(advance from group), P(reach R16/QF/SF/Final), P(win title).
   Knockout pairings depend on group results, so they can only be simulated.

Group standings tie-breaks follow FIFA order as far as is cheap to compute:
points, goal difference, goals for, then a deterministic Elo fallback.

Data is loaded from ``data/groups_2026.json`` and ``data/bracket_2026.json``.
"""

from __future__ import annotations

import itertools
import random
from typing import Dict, List, Optional, Sequence, Tuple

from .engine import PredictionEngine

# ---------------------------------------------------------------------------
# Per-match (deterministic) prediction
# ---------------------------------------------------------------------------


def group_match_pairings(teams: Sequence[str]) -> List[Tuple[str, str]]:
    """All 6 round-robin pairings for a group of 4 (order is cosmetic)."""
    return list(itertools.combinations(teams, 2))


def predict_group_stage(
    engine: PredictionEngine,
    groups: Dict[str, List[str]],
    hosts: Optional[Sequence[str]] = None,
) -> Dict[str, List[dict]]:
    """Predict every group-stage match.

    Returns ``{group_letter: [match_prediction_dict, ...]}``. Matches are played
    at neutral venues except for host nations, which get home advantage.
    """
    hosts = set(hosts or [])
    out: Dict[str, List[dict]] = {}
    for g, teams in groups.items():
        preds = []
        for home, away in group_match_pairings(teams):
            # Give a host its home edge regardless of nominal home/away ordering.
            neutral = True
            if home in hosts and away not in hosts:
                neutral = False
            elif away in hosts and home not in hosts:
                home, away = away, home
                neutral = False
            p = engine.predict(home, away, neutral=neutral)
            preds.append(
                {
                    "home": home,
                    "away": away,
                    "neutral": neutral,
                    "probs": p.one_x_two,
                    "most_likely": p.most_likely,
                    "lambda_home": p.lambda_home,
                    "lambda_away": p.lambda_away,
                    "top_score": p.correct_scores[0][0],
                    "top_score_prob": p.correct_scores[0][1],
                    "over_2_5": p.over_2_5,
                    "btts_yes": p.btts_yes,
                }
            )
        out[g] = preds
    return out


# ---------------------------------------------------------------------------
# Monte-Carlo machinery (uses precomputed probabilities for speed)
# ---------------------------------------------------------------------------


class _MatchCache:
    """Precomputes and caches match probabilities so the Monte-Carlo loop only
    samples (cheap) instead of rebuilding Poisson matrices (expensive)."""

    def __init__(self, engine: PredictionEngine, hosts: Optional[Sequence[str]] = None):
        self.engine = engine
        self.hosts = set(hosts or [])
        # group match: (home, away, neutral) -> (score_matrix flat list, side)
        self._group: Dict[Tuple[str, str, bool], Tuple[List[float], int]] = {}
        # knockout: frozenset{a,b} -> P(a advances) keyed by sorted order
        self._ko: Dict[Tuple[str, str], float] = {}

    def group_outcome(self, home: str, away: str, neutral: bool, rng: random.Random):
        key = (home, away, neutral)
        cached = self._group.get(key)
        if cached is None:
            pred = self.engine.predict(home, away, neutral=neutral)
            from . import poisson as ps  # local import to avoid cycles at import

            matrix = ps.rescale_to_1x2(
                ps.score_matrix(pred.lambda_home, pred.lambda_away, rho=self.engine.rho,
                                max_goals=self.engine.max_goals),
                *pred.one_x_two,
            )
            n = len(matrix)
            flat = []
            for i in range(n):
                for j in range(n):
                    flat.append(matrix[i][j])
            self._group[key] = (flat, n)
            cached = self._group[key]
        flat, n = cached
        # sample a scoreline index
        r = rng.random()
        acc = 0.0
        idx = len(flat) - 1
        for k, p in enumerate(flat):
            acc += p
            if r <= acc:
                idx = k
                break
        return divmod(idx, n)  # (home_goals, away_goals)

    def advance_prob(self, a: str, b: str) -> float:
        """P(a beats b) in a neutral knockout match (ET/penalties included)."""
        key = (a, b) if a <= b else (b, a)
        val = self._ko.get(key)
        if val is None:
            pred = self.engine.predict(key[0], key[1], neutral=True, knockout=True)
            val = pred.advance_home  # P(key[0] advances)
            self._ko[key] = val
        return val if a <= b else 1.0 - val


def _rank_group(table: Dict[str, dict], engine: PredictionEngine) -> List[str]:
    """Order a group's teams by points, GD, GF, then Elo (deterministic fallback)."""
    def sort_key(team: str):
        t = table[team]
        return (t["pts"], t["gd"], t["gf"], engine.elo.rating(team))
    return sorted(table, key=sort_key, reverse=True)


def _simulate_group(
    teams: List[str],
    cache: _MatchCache,
    hosts: set,
    rng: random.Random,
    engine: PredictionEngine,
):
    table = {t: {"pts": 0, "gd": 0, "gf": 0} for t in teams}
    for home, away in group_match_pairings(teams):
        neutral = True
        h, a = home, away
        if h in hosts and a not in hosts:
            neutral = False
        elif a in hosts and h not in hosts:
            h, a = a, h
            neutral = False
        hg, ag = cache.group_outcome(h, a, neutral, rng)
        table[h]["gf"] += hg
        table[a]["gf"] += ag
        table[h]["gd"] += hg - ag
        table[a]["gd"] += ag - hg
        if hg > ag:
            table[h]["pts"] += 3
        elif hg < ag:
            table[a]["pts"] += 3
        else:
            table[h]["pts"] += 1
            table[a]["pts"] += 1
    ranked = _rank_group(table, engine)
    return ranked, table


def _third_place_score(table_entry: dict, rating: float):
    return (table_entry["pts"], table_entry["gd"], table_entry["gf"], rating)

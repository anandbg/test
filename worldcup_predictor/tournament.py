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


# ---------------------------------------------------------------------------
# Third-place allocation (constrained bipartite matching)
# ---------------------------------------------------------------------------


def assign_thirds(qualifying_groups, third_slots) -> Optional[Dict[int, str]]:
    """Assign the 8 qualifying third-place groups to the 8 winner-vs-third R32
    slots, respecting each slot's allowed-group pool.

    ``third_slots`` is a list of ``(match_id, set_of_allowed_groups)``. Returns
    ``{match_id: group}`` or ``None`` if no perfect matching exists.

    FIFA's Annex C table is the official mapping (designed to avoid rematches);
    any perfect matching satisfies the structural pool constraints, which is
    sufficient for unbiased Monte-Carlo bracket estimates.
    """
    groups = list(qualifying_groups)
    # order slots by fewest options first (constraint propagation)
    slots = sorted(third_slots, key=lambda s: len(s[1] & qualifying_groups))
    assignment: Dict[int, str] = {}
    used = set()

    def backtrack(k: int) -> bool:
        if k == len(slots):
            return True
        mid, pool = slots[k]
        for g in groups:
            if g in pool and g not in used:
                assignment[mid] = g
                used.add(g)
                if backtrack(k + 1):
                    return True
                used.discard(g)
                del assignment[mid]
        return False

    return assignment if backtrack(0) else None


def _resolve_slot(slot, winners, runners, third_by_group, third_assignment, match_id):
    """Resolve an R32 slot spec to a concrete team."""
    if "w" in slot:
        return winners[slot["w"]]
    if "r" in slot:
        return runners[slot["r"]]
    if "t" in slot:
        g = third_assignment.get(match_id)
        return third_by_group.get(g) if g is not None else None
    raise ValueError(f"bad slot spec: {slot}")


# ---------------------------------------------------------------------------
# Full-tournament Monte-Carlo
# ---------------------------------------------------------------------------

_STAGES = ("reach_r32", "reach_r16", "reach_qf", "reach_sf", "reach_final", "champion")


def simulate_tournament(
    engine: PredictionEngine,
    groups_data: dict,
    bracket: dict,
    n_sims: int = 20000,
    seed: int = 12345,
):
    """Monte-Carlo the whole tournament; return per-team stage probabilities
    and per-group winner/runner/advance probabilities.
    """
    groups = groups_data["groups"]
    hosts = set(groups_data.get("hosts", []))
    rng = random.Random(seed)
    cache = _MatchCache(engine, hosts)

    teams = [t for g in groups.values() for t in g]
    stage = {t: {s: 0 for s in _STAGES} for t in teams}
    group_stat = {
        g: {t: {"win": 0, "runner": 0, "advance": 0} for t in gteams}
        for g, gteams in groups.items()
    }

    third_slots = [
        (m["id"], set(m["b"]["t"]))
        for m in bracket["r32"]
        if "t" in m["b"]
    ]

    # later-round matches reference earlier results as "W##" / "L##"
    later_rounds = bracket["r16"] + bracket["qf"] + bracket["sf"] + [bracket["final"]]

    for _ in range(n_sims):
        winners: Dict[str, str] = {}
        runners: Dict[str, str] = {}
        thirds = []  # (group, team, score)

        for g, gteams in groups.items():
            ranked, table = _simulate_group(gteams, cache, hosts, rng, engine)
            winners[g], runners[g] = ranked[0], ranked[1]
            group_stat[g][ranked[0]]["win"] += 1
            group_stat[g][ranked[0]]["advance"] += 1
            group_stat[g][ranked[1]]["runner"] += 1
            group_stat[g][ranked[1]]["advance"] += 1
            third = ranked[2]
            thirds.append(
                (g, third, _third_place_score(table[third], engine.elo.rating(third)))
            )

        thirds.sort(key=lambda x: x[2], reverse=True)
        qual = thirds[:8]
        qual_groups = {g for g, _, _ in qual}
        third_by_group = {g: t for g, t, _ in qual}
        for g, t, _ in qual:
            group_stat[g][t]["advance"] += 1

        assignment = assign_thirds(qual_groups, third_slots) or {}

        # --- seed and play the Round of 32 -------------------------------
        win_of: Dict[int, str] = {}
        lose_of: Dict[int, str] = {}
        for m in bracket["r32"]:
            a = _resolve_slot(m["a"], winners, runners, third_by_group, assignment, m["id"])
            b = _resolve_slot(m["b"], winners, runners, third_by_group, assignment, m["id"])
            if a is None or b is None:  # assignment fell through (rare); skip safely
                continue
            stage[a]["reach_r32"] += 1
            stage[b]["reach_r32"] += 1
            w, l = _play(a, b, cache, rng)
            win_of[m["id"]], lose_of[m["id"]] = w, l
            stage[w]["reach_r16"] += 1

        # --- remaining rounds -------------------------------------------
        # map a match id to the stage credited to its winner
        def winner_stage(mid: int) -> Optional[str]:
            if 89 <= mid <= 96:
                return "reach_qf"
            if 97 <= mid <= 100:
                return "reach_sf"
            if 101 <= mid <= 102:
                return "reach_final"
            if mid == 104:
                return "champion"
            return None

        for m in later_rounds:
            a = _ref(m["a"], win_of, lose_of)
            b = _ref(m["b"], win_of, lose_of)
            if a is None or b is None:
                continue
            w, l = _play(a, b, cache, rng)
            win_of[m["id"]], lose_of[m["id"]] = w, l
            st = winner_stage(m["id"])
            if st:
                stage[w][st] += 1

    # normalize to probabilities
    def norm(d):
        return {k: v / n_sims for k, v in d.items()}

    team_probs = {t: norm(stage[t]) for t in teams}
    group_probs = {
        g: {t: {k: v / n_sims for k, v in group_stat[g][t].items()} for t in group_stat[g]}
        for g in groups
    }
    return {"n_sims": n_sims, "teams": team_probs, "groups": group_probs}


def _play(a: str, b: str, cache: _MatchCache, rng: random.Random):
    """Sample a knockout winner; return (winner, loser)."""
    p_a = cache.advance_prob(a, b)
    if rng.random() < p_a:
        return a, b
    return b, a


def _ref(ref: str, win_of, lose_of):
    """Resolve a 'W##' / 'L##' reference to a team."""
    kind, mid = ref[0], int(ref[1:])
    return win_of.get(mid) if kind == "W" else lose_of.get(mid)

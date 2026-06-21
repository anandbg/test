"""World Football Elo ratings for international teams.

Implements the eloratings.net update rule so the engine can *learn* team strength
from actual results, then convert a rating difference into an expected result and
expected goal supremacy (which the Poisson model turns into a full scoreline).

  R' = R + K * G * (W - We)
  We = 1 / (1 + 10 ** (-dr / 400)),  dr = (R_home - R_away) + home_advantage
  W  = 1 win / 0.5 draw / 0 loss
  K  = importance weight (60 WC finals, 50, 40, 30, 20 friendlies)
  G  = goal-difference multiplier

See RESEARCH.md sections 2 & 5.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

__all__ = ["EloModel", "IMPORTANCE_K"]

# K-factor by match importance (World Football Elo conventions).
IMPORTANCE_K = {
    "world_cup": 60,
    "continental_final": 50,
    "major_tournament": 40,
    "qualifier": 40,
    "minor_tournament": 30,
    "friendly": 20,
}


def goal_difference_multiplier(goal_diff: int) -> float:
    """G: 1 -> x1, 2 -> x1.5, 3 -> x1.75, N>=4 -> x(1.75 + (N-3)/8)."""
    n = abs(goal_diff)
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.5
    if n == 3:
        return 1.75
    return 1.75 + (n - 3) / 8.0


def expected_result(rating_diff: float) -> float:
    """We in [0,1] from an (already home-adjusted) rating difference."""
    return 1.0 / (1.0 + 10.0 ** (-rating_diff / 400.0))


class EloModel:
    """A mutable table of national-team Elo ratings.

    Parameters
    ----------
    default_rating: rating assigned to a team seen for the first time.
    home_advantage: Elo points added to the home side (0 for neutral venues).
    """

    def __init__(
        self,
        ratings: Optional[Dict[str, float]] = None,
        default_rating: float = 1500.0,
        home_advantage: float = 100.0,
    ) -> None:
        self.ratings: Dict[str, float] = dict(ratings or {})
        self.default_rating = default_rating
        self.home_advantage = home_advantage

    # -- access ---------------------------------------------------------------
    def rating(self, team: str) -> float:
        return self.ratings.get(team, self.default_rating)

    def set_rating(self, team: str, value: float) -> None:
        self.ratings[team] = value

    # -- prediction -----------------------------------------------------------
    def expected(self, home: str, away: str, neutral: bool = False) -> float:
        """We for the home team (counts a draw as 0.5)."""
        adv = 0.0 if neutral else self.home_advantage
        dr = self.rating(home) - self.rating(away) + adv
        return expected_result(dr)

    def rating_diff(self, home: str, away: str, neutral: bool = False) -> float:
        adv = 0.0 if neutral else self.home_advantage
        return self.rating(home) - self.rating(away) + adv

    # -- learning -------------------------------------------------------------
    def update_match(
        self,
        home: str,
        away: str,
        home_goals: int,
        away_goals: int,
        importance: str = "friendly",
        neutral: bool = False,
    ) -> Tuple[float, float]:
        """Apply one result and return the teams' new ratings.

        Both teams move by an equal and opposite amount (zero-sum).
        """
        k = IMPORTANCE_K.get(importance, 20)
        adv = 0.0 if neutral else self.home_advantage
        rh, ra = self.rating(home), self.rating(away)
        we_home = expected_result(rh - ra + adv)

        if home_goals > away_goals:
            w_home = 1.0
        elif home_goals == away_goals:
            w_home = 0.5
        else:
            w_home = 0.0

        g = goal_difference_multiplier(home_goals - away_goals)
        delta = k * g * (w_home - we_home)
        self.ratings[home] = rh + delta
        self.ratings[away] = ra - delta
        return self.ratings[home], self.ratings[away]

    def fit(self, matches: Iterable[dict]) -> "EloModel":
        """Process an iterable of match dicts (in chronological order).

        Each dict needs: home, away, home_goals, away_goals, and optionally
        importance and neutral.
        """
        for m in matches:
            self.update_match(
                m["home"],
                m["away"],
                int(m["home_goals"]),
                int(m["away_goals"]),
                importance=m.get("importance", "friendly"),
                neutral=bool(m.get("neutral", False)),
            )
        return self

    def top(self, n: int = 20):
        """Return the ``n`` highest-rated teams as ``(team, rating)``."""
        return sorted(self.ratings.items(), key=lambda kv: kv[1], reverse=True)[:n]

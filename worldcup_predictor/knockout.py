"""Knockout-stage handling: there is no draw in the bracket.

A 90-minute draw goes to extra time and then penalties, so we convert the
90-minute 1X2 probabilities into "probability each team advances".

P(home advances) = P(home win90) + P(draw90) * P(home wins ET/pens | draw90)

The conditional ET/penalty winner is modelled as close to a coin flip, nudged by
the stronger team's expected-result edge. Penalty shootouts in particular are
famously near-random, so the nudge is deliberately shallow.

See RESEARCH.md section 4.
"""

from __future__ import annotations

from typing import Tuple

__all__ = ["advance_probability", "PENALTY_FLATTEN"]

# How strongly relative strength tilts a drawn-after-90 match. 1.0 == use the
# full expected-result edge; lower values flatten toward a coin flip to reflect
# the high randomness of extra time + penalties.
PENALTY_FLATTEN = 0.5


def advance_probability(
    p_home_win: float,
    p_draw: float,
    p_away_win: float,
    we_home: float = 0.5,
    flatten: float = PENALTY_FLATTEN,
) -> Tuple[float, float]:
    """Return ``(P(home advances), P(away advances))``.

    ``we_home`` is the home team's Elo expected result (0.5 == evenly matched);
    it decides who is favoured if the match is level after 90 minutes.
    """
    # Tilt the coin flip toward the stronger side, but only partially.
    cond_home = 0.5 + flatten * (we_home - 0.5)
    cond_home = min(1.0, max(0.0, cond_home))

    home_adv = p_home_win + p_draw * cond_home
    away_adv = p_away_win + p_draw * (1.0 - cond_home)

    total = home_adv + away_adv
    if total > 0:
        home_adv /= total
        away_adv /= total
    return home_adv, away_adv

"""The prediction engine: market odds + Elo + Dixon-Coles Poisson -> one forecast.

Pipeline (see RESEARCH.md):
  1. De-vig the bookmaker 1X2 odds (if supplied)            -> market probabilities
  2. Elo rating diff -> expected goal supremacy -> Poisson   -> model probabilities
                        + Dixon-Coles low-score correction      and a scoreline matrix
  3. Logarithmic pool of (market, model), market-weighted    -> ensemble 1X2
  4. Anchor the scoreline matrix to the ensemble 1X2         -> correct scores, O/U, BTTS
  5. Knockout? convert 90-min 1X2 into advance probabilities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import devig as devig_mod
from . import ensemble as ens
from . import knockout as ko
from . import poisson as ps
from .elo import EloModel, expected_result

OUTCOMES = ("home", "draw", "away")


@dataclass
class Prediction:
    """The full forecast for a single match."""

    home: str
    away: str
    neutral: bool
    knockout: bool

    # 1X2 (the headline numbers), as probabilities summing to 1
    prob_home: float
    prob_draw: float
    prob_away: float

    # component forecasts (for transparency / debugging)
    market_probs: Optional[Tuple[float, float, float]]
    model_probs: Tuple[float, float, float]
    market_weight: float

    # expected goals used by the model
    lambda_home: float
    lambda_away: float

    # derived markets, anchored to the ensemble 1X2
    correct_scores: List[Tuple[Tuple[int, int], float]]
    over_2_5: float
    under_2_5: float
    btts_yes: float
    btts_no: float

    # knockout only
    advance_home: Optional[float] = None
    advance_away: Optional[float] = None

    extras: Dict[str, float] = field(default_factory=dict)

    @property
    def one_x_two(self) -> Tuple[float, float, float]:
        return (self.prob_home, self.prob_draw, self.prob_away)

    @property
    def most_likely(self) -> str:
        probs = self.one_x_two
        return OUTCOMES[max(range(3), key=lambda i: probs[i])]

    def summary(self) -> str:
        """Human-readable multi-line report."""
        venue = "neutral venue" if self.neutral else f"{self.home} at home"
        stage = "knockout" if self.knockout else "group/league"
        lines = [
            f"{self.home} vs {self.away}  ({venue}, {stage})",
            "-" * 56,
            f"  {self.home:<22} win : {self.prob_home*100:5.1f}%",
            f"  {'Draw':<22}     : {self.prob_draw*100:5.1f}%",
            f"  {self.away:<22} win : {self.prob_away*100:5.1f}%",
            f"  -> most likely (1X2)    : {self.most_likely.upper()}",
            "",
            f"  expected goals          : {self.home} {self.lambda_home:.2f}"
            f" - {self.lambda_away:.2f} {self.away}",
            f"  over 2.5 / under 2.5    : {self.over_2_5*100:4.1f}% / {self.under_2_5*100:4.1f}%",
            f"  both teams to score     : {self.btts_yes*100:4.1f}% yes / {self.btts_no*100:4.1f}% no",
        ]
        if self.market_probs is not None:
            mh, md, ma = self.market_probs
            gh, gd, ga = self.model_probs
            lines += [
                "",
                f"  components (market weight {self.market_weight:.2f}):",
                f"     market : {mh*100:4.1f}% / {md*100:4.1f}% / {ma*100:4.1f}%",
                f"     model  : {gh*100:4.1f}% / {gd*100:4.1f}% / {ga*100:4.1f}%",
            ]
        lines += ["", "  most likely scorelines:"]
        for (i, j), p in self.correct_scores[:5]:
            lines.append(f"     {i}-{j} : {p*100:4.1f}%")
        if self.knockout:
            lines += [
                "",
                f"  to advance (after ET/pens):",
                f"     {self.home:<22}: {self.advance_home*100:5.1f}%",
                f"     {self.away:<22}: {self.advance_away*100:5.1f}%",
            ]
        return "\n".join(lines)


class PredictionEngine:
    """Configurable engine combining market odds with an Elo/Poisson model.

    Parameters
    ----------
    elo: an EloModel holding national-team ratings (optional; defaults to empty,
        which makes the model component neutral unless ratings are passed in).
    market_weight: weight on the de-vigged market in the log pool (0..1). 0.65
        reflects the empirical dominance of market odds.
    devig_method: one of devig.METHODS ('shin' recommended).
    rho: Dixon-Coles dependence parameter (small negative).
    mu_total: baseline expected total goals for an even match (international ~2.6).
    elo_to_supremacy: goals of expected supremacy per Elo point of (adjusted)
        rating difference. Default 1/350 ~= 1.14 goals per 400 Elo.
    max_goals: scoreline matrix truncation.
    """

    def __init__(
        self,
        elo: Optional[EloModel] = None,
        market_weight: float = 0.65,
        devig_method: str = "shin",
        rho: float = -0.13,
        mu_total: float = 2.6,
        elo_to_supremacy: float = 1.0 / 350.0,
        max_goals: int = 10,
    ) -> None:
        if not 0.0 <= market_weight <= 1.0:
            raise ValueError("market_weight must be in [0, 1]")
        self.elo = elo if elo is not None else EloModel()
        self.market_weight = market_weight
        self.devig_method = devig_method
        self.rho = rho
        self.mu_total = mu_total
        self.elo_to_supremacy = elo_to_supremacy
        self.max_goals = max_goals

    # -- expected goals from Elo ---------------------------------------------
    def _lambdas(self, rating_diff: float) -> Tuple[float, float]:
        """Split baseline total goals by Elo supremacy into (home, away) lambdas."""
        supremacy = self.elo_to_supremacy * rating_diff
        # keep supremacy within the achievable range of the total
        supremacy = max(-self.mu_total + 0.3, min(self.mu_total - 0.3, supremacy))
        lam_home = max(0.15, (self.mu_total + supremacy) / 2.0)
        lam_away = max(0.15, (self.mu_total - supremacy) / 2.0)
        return lam_home, lam_away

    # -- main entry point -----------------------------------------------------
    def predict(
        self,
        home: str,
        away: str,
        market_odds: Optional[Sequence[float]] = None,
        home_rating: Optional[float] = None,
        away_rating: Optional[float] = None,
        neutral: bool = False,
        knockout: bool = False,
        market_weight: Optional[float] = None,
    ) -> Prediction:
        """Predict one match.

        ``market_odds`` is ``[home, draw, away]`` decimal odds (optional). If
        omitted, the forecast is model-only. ``home_rating`` / ``away_rating``
        override the EloModel's stored ratings if given.
        """
        w_market = self.market_weight if market_weight is None else market_weight

        # --- model component (Elo -> Poisson scoreline matrix) ---------------
        rh = home_rating if home_rating is not None else self.elo.rating(home)
        ra = away_rating if away_rating is not None else self.elo.rating(away)
        adv = 0.0 if neutral else self.elo.home_advantage
        rating_diff = rh - ra + adv
        we_home = expected_result(rating_diff)

        lam_home, lam_away = self._lambdas(rating_diff)
        matrix = ps.score_matrix(lam_home, lam_away, rho=self.rho, max_goals=self.max_goals)
        model_probs = ps.outcome_probs(matrix)

        # --- market component (de-vig) ---------------------------------------
        market_probs: Optional[Tuple[float, float, float]] = None
        if market_odds is not None:
            mp = devig_mod.devig(market_odds, method=self.devig_method)
            if len(mp) != 3:
                raise ValueError("market_odds must have exactly 3 outcomes (home/draw/away)")
            market_probs = (mp[0], mp[1], mp[2])

        # --- ensemble (log pool) ---------------------------------------------
        if market_probs is not None and w_market > 0.0:
            final = ens.log_pool(
                [list(market_probs), list(model_probs)],
                [w_market, 1.0 - w_market],
            )
        else:
            final = list(model_probs)
        ph, pd, pa = final

        # --- derived markets anchored to ensemble 1X2 ------------------------
        anchored = ps.rescale_to_1x2(matrix, ph, pd, pa)
        cs = ps.correct_scores(anchored, top_n=8)
        over, under = ps.over_under(anchored, 2.5)
        byes, bno = ps.btts(anchored)

        pred = Prediction(
            home=home,
            away=away,
            neutral=neutral,
            knockout=knockout,
            prob_home=ph,
            prob_draw=pd,
            prob_away=pa,
            market_probs=market_probs,
            model_probs=model_probs,
            market_weight=w_market if market_probs is not None else 0.0,
            lambda_home=lam_home,
            lambda_away=lam_away,
            correct_scores=cs,
            over_2_5=over,
            under_2_5=under,
            btts_yes=byes,
            btts_no=bno,
        )

        if knockout:
            ah, aa = ko.advance_probability(ph, pd, pa, we_home=we_home)
            pred.advance_home = ah
            pred.advance_away = aa

        return pred

"""World Cup football match prediction engine.

A market-anchored ensemble that de-vigs bookmaker odds, blends them with a
World-Football-Elo + Dixon-Coles-Poisson model via logarithmic pooling, and
produces calibrated 1X2, correct-score, over/under, BTTS and knockout-advance
probabilities.

See RESEARCH.md for the evidence behind the design.
"""

from .engine import PredictionEngine, Prediction
from .elo import EloModel
from . import devig, poisson, ensemble, knockout, metrics

__all__ = [
    "PredictionEngine",
    "Prediction",
    "EloModel",
    "devig",
    "poisson",
    "ensemble",
    "knockout",
    "metrics",
]

__version__ = "0.1.0"

"""Quickstart: predict a few World Cup matches and print full reports.

Run from the repo root:  python examples/quickstart.py
"""

import os
import sys

# Make the repo root importable when run as a script (no install required).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldcup_predictor import PredictionEngine
from worldcup_predictor.datasets import load_elo

engine = PredictionEngine(elo=load_elo(), market_weight=0.65, devig_method="shin")

# (home, away, [home, draw, away] decimal odds or None, neutral, knockout)
fixtures = [
    ("Argentina", "France", [2.40, 3.20, 3.10], True, True),   # a final, with odds
    ("Spain", "Germany", [2.70, 3.30, 2.60], True, False),     # group game, with odds
    ("Brazil", "Croatia", None, True, True),                   # knockout, model-only
]

for home, away, odds, neutral, knockout in fixtures:
    pred = engine.predict(
        home, away, market_odds=odds, neutral=neutral, knockout=knockout
    )
    print(pred.summary())
    print()

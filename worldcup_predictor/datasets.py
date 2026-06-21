"""Loaders for ratings and historical match/odds data.

Keeps the engine usable offline (bundled seed ratings + sample results) while
documenting how to plug in the real free datasets listed in RESEARCH.md:

  - football-data.co.uk  : league results + bookmaker odds CSVs (back-testing)
  - martj42/international_results : all internationals 1872-present (Elo training)
  - The Odds API / football-data.org : live odds & fixtures (online)
"""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

from .elo import EloModel

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")
SEED_RATINGS = os.path.join(DATA_DIR, "elo_ratings.json")
SAMPLE_MATCHES = os.path.join(DATA_DIR, "sample_matches.csv")


def load_seed_ratings(path: str = SEED_RATINGS) -> Dict[str, float]:
    """Load the bundled (or a custom) team -> Elo rating map."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: float(v) for k, v in raw.items() if not k.startswith("_")}


def load_elo(path: str = SEED_RATINGS, home_advantage: float = 100.0) -> EloModel:
    """Build an EloModel from a ratings JSON file."""
    return EloModel(ratings=load_seed_ratings(path), home_advantage=home_advantage)


def _result_index(home_goals: int, away_goals: int) -> int:
    """0 home win, 1 draw, 2 away win."""
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def load_matches(path: str = SAMPLE_MATCHES) -> List[dict]:
    """Load a results+odds CSV.

    Expected columns (header row):
        home, away, home_goals, away_goals,
        odds_home, odds_draw, odds_away   (decimal; optional),
        importance (optional), neutral (optional 0/1)

    Returns a list of dicts with parsed types plus a derived ``outcome`` index.
    This format is a simplified superset of football-data.co.uk's columns; map
    their B365H/B365D/B365A into odds_home/draw/away to back-test on real data.
    """
    matches: List[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            hg = int(row["home_goals"])
            ag = int(row["away_goals"])
            m = {
                "home": row["home"].strip(),
                "away": row["away"].strip(),
                "home_goals": hg,
                "away_goals": ag,
                "importance": (row.get("importance") or "friendly").strip(),
                "neutral": str(row.get("neutral", "0")).strip() in ("1", "true", "True"),
                "outcome": _result_index(hg, ag),
            }
            odds = _parse_odds(row)
            if odds is not None:
                m["odds"] = odds
            matches.append(m)
    return matches


def _parse_odds(row: dict) -> Optional[List[float]]:
    keys = ("odds_home", "odds_draw", "odds_away")
    if not all(row.get(k) not in (None, "") for k in keys):
        return None
    try:
        return [float(row[k]) for k in keys]
    except (TypeError, ValueError):
        return None

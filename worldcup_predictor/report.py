"""Generate a full WC2026 predictions report (PREDICTIONS.md).

Predicts every group-stage match with the ensemble engine and Monte-Carlos the
whole bracket for advancement / title probabilities, then writes a markdown
report.

Run:  python -m worldcup_predictor report [output_path] [n_sims]
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List

from .datasets import load_bracket_2026, load_groups_2026, RATINGS_2026
from .elo import EloModel
from .engine import PredictionEngine
from . import tournament as tmt
from . import datasets


def build_engine(home_advantage: float = 60.0) -> PredictionEngine:
    """Engine for tournament use. Home advantage is modest (only hosts get it,
    and even then a World Cup crowd edge is smaller than a club home game)."""
    ratings = datasets.load_seed_ratings(RATINGS_2026)
    elo = EloModel(ratings=ratings, home_advantage=home_advantage)
    # No per-match odds for 104 fixtures -> model-only (market_weight ignored
    # when no odds are supplied). Odds can be passed per-match via the engine.
    return PredictionEngine(elo=elo, mu_total=2.6)


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%" if x >= 0.095 else f"{x * 100:.1f}%"


def _fav(probs):
    h, d, a = probs
    if h >= d and h >= a:
        return "1"
    if a >= h and a >= d:
        return "2"
    return "X"


def generate(out_path: str = "PREDICTIONS.md", n_sims: int = 20000) -> str:
    groups_data = load_groups_2026()
    bracket = load_bracket_2026()
    groups = groups_data["groups"]
    hosts = groups_data["hosts"]
    engine = build_engine()

    match_preds = tmt.predict_group_stage(engine, groups, hosts=hosts)
    sim = tmt.simulate_tournament(engine, groups_data, bracket, n_sims=n_sims)

    teams = sim["teams"]
    today = _dt.date(2026, 6, 21).isoformat()

    L: List[str] = []
    w = L.append

    w("# 2026 FIFA World Cup — Match Predictions\n")
    w(f"*Generated {today} · hosts: USA, Mexico, Canada · 48 teams, 104 matches*\n")
    w("> **These are calibrated model probabilities, not certainties.** A World "
      "Cup is high-variance: the pre-tournament favourite typically has only a "
      "~15–25% chance of winning the whole thing, and ~1 group match in 3 is an "
      "upset. Use these as odds, not predictions of fact.\n")

    # -- methodology -------------------------------------------------------
    w("## How these were produced\n")
    w("- **Engine:** World-Football-Elo ratings → expected goal supremacy → "
      "Dixon–Coles Poisson scoreline matrix (1X2, scores, over/under, BTTS). "
      "See `RESEARCH.md` for the evidence base.\n")
    w("- **Tournament:** a 20,000-run Monte-Carlo simulation of all 104 matches "
      "(group stage + the verified knockout bracket, including the 8-best-third "
      "rule) gives each team's advancement and title probabilities.\n")
    w("- **Model-only:** per-match bookmaker odds for 104 fixtures aren't "
      "feasibly collected here, so the market component is off; the engine runs "
      "on ratings alone. Feed `--odds` per match for the market-anchored ensemble.\n")
    w("- **Ratings caveat:** Elo values are an approximate June-2026 snapshot "
      "(top teams high-confidence; lower tier interpolated from FIFA ranking, as "
      "eloratings.net was unreachable). Swap in the live table to refine.\n")

    # -- title contenders --------------------------------------------------
    w("## Title & deep-run probabilities (top 16)\n")
    ranked = sorted(teams, key=lambda t: teams[t]["champion"], reverse=True)
    w("| # | Team | Champion | Final | Semi | Quarter | Last 16 |")
    w("|---|------|---------:|------:|-----:|--------:|--------:|")
    for i, t in enumerate(ranked[:16], 1):
        p = teams[t]
        w(f"| {i} | {t} | {_pct(p['champion'])} | {_pct(p['reach_final'])} | "
          f"{_pct(p['reach_sf'])} | {_pct(p['reach_qf'])} | {_pct(p['reach_r16'])} |")
    w("")

    # -- groups ------------------------------------------------------------
    w("## Group-by-group\n")
    for g in sorted(groups):
        gteams = groups[g]
        w(f"### Group {g}\n")
        gp = sim["groups"][g]
        order = sorted(gteams, key=lambda t: (gp[t]["advance"], gp[t]["win"]), reverse=True)
        w("**Projected finish** (probability to win group / advance to knockouts):\n")
        w("| Team | Win group | Advance |")
        w("|------|----------:|--------:|")
        for t in order:
            w(f"| {t} | {_pct(gp[t]['win'])} | {_pct(gp[t]['advance'])} |")
        w("\n**Match predictions:**\n")
        w("| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |")
        w("|-------|---------:|-----:|---------:|:------:|:---------:|----:|")
        for m in match_preds[g]:
            h, d, a = m["probs"]
            host_tag = " *(host)*" if not m["neutral"] else ""
            ms = f"{m['home']}{host_tag} v {m['away']}"
            sc = f"{m['top_score'][0]}–{m['top_score'][1]}"
            w(f"| {ms} | {_pct(h)} | {_pct(d)} | {_pct(a)} | "
              f"{_fav(m['probs'])} | {sc} | {_pct(m['over_2_5'])} |")
        w("")

    # -- footer ------------------------------------------------------------
    w("## Notes\n")
    w("- **1 / X / 2** = home win / draw / away win. *Likely* is the single most "
      "probable 1X2 outcome (often the favourite even when <50%).\n")
    w("- Knockout ties are decided in the simulation by 90-minute probabilities "
      "plus an extra-time/penalty coin-flip nudged by team strength.\n")
    w("- The third-place qualifiers are seeded into the Round of 32 by a "
      "constrained matching consistent with FIFA's combination-table pools.\n")
    w("- Regenerate any time with `python -m worldcup_predictor report`. Refresh "
      "`data/elo_ratings_2026.json` from eloratings.net for sharper numbers.\n")

    text = "\n".join(L)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return out_path


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    out = argv[0] if argv else "PREDICTIONS.md"
    n = int(argv[1]) if len(argv) > 1 else 20000
    path = generate(out, n_sims=n)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

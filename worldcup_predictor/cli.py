"""Command-line interface for the World Cup prediction engine.

Examples
--------
Predict from bookmaker odds + bundled Elo ratings:
    python -m worldcup_predictor predict --home Argentina --away France \\
        --odds 2.40 3.20 3.10 --neutral --knockout

Model-only (no odds), using bundled ratings:
    python -m worldcup_predictor predict --home Brazil --away Croatia --neutral

Show the current Elo table / run the sample back-test:
    python -m worldcup_predictor ratings
    python -m worldcup_predictor backtest
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .backtest import main as backtest_main
from .datasets import load_elo
from .engine import PredictionEngine


def _build_engine(args) -> PredictionEngine:
    elo = load_elo(home_advantage=args.home_advantage)
    return PredictionEngine(
        elo=elo,
        market_weight=args.market_weight,
        devig_method=args.devig,
        rho=args.rho,
        mu_total=args.mu_total,
    )


def cmd_predict(args) -> int:
    engine = _build_engine(args)
    odds: Optional[List[float]] = args.odds
    if odds is not None and len(odds) != 3:
        print("error: --odds needs exactly 3 values: home draw away", file=sys.stderr)
        return 2

    # Warn (don't fail) if a team isn't in the ratings table.
    for team in (args.home, args.away):
        if team not in engine.elo.ratings:
            print(
                f"note: '{team}' not in ratings table; using default "
                f"{engine.elo.default_rating:.0f}",
                file=sys.stderr,
            )

    pred = engine.predict(
        home=args.home,
        away=args.away,
        market_odds=odds,
        neutral=args.neutral,
        knockout=args.knockout,
    )
    print(pred.summary())
    return 0


def cmd_ratings(args) -> int:
    elo = load_elo()
    print(f"{'Team':<22} Elo")
    print("-" * 30)
    for team, r in elo.top(n=args.top):
        print(f"{team:<22} {r:.0f}")
    return 0


def cmd_backtest(args) -> int:
    backtest_main()
    return 0


def cmd_report(args) -> int:
    from .report import generate
    path = generate(args.output, n_sims=args.sims)
    print(f"wrote {path} ({args.sims} simulations)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worldcup_predictor",
        description="Predict World Cup match outcomes from odds + Elo/Poisson model.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("predict", help="predict a single match")
    pp.add_argument("--home", required=True, help="home (or first) team")
    pp.add_argument("--away", required=True, help="away (or second) team")
    pp.add_argument(
        "--odds", type=float, nargs=3, metavar=("HOME", "DRAW", "AWAY"),
        default=None, help="decimal bookmaker 1X2 odds (optional)",
    )
    pp.add_argument("--neutral", action="store_true", help="neutral venue (no home advantage)")
    pp.add_argument("--knockout", action="store_true", help="knockout match (report advance %)")
    pp.add_argument("--market-weight", type=float, default=0.65, dest="market_weight",
                    help="weight on the market in the log pool (0..1, default 0.65)")
    pp.add_argument("--devig", default="shin",
                    choices=["shin", "power", "multiplicative", "additive", "odds_ratio"],
                    help="de-vig method (default shin)")
    pp.add_argument("--rho", type=float, default=-0.13, help="Dixon-Coles rho (default -0.13)")
    pp.add_argument("--mu-total", type=float, default=2.6, dest="mu_total",
                    help="baseline expected total goals (default 2.6)")
    pp.add_argument("--home-advantage", type=float, default=100.0, dest="home_advantage",
                    help="Elo home advantage points (default 100)")
    pp.set_defaults(func=cmd_predict)

    pr = sub.add_parser("ratings", help="show the bundled Elo ratings table")
    pr.add_argument("--top", type=int, default=20, help="how many teams to show")
    pr.set_defaults(func=cmd_ratings)

    pb = sub.add_parser("backtest", help="run the sample back-test")
    pb.set_defaults(func=cmd_backtest)

    prep = sub.add_parser("report", help="generate the full WC2026 PREDICTIONS.md report")
    prep.add_argument("--output", default="PREDICTIONS.md", help="output path")
    prep.add_argument("--sims", type=int, default=20000, help="Monte-Carlo runs")
    prep.set_defaults(func=cmd_report)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

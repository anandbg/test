"""Back-test: score market-only vs model-only vs ensemble on historical matches.

Demonstrates the central claim of RESEARCH.md: the de-vigged market is the
strongest single component, and a market-weighted log-pool ensemble is at least
as good while adding correct-score / O/U / BTTS structure the raw odds lack.

Run:  python -m worldcup_predictor.backtest
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from . import devig as devig_mod
from . import ensemble as ens
from . import metrics
from .datasets import load_elo, load_matches
from .engine import PredictionEngine


def _model_probs(engine: PredictionEngine, m: dict) -> Tuple[float, float, float]:
    pred = engine.predict(
        m["home"], m["away"],
        market_odds=None,
        neutral=m.get("neutral", False),
    )
    return pred.one_x_two


def run_backtest(
    matches: Optional[List[dict]] = None,
    engine: Optional[PredictionEngine] = None,
    market_weights: Sequence[float] = (0.5, 0.65, 0.8),
    devig_method: str = "shin",
) -> dict:
    """Return metric dicts for each strategy + a sweep over market weights."""
    if matches is None:
        matches = load_matches()
    if engine is None:
        engine = PredictionEngine(elo=load_elo(), devig_method=devig_method)

    with_odds = [m for m in matches if "odds" in m]
    outcomes = [m["outcome"] for m in with_odds]

    market_f: List[List[float]] = []
    model_f: List[List[float]] = []
    for m in with_odds:
        market_f.append(devig_mod.devig(m["odds"], method=devig_method))
        model_f.append(list(_model_probs(engine, m)))

    results = {
        "n": len(with_odds),
        "market_only": metrics.evaluate(market_f, outcomes),
        "model_only": metrics.evaluate(model_f, outcomes),
        "ensemble": {},
    }
    for w in market_weights:
        pooled = [
            ens.log_pool([mk, md], [w, 1.0 - w])
            for mk, md in zip(market_f, model_f)
        ]
        results["ensemble"][w] = metrics.evaluate(pooled, outcomes)
    return results


def _fmt(d: dict) -> str:
    return (
        f"n={d['n']:>3}  RPS={d['rps']:.4f}  Brier={d['brier']:.4f}  "
        f"logloss={d['log_loss']:.4f}  hit={d['hit_rate']*100:4.1f}%"
    )


def main() -> None:
    res = run_backtest()
    print("Back-test on bundled sample (World Cup 2022 group stage, approx odds)")
    print("Lower RPS / Brier / log-loss is better.\n")
    print(f"  market only   : {_fmt(res['market_only'])}")
    print(f"  model only    : {_fmt(res['model_only'])}")
    for w, d in res["ensemble"].items():
        print(f"  ensemble w={w:<4}: {_fmt(d)}")
    print(
        "\nNote: a ~20-match sample is far too small for statistical significance;"
        "\nthis demonstrates the pipeline. Back-test on football-data.co.uk CSVs"
        "\n(thousands of matches) for real evaluation."
    )


if __name__ == "__main__":
    main()

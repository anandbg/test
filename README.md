# World Cup Match Prediction Engine

A football match-outcome prediction engine for the FIFA World Cup. It implements
the strategy that the research literature actually supports: **anchor on the
de-vigged bookmaker market, add a World-Football-Elo + Dixon–Coles-Poisson model
as a second opinion, and blend them with logarithmic opinion pooling.**

It outputs calibrated probabilities for **1X2 (home / draw / away)**, **correct
scores**, **over/under 2.5**, **both-teams-to-score**, and — for knockout games —
**probability each team advances** after extra time / penalties.

Pure Python, **zero dependencies** (standard library only). Python 3.8+.

> See [`RESEARCH.md`](RESEARCH.md) for the full evidence base and citations.

## Why this design (the short version)

- **Bookmaker odds are the single most accurate probability source** for football
  (Štrumbelj 2014; Hvattum & Arntzen). So the de-vigged market is the backbone.
- **A model is a useful second opinion**, especially for international football,
  where ratings have occasionally beaten the market (FIFA ranking beat the market
  at WC 2014). It also adds structure the raw 1X2 odds lack (correct scores, O/U).
- **Logarithmic pooling, market-weighted ~65%**, is what leading academic
  forecasters actually deploy.
- **The draw is hard** (~25% base rate, rarely the modal pick). The Dixon–Coles
  low-score correction (ρ ≈ −0.13) fixes Poisson's chronic under-prediction of
  0-0 / 1-1.
- **Tournaments are uncertain.** The favourite is typically only ~15–22% to win
  the trophy — the engine reports honest probabilities, not false certainty.

## Pipeline

```
bookmaker 1X2 odds ──▶ de-vig (Shin) ─────────────┐
                                                   ├─▶ log pool (market 65%) ─▶ 1X2
Elo ratings ─▶ supremacy ─▶ Dixon–Coles Poisson ──┘            │
                              │                                 ▼
                              └──▶ scoreline matrix ─ anchored to ─▶ correct scores,
                                                       ensemble 1X2   O/U, BTTS
                                                                      knockout ▶ advance %
```

## Install

No install required — clone and run. To use it as an importable package from
anywhere:

```bash
pip install -e .
```

## Usage (CLI)

```bash
# Predict a knockout tie from bookmaker odds + bundled Elo ratings
python -m worldcup_predictor predict --home Argentina --away France \
    --odds 2.40 3.20 3.10 --neutral --knockout

# Model-only (no odds)
python -m worldcup_predictor predict --home Brazil --away Croatia --neutral

# Show the Elo table / run the sample back-test
python -m worldcup_predictor ratings
python -m worldcup_predictor backtest

# Generate the full 2026 World Cup predictions report (every match + title odds)
python -m worldcup_predictor report --output PREDICTIONS.md --sims 20000
```

## Full 2026 World Cup predictions

[`PREDICTIONS.md`](PREDICTIONS.md) contains predictions for **every** 2026 World
Cup match plus title/advancement probabilities for all 48 teams. It is generated
by predicting all 72 group-stage games with the engine and running a **20,000-run
Monte-Carlo** of the complete bracket (the verified group draw + knockout
structure, including the 8-best-third-place rule).

```bash
python -m worldcup_predictor report          # regenerate PREDICTIONS.md
```

The group draw (`data/groups_2026.json`), knockout bracket
(`data/bracket_2026.json`) and team ratings (`data/elo_ratings_2026.json`) are
bundled and easy to refresh. Because per-match odds for 104 fixtures aren't
practical to collect, the tournament report runs **model-only** (Elo/Poisson);
pass `--odds` to `predict` for the market-anchored ensemble on individual games.

Example output:

```
Argentina vs France  (neutral venue, knockout)
--------------------------------------------------------
  Argentina              win :  39.8%
  Draw                       :  29.5%
  France                 win :  30.6%
  -> most likely (1X2)    : HOME
  expected goals          : Argentina 1.40 - 1.20 France
  over 2.5 / under 2.5    : 48.1% / 51.9%
  both teams to score     : 54.3% yes / 45.7% no
  most likely scorelines:
     1-1 : 14.1%   0-0 : 9.1%   1-0 : 8.8%   2-1 : 8.7%   1-2 : 7.5%
  to advance (after ET/pens):
     Argentina : 56.0%    France : 44.0%
```

## Usage (Python)

```python
from worldcup_predictor import PredictionEngine
from worldcup_predictor.datasets import load_elo

engine = PredictionEngine(elo=load_elo(), market_weight=0.65, devig_method="shin")

pred = engine.predict(
    "England", "USA",
    market_odds=[1.50, 3.90, 7.50],   # decimal home/draw/away (optional)
    neutral=True,
)
print(pred.one_x_two)       # (P_home, P_draw, P_away)
print(pred.most_likely)     # 'home' | 'draw' | 'away'
print(pred.correct_scores)  # [((i, j), prob), ...]
print(pred.summary())
```

Learn ratings from real results instead of the bundled snapshot:

```python
from worldcup_predictor.elo import EloModel
elo = EloModel(home_advantage=100).fit(historical_matches)  # chronological dicts
```

## Package layout

| Module | Responsibility |
|---|---|
| `devig.py` | Odds → fair probabilities (multiplicative, additive, power, odds-ratio, **Shin**) |
| `elo.py` | World Football Elo — learn from results, predict expected result/supremacy |
| `poisson.py` | Dixon–Coles scoreline matrix → 1X2, correct scores, O/U, BTTS |
| `ensemble.py` | Linear & **logarithmic** opinion pooling |
| `knockout.py` | 90-min draw → extra-time / penalty advance probabilities |
| `metrics.py` | Brier, **RPS**, log-loss (proper scoring rules) |
| `engine.py` | Orchestration → a `Prediction` object |
| `backtest.py` | Score market vs model vs ensemble on historical data |
| `tournament.py` | Predict-all + Monte-Carlo bracket simulation (title/advance odds) |
| `report.py` | Generate `PREDICTIONS.md` for the full 2026 World Cup |
| `datasets.py` | Load ratings, results/odds CSVs, WC2026 groups & bracket |
| `data/` | Seed Elo ratings, WC-2022 sample, WC-2026 groups/bracket/ratings |

## Back-testing on real data

The bundled sample is ~22 WC-2022 group games with **approximate** closing odds —
enough to exercise the pipeline, **far too small to prove anything**. That 2022
group stage was also unusually upset-heavy (Saudi Arabia, Japan, Morocco,
Cameroon and Korea all beat favourites), so on this sample the model actually
scores *better* than the market — the opposite of the long-run result. For a real
evaluation, point the loader at thousands of matches:

- **[football-data.co.uk](https://www.football-data.co.uk/data.php)** — league
  results **with bookmaker odds** (map `B365H/B365D/B365A` →
  `odds_home/odds_draw/odds_away`).
- **[martj42/international_results](https://github.com/martj42/international_results)**
  — all internationals 1872–present, to train Elo via `EloModel.fit()`.
- **[The Odds API](https://the-odds-api.com/)** / **[football-data.org](https://www.football-data.org/)**
  — live odds & fixtures.

```python
from worldcup_predictor.datasets import load_matches
from worldcup_predictor.backtest import run_backtest
print(run_backtest(load_matches("path/to/your_results_with_odds.csv")))
```

## Tuning knobs

`PredictionEngine(market_weight=0.65, devig_method="shin", rho=-0.13,
mu_total=2.6, elo_to_supremacy=1/350, home_advantage=...)`. Tune `market_weight`
and `rho` by minimising out-of-sample **RPS / log-loss** on a large back-test.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Caveats

- Probabilities are **calibrated estimates, not certainties** — single-elimination
  football is high-variance by nature.
- This is a forecasting tool. Forecast accuracy and betting profitability are
  *different* things (Wunderlich & Memmert 2020); nothing here is betting advice.
- The bundled Elo ratings are an **illustrative snapshot** — refresh them from
  eloratings.net or by fitting on real results before serious use.

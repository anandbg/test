# Research: Predicting World Cup Football Match Outcomes

This document summarises the evidence behind the prediction strategy implemented in
this repository. It was compiled from a fan-out web-research pass across five angles:
(1) converting odds to probabilities, (2) odds vs. statistical models, (3) how the major
forecasters actually did at WC 2018/2022, (4) modelling the draw, and (5) ensemble design
and data sources. Sources are listed inline.

## TL;DR — the strategy

> **De-vig the bookmaker 1X2 odds, build an Elo + Dixon–Coles-Poisson model as a second
> opinion, and combine them with logarithmic (log-odds) pooling that weights the market
> ~65%. Tune the weight to minimise out-of-sample log-loss / ranked probability score.**

Market odds are the single most accurate probability source available; a well-built model
mostly *matches* them and occasionally edges them in international football. The robust,
defensible move is to anchor on the de-vigged market and let the model nudge it.

---

## 1. Converting bookmaker odds into true probabilities (de-vigging)

For each outcome *i* with decimal odds `o_i`, the raw implied probability is `r_i = 1/o_i`.
The **overround / booksum** `M = Σ r_i > 1`; the excess `M − 1` is the bookmaker margin.
Typical 1X2 margins: ~2–3% (sharp books e.g. Pinnacle) to ~5–10% (recreational books).

| Method | Formula | Notes |
|---|---|---|
| **Multiplicative** (normalization) | `p_i = r_i / M` | Simplest. Does **not** correct favourite-longshot bias. Fine for balanced markets. |
| **Additive** | `p_i = r_i − (M−1)/n` | Splits margin equally; can produce **negative** probabilities for longshots. |
| **Power** | `p_i = r_i^e`, solve `e` s.t. `Σ r_i^e = 1` | Stays in [0,1]; corrects some bias. Good general default. |
| **Odds-ratio** (Cheung) | `p_i = r_i / (c + r_i − c·r_i)`, solve `c` s.t. `Σ p_i = 1` | Multiplicative in odds-space. |
| **Shin** | `p_i = (√(z² + 4(1−z)·r_i²/M) − z) / (2(1−z))`, solve `z` s.t. `Σ p_i = 1` | Models insider money; corrects favourite-longshot bias; academically favoured. |

**Evidence:** Štrumbelj (2014), *On determining probability forecasts from betting odds*,
*Int. J. Forecasting* 30(4):934–943 — Shin > multiplicative > regression for forecast
accuracy; the advantage shrinks as the market grows more liquid. The favourite-longshot
bias is real and large in 1X2 markets (longshots lose ~17%/bet vs ~2% for favourites —
Hegarty & Whelan, *karlwhelan.com/Papers/Overround.pdf*). Caveat: Hegarty & Whelan (2023)
argue Shin's insider-trading rationale does **not** fit football and that Asian-handicap
markets are more efficient than 1X2 — so on lopsided games the method choice matters; on
balanced games all methods nearly agree.

All five methods are implemented in the R `implied` package, which we used to cross-check
formulas.

## 2. Do market odds beat statistical models?

- **Yes, mostly.** Bookmaker odds are efficient, near-ceiling forecasters
  (Forrest, Goddard & Simmons 2005, *Odds-setters as forecasters*, IJF 21(3)). Prediction
  markets and odds tie each other (~54% W/D/L accuracy) and crush human tipsters (~43%) —
  Spann & Skiera (2009), *J. Forecasting* 28(1).
- **The accuracy ceiling is ~50–55% W/D/L / RPS ≈ 0.20.** In the 2017 Open International
  Soccer Prediction Challenge, bookmaker odds (RPS ≈ 0.202, acc 51.9%) matched or beat the
  best ML entries. State-of-the-art models cluster at the same ceiling.
- **International football is where models can win.** The post-2006 FIFA World Ranking
  *significantly outperformed* the market at WC 2014 (Wunderlich & Memmert 2016, *J. Sports
  Sciences*). Bookmaker-**consensus** models beat standalone Elo/FIFA ratings and called
  Spain 2010 + 3/4 semifinalists 2014 (Leitner, Zeileis & Hornik 2010).
- **Bivariate-Poisson ability ratings + random forests** are the leading pure-model family
  for tournaments (Groll, Ley, Schauberger et al. 2018).
- **Metric standard:** Ranked Probability Score (RPS) for ordinal W/D/L; also Brier and
  log-loss. **Forecast accuracy ≠ betting profit** (Wunderlich & Memmert 2020).

## 3. How the forecasters actually did at WC 2018 & 2022

- **2018:** 538 SPI #1 = Brazil; books made Brazil/Germany co-favourites; the Gilch–Müller
  Elo+Poisson model favoured Germany. **France won** (mid-board). Germany went out in the
  group stage (missed by everyone).
- **2022:** 538 SPI #1 = Brazil (22%), **Argentina just 8%, joint 4th**; Opta favoured
  France/Brazil, rated Argentina ~5%. **Argentina won.** Saudi Arabia 2-1 Argentina was a
  ~+1200 historic upset no model foresaw; Germany again exited in the group stage.
- **Lesson:** single-elimination tournaments have irreducible uncertainty — the modal
  favourite is only ~15–22% to win the whole thing, so being "wrong" about the champion is
  expected, not a model failure. A good engine outputs **calibrated** probabilities (538's
  self-reported soccer Brier ≈ 0.16; favourites win ~62% of matches), not false certainty.

## 4. Modelling the draw (the hard part)

- Draws are ~**25%** of league matches and ~24% of WC group games (16% in 2018) — the
  least frequent of the three outcomes and **low-variance**; even in the most balanced game
  the draw rarely exceeds ~30%, so it's almost never the modal pick.
- Two opposite biases: **humans under-predict** draws; **markets tend to over-price** them.
- **Independent Poisson under-predicts low/drawn scores.** The **Dixon–Coles (1997)** fix
  multiplies the four lowest cells by a correction `τ` governed by a small negative `ρ`:
  - `τ(0,0) = 1 − λ·μ·ρ`
  - `τ(0,1) = 1 + λ·ρ`
  - `τ(1,0) = 1 + μ·ρ`
  - `τ(1,1) = 1 − ρ`
  - `τ = 1` for all other scores.
  With `ρ ≈ −0.13` (original; typically −0.03…−0.15) this lifts 0-0 and 1-1 back to
  observed frequency. It fixes the low-score tail; it does **not** make the draw the modal
  outcome.
- **Knockouts:** there is no "draw" in the bracket. Model the **90-minute** draw, then the
  conditional extra-time/penalty winner (≈ coin flip nudged by relative strength).

## 5. Ensemble design and data

- **Logarithmic (log-odds) pooling** = weighted geometric mean of the component
  probabilities, renormalised: `p ∝ Π pᵢ^wᵢ`. It takes confident forecasts more seriously
  than linear pooling and is sharper for well-calibrated experts (Ranjan & Gneiting). Any
  pool of distinct calibrated forecasts is itself slightly mis-calibrated, so
  **recalibrate** and tune weights against log-loss/Brier.
- **Market-heavy weighting (~60–80% market)** is empirically justified (market dominates;
  Hvattum & Arntzen). We default to **0.65** and expose it as a tunable.
- **Poisson → markets:** build a scoreline matrix `P(i,j) = Pois(i;λ_home)·Pois(j;λ_away)`
  (+ Dixon–Coles τ), then `P(home)=Σ_{i>j}`, `P(draw)=Σ_{i=j}`, `P(away)=Σ_{i<j}`; each cell
  is a correct-score probability and over/under, BTTS, double-chance are sums of cells.
- **Elo for internationals (World Football Elo):** `R' = R + K·(W − Wₑ)`,
  `Wₑ = 1/(1+10^(−dr/400))`, dr = ratingdiff + home advantage (~100). K = 60 (WC finals),
  50, 40, 30, 20 (friendlies); goal-difference multiplier ×1, ×1.5, ×1.75, … for the margin.

### Free / open data sources (to feed and back-test the engine)

| Source | What | URL |
|---|---|---|
| Kaggle `martj42` | All men's internationals 1872–present (~49k) | https://github.com/martj42/international_results |
| football-data.co.uk | 30y league results **+ bookmaker odds** CSVs | https://www.football-data.co.uk/data.php |
| football-data.org | Free fixtures/results REST API | https://www.football-data.org/ |
| The Odds API | Live bookmaker odds (free tier) | https://the-odds-api.com/ |
| OpenFootball | Public-domain results DB | https://github.com/openfootball |
| eloratings.net | International Elo reference | http://www.eloratings.net/ |
| FiveThirtyEight SPI | Archived SPI match CSVs | https://github.com/fivethirtyeight/data/tree/master/soccer-spi |

---

### How this maps to the code

| Concept | Module |
|---|---|
| De-vig (multiplicative/additive/power/odds-ratio/Shin) | `worldcup_predictor/devig.py` |
| World Football Elo (rate from results + predict) | `worldcup_predictor/elo.py` |
| Dixon–Coles Poisson scoreline matrix + derived markets | `worldcup_predictor/poisson.py` |
| Log / linear opinion pooling | `worldcup_predictor/ensemble.py` |
| Extra-time / penalty (knockout) winner | `worldcup_predictor/knockout.py` |
| Brier / RPS / log-loss | `worldcup_predictor/metrics.py` |
| Orchestration (market + Elo + Poisson → prediction) | `worldcup_predictor/engine.py` |
| CLI | `worldcup_predictor/cli.py` |

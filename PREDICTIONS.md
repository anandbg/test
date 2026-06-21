# 2026 FIFA World Cup — Match Predictions

*Generated 2026-06-21 · hosts: USA, Mexico, Canada · 48 teams, 104 matches*

> **These are calibrated model probabilities, not certainties.** A World Cup is high-variance: the pre-tournament favourite typically has only a ~15–25% chance of winning the whole thing, and ~1 group match in 3 is an upset. Use these as odds, not predictions of fact.

## How these were produced

- **Engine:** World-Football-Elo ratings → expected goal supremacy → Dixon–Coles Poisson scoreline matrix (1X2, scores, over/under, BTTS). See `RESEARCH.md` for the evidence base.

- **Tournament:** a 20,000-run Monte-Carlo simulation of all 104 matches (group stage + the verified knockout bracket, including the 8-best-third rule) gives each team's advancement and title probabilities.

- **Model-only:** per-match bookmaker odds for 104 fixtures aren't feasibly collected here, so the market component is off; the engine runs on ratings alone. Feed `--odds` per match for the market-anchored ensemble.

- **Ratings caveat:** Elo values are an approximate June-2026 snapshot (top teams high-confidence; lower tier interpolated from FIFA ranking, as eloratings.net was unreachable). Swap in the live table to refine.

## Title & deep-run probabilities (top 16)

| # | Team | Champion | Final | Semi | Quarter | Last 16 |
|---|------|---------:|------:|-----:|--------:|--------:|
| 1 | Argentina | 14% | 22% | 34% | 48% | 65% |
| 2 | Spain | 14% | 22% | 34% | 46% | 67% |
| 3 | France | 11% | 19% | 31% | 46% | 67% |
| 4 | England | 8.7% | 15% | 26% | 41% | 61% |
| 5 | Portugal | 6.6% | 12% | 21% | 37% | 58% |
| 6 | Colombia | 5.7% | 11% | 20% | 34% | 55% |
| 7 | Brazil | 5.5% | 10% | 20% | 35% | 56% |
| 8 | Netherlands | 4.7% | 9.1% | 18% | 33% | 52% |
| 9 | Germany | 4.2% | 8.7% | 17% | 30% | 56% |
| 10 | Senegal | 3.4% | 7.5% | 15% | 29% | 50% |
| 11 | Belgium | 2.3% | 5.5% | 12% | 26% | 50% |
| 12 | Croatia | 1.9% | 4.6% | 10% | 20% | 39% |
| 13 | Morocco | 1.7% | 4.3% | 10% | 22% | 41% |
| 14 | Mexico | 1.7% | 4.5% | 11% | 24% | 51% |
| 15 | Uruguay | 1.7% | 4.2% | 9.4% | 19% | 37% |
| 16 | United States | 1.2% | 3.3% | 7.7% | 19% | 42% |

## Group-by-group

### Group A

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Mexico | 47% | 87% |
| South Korea | 26% | 72% |
| Czechia | 16% | 60% |
| South Africa | 11% | 49% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Mexico *(host)* v South Africa | 56% | 26% | 18% | 1 | 1–1 | 51% |
| Mexico *(host)* v South Korea | 45% | 29% | 26% | 1 | 1–1 | 49% |
| Mexico *(host)* v Czechia | 51% | 27% | 21% | 1 | 1–1 | 50% |
| South Africa v South Korea | 25% | 28% | 46% | 2 | 1–1 | 50% |
| South Africa v Czechia | 31% | 29% | 40% | 2 | 1–1 | 49% |
| South Korea v Czechia | 41% | 29% | 29% | 1 | 1–1 | 49% |

### Group B

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Switzerland | 36% | 80% |
| Canada | 34% | 79% |
| Qatar | 16% | 57% |
| Bosnia and Herzegovina | 14% | 53% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Canada *(host)* v Switzerland | 35% | 30% | 36% | 2 | 1–1 | 48% |
| Canada *(host)* v Qatar | 47% | 28% | 25% | 1 | 1–1 | 50% |
| Canada *(host)* v Bosnia and Herzegovina | 48% | 28% | 24% | 1 | 1–1 | 50% |
| Switzerland v Qatar | 47% | 28% | 25% | 1 | 1–1 | 50% |
| Switzerland v Bosnia and Herzegovina | 48% | 28% | 24% | 1 | 1–1 | 50% |
| Qatar v Bosnia and Herzegovina | 37% | 30% | 34% | 1 | 1–1 | 48% |

### Group C

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Brazil | 49% | 90% |
| Morocco | 30% | 79% |
| Scotland | 16% | 64% |
| Haiti | 5.3% | 33% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Brazil v Morocco | 43% | 29% | 28% | 1 | 1–1 | 49% |
| Brazil v Scotland | 52% | 27% | 21% | 1 | 1–1 | 50% |
| Brazil v Haiti | 66% | 23% | 12% | 1 | 2–0 | 52% |
| Morocco v Scotland | 44% | 29% | 27% | 1 | 1–1 | 49% |
| Morocco v Haiti | 58% | 26% | 17% | 1 | 1–1 | 51% |
| Scotland v Haiti | 49% | 28% | 23% | 1 | 1–1 | 50% |

### Group D

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| United States | 36% | 79% |
| Turkey | 27% | 71% |
| Australia | 20% | 63% |
| Paraguay | 17% | 57% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| United States *(host)* v Paraguay | 46% | 28% | 25% | 1 | 1–1 | 50% |
| United States *(host)* v Australia | 43% | 29% | 28% | 1 | 1–1 | 49% |
| United States *(host)* v Turkey | 40% | 29% | 31% | 1 | 1–1 | 49% |
| Paraguay v Australia | 33% | 30% | 38% | 2 | 1–1 | 49% |
| Paraguay v Turkey | 29% | 29% | 42% | 2 | 1–1 | 49% |
| Australia v Turkey | 32% | 29% | 39% | 2 | 1–1 | 49% |

### Group E

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Germany | 50% | 89% |
| Ecuador | 23% | 73% |
| Ivory Coast | 20% | 68% |
| Curacao | 7.2% | 39% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Germany v Curacao | 63% | 24% | 13% | 1 | 2–0 | 52% |
| Germany v Ivory Coast | 50% | 28% | 22% | 1 | 1–1 | 50% |
| Germany v Ecuador | 47% | 28% | 25% | 1 | 1–1 | 50% |
| Curacao v Ivory Coast | 24% | 28% | 48% | 2 | 1–1 | 50% |
| Curacao v Ecuador | 22% | 27% | 51% | 2 | 1–1 | 50% |
| Ivory Coast v Ecuador | 32% | 29% | 38% | 2 | 1–1 | 49% |

### Group F

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Netherlands | 48% | 87% |
| Japan | 24% | 70% |
| Sweden | 16% | 59% |
| Tunisia | 13% | 53% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Netherlands v Japan | 46% | 28% | 25% | 1 | 1–1 | 50% |
| Netherlands v Tunisia | 55% | 26% | 19% | 1 | 1–1 | 51% |
| Netherlands v Sweden | 52% | 27% | 21% | 1 | 1–1 | 50% |
| Japan v Tunisia | 43% | 29% | 28% | 1 | 1–1 | 49% |
| Japan v Sweden | 41% | 29% | 30% | 1 | 1–1 | 49% |
| Tunisia v Sweden | 33% | 30% | 38% | 2 | 1–1 | 49% |

### Group G

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Belgium | 43% | 85% |
| Iran | 28% | 76% |
| Egypt | 21% | 68% |
| New Zealand | 7.8% | 40% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Belgium v Egypt | 46% | 29% | 26% | 1 | 1–1 | 49% |
| Belgium v Iran | 41% | 29% | 30% | 1 | 1–1 | 49% |
| Belgium v New Zealand | 58% | 25% | 16% | 1 | 1–1 | 51% |
| Egypt v Iran | 31% | 29% | 39% | 2 | 1–1 | 49% |
| Egypt v New Zealand | 48% | 28% | 24% | 1 | 1–1 | 50% |
| Iran v New Zealand | 52% | 27% | 21% | 1 | 1–1 | 50% |

### Group H

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Spain | 65% | 96% |
| Uruguay | 23% | 80% |
| Saudi Arabia | 5.9% | 43% |
| Cape Verde | 5.4% | 41% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Spain v Cape Verde | 71% | 20% | 8.6% | 1 | 2–0 | 53% |
| Spain v Saudi Arabia | 70% | 21% | 9.2% | 1 | 2–0 | 52% |
| Spain v Uruguay | 53% | 27% | 20% | 1 | 1–1 | 50% |
| Cape Verde v Saudi Arabia | 34% | 30% | 37% | 2 | 1–1 | 48% |
| Cape Verde v Uruguay | 19% | 27% | 54% | 2 | 1–1 | 50% |
| Saudi Arabia v Uruguay | 20% | 27% | 53% | 2 | 1–1 | 50% |

### Group I

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| France | 53% | 91% |
| Senegal | 29% | 80% |
| Norway | 13% | 58% |
| Iraq | 5.9% | 36% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| France v Senegal | 45% | 29% | 26% | 1 | 1–1 | 49% |
| France v Norway | 57% | 26% | 17% | 1 | 1–1 | 51% |
| France v Iraq | 67% | 22% | 11% | 1 | 2–0 | 52% |
| Senegal v Norway | 47% | 28% | 25% | 1 | 1–1 | 50% |
| Senegal v Iraq | 57% | 26% | 18% | 1 | 1–1 | 51% |
| Norway v Iraq | 45% | 29% | 27% | 1 | 1–1 | 49% |

### Group J

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Argentina | 65% | 95% |
| Austria | 16% | 67% |
| Algeria | 14% | 62% |
| Jordan | 5.5% | 38% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Argentina v Algeria | 60% | 25% | 15% | 1 | 1–1 | 51% |
| Argentina v Austria | 58% | 25% | 16% | 1 | 1–1 | 51% |
| Argentina v Jordan | 70% | 21% | 9.1% | 1 | 2–0 | 52% |
| Algeria v Austria | 33% | 30% | 37% | 2 | 1–1 | 48% |
| Algeria v Jordan | 46% | 29% | 26% | 1 | 1–1 | 49% |
| Austria v Jordan | 48% | 28% | 24% | 1 | 1–1 | 50% |

### Group K

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| Portugal | 44% | 89% |
| Colombia | 41% | 88% |
| Uzbekistan | 7.6% | 45% |
| DR Congo | 7.3% | 44% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| Portugal v Colombia | 36% | 30% | 34% | 1 | 1–1 | 48% |
| Portugal v Uzbekistan | 60% | 25% | 15% | 1 | 1–1 | 51% |
| Portugal v DR Congo | 60% | 25% | 15% | 1 | 1–1 | 51% |
| Colombia v Uzbekistan | 59% | 25% | 16% | 1 | 1–1 | 51% |
| Colombia v DR Congo | 59% | 25% | 16% | 1 | 1–1 | 51% |
| Uzbekistan v DR Congo | 36% | 30% | 35% | 1 | 1–1 | 48% |

### Group L

**Projected finish** (probability to win group / advance to knockouts):

| Team | Win group | Advance |
|------|----------:|--------:|
| England | 55% | 92% |
| Croatia | 27% | 78% |
| Panama | 11% | 54% |
| Ghana | 6.8% | 41% |

**Match predictions:**

| Match | Home win | Draw | Away win | Likely | Top score | O2.5 |
|-------|---------:|-----:|---------:|:------:|:---------:|----:|
| England v Croatia | 47% | 28% | 24% | 1 | 1–1 | 50% |
| England v Ghana | 65% | 23% | 12% | 1 | 2–0 | 52% |
| England v Panama | 60% | 25% | 15% | 1 | 1–1 | 51% |
| Croatia v Ghana | 53% | 27% | 20% | 1 | 1–1 | 50% |
| Croatia v Panama | 48% | 28% | 24% | 1 | 1–1 | 50% |
| Ghana v Panama | 30% | 29% | 41% | 2 | 1–1 | 49% |

## Notes

- **1 / X / 2** = home win / draw / away win. *Likely* is the single most probable 1X2 outcome (often the favourite even when <50%).

- Knockout ties are decided in the simulation by 90-minute probabilities plus an extra-time/penalty coin-flip nudged by team strength.

- The third-place qualifiers are seeded into the Round of 32 by a constrained matching consistent with FIFA's combination-table pools.

- Regenerate any time with `python -m worldcup_predictor report`. Refresh `data/elo_ratings_2026.json` from eloratings.net for sharper numbers.

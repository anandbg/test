import unittest

from worldcup_predictor import PredictionEngine
from worldcup_predictor.datasets import load_elo, load_matches
from worldcup_predictor.backtest import run_backtest


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PredictionEngine(elo=load_elo())

    def test_prediction_is_distribution(self):
        p = self.engine.predict("Argentina", "France", market_odds=[2.4, 3.2, 3.1],
                                neutral=True)
        self.assertAlmostEqual(p.prob_home + p.prob_draw + p.prob_away, 1.0, places=9)
        self.assertIn(p.most_likely, ("home", "draw", "away"))

    def test_market_pulls_toward_odds(self):
        # A heavy home favourite in the odds should raise home prob vs model-only.
        model_only = self.engine.predict("Brazil", "Serbia", neutral=True)
        with_odds = self.engine.predict("Brazil", "Serbia", market_odds=[1.40, 4.5, 8.5],
                                        neutral=True)
        self.assertGreater(with_odds.prob_home, model_only.prob_home)

    def test_derived_markets_valid(self):
        p = self.engine.predict("Spain", "Germany", market_odds=[2.7, 3.3, 2.6],
                                neutral=True)
        self.assertAlmostEqual(p.over_2_5 + p.under_2_5, 1.0, places=6)
        self.assertAlmostEqual(p.btts_yes + p.btts_no, 1.0, places=6)
        cs_total = sum(prob for _, prob in p.correct_scores)
        self.assertTrue(0.0 < cs_total <= 1.0 + 1e-9)

    def test_correct_scores_anchor_to_1x2(self):
        # Summing the anchored matrix's home-win cells should align with 1X2.
        p = self.engine.predict("France", "Australia", market_odds=[1.28, 6.0, 9.5],
                                neutral=True)
        home_cells = sum(prob for (i, j), prob in p.correct_scores if i > j)
        self.assertLessEqual(home_cells, p.prob_home + 1e-9)

    def test_knockout_advance(self):
        p = self.engine.predict("Argentina", "Netherlands", market_odds=[2.3, 3.1, 3.4],
                                neutral=True, knockout=True)
        self.assertIsNotNone(p.advance_home)
        self.assertAlmostEqual(p.advance_home + p.advance_away, 1.0, places=9)

    def test_summary_renders(self):
        p = self.engine.predict("Morocco", "Portugal", market_odds=[4.0, 3.3, 2.0],
                                neutral=True, knockout=True)
        text = p.summary()
        self.assertIn("Morocco", text)
        self.assertIn("most likely scorelines", text)


class TestBacktest(unittest.TestCase):
    def test_backtest_runs(self):
        res = run_backtest(matches=load_matches())
        self.assertGreater(res["n"], 0)
        for key in ("market_only", "model_only"):
            self.assertIn("rps", res[key])
            self.assertGreaterEqual(res[key]["rps"], 0.0)


if __name__ == "__main__":
    unittest.main()

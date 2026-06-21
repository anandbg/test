import math
import unittest

from worldcup_predictor import ensemble as ens
from worldcup_predictor import knockout as ko
from worldcup_predictor import metrics


class TestEnsemble(unittest.TestCase):
    def test_linear_pool_average(self):
        out = ens.linear_pool([[0.6, 0.2, 0.2], [0.2, 0.2, 0.6]], [0.5, 0.5])
        self.assertAlmostEqual(out[0], 0.4)
        self.assertAlmostEqual(out[2], 0.4)
        self.assertAlmostEqual(sum(out), 1.0)

    def test_log_pool_normalized(self):
        out = ens.log_pool([[0.6, 0.2, 0.2], [0.3, 0.4, 0.3]], [0.65, 0.35])
        self.assertAlmostEqual(sum(out), 1.0, places=9)

    def test_log_pool_sharper_than_linear(self):
        # For agreeing confident forecasts, log pool is at least as sharp.
        f = [[0.7, 0.2, 0.1], [0.7, 0.2, 0.1]]
        lin = ens.linear_pool(f, [0.5, 0.5])
        log = ens.log_pool(f, [0.5, 0.5])
        self.assertGreaterEqual(log[0], lin[0] - 1e-9)

    def test_weights_normalized(self):
        a = ens.log_pool([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]], [1, 1])
        b = ens.log_pool([[0.5, 0.3, 0.2], [0.2, 0.3, 0.5]], [10, 10])
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=9)


class TestMetrics(unittest.TestCase):
    def test_perfect_forecast(self):
        self.assertAlmostEqual(metrics.brier([1, 0, 0], 0), 0.0)
        self.assertAlmostEqual(metrics.rps([1, 0, 0], 0), 0.0)
        self.assertAlmostEqual(metrics.log_loss([1, 0, 0], 0), 0.0, places=6)

    def test_rps_rewards_ordinal_closeness(self):
        # Predicting the adjacent outcome (draw) beats predicting the far one
        # (away) when home actually wins.
        near = metrics.rps([0.0, 1.0, 0.0], 0)
        far = metrics.rps([0.0, 0.0, 1.0], 0)
        self.assertLess(near, far)

    def test_evaluate_aggregates(self):
        res = metrics.evaluate([[0.7, 0.2, 0.1], [0.1, 0.2, 0.7]], [0, 2])
        self.assertEqual(res["n"], 2)
        self.assertAlmostEqual(res["hit_rate"], 1.0)
        self.assertGreater(res["brier"], 0.0)


class TestKnockout(unittest.TestCase):
    def test_advance_sums_to_one(self):
        ah, aa = ko.advance_probability(0.4, 0.3, 0.3, we_home=0.5)
        self.assertAlmostEqual(ah + aa, 1.0, places=9)

    def test_no_draw_passthrough(self):
        ah, aa = ko.advance_probability(0.6, 0.0, 0.4, we_home=0.7)
        self.assertAlmostEqual(ah, 0.6, places=9)
        self.assertAlmostEqual(aa, 0.4, places=9)

    def test_stronger_team_favoured_in_shootout(self):
        # Even teams on 90-min 1X2, but home is stronger on Elo -> advances more.
        ah, _ = ko.advance_probability(0.35, 0.30, 0.35, we_home=0.7)
        self.assertGreater(ah, 0.5)


if __name__ == "__main__":
    unittest.main()

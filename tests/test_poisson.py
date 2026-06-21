import unittest

from worldcup_predictor import poisson as ps


class TestPoisson(unittest.TestCase):
    def test_pmf_basic(self):
        self.assertAlmostEqual(ps.poisson_pmf(0, 0.0), 1.0)
        # sum over k approximates 1
        total = sum(ps.poisson_pmf(k, 1.7) for k in range(30))
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_matrix_normalized(self):
        m = ps.score_matrix(1.6, 1.1)
        total = sum(sum(row) for row in m)
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_outcome_probs_sum_to_one(self):
        h, d, a = ps.outcome_probs(ps.score_matrix(1.5, 1.5))
        self.assertAlmostEqual(h + d + a, 1.0, places=9)

    def test_equal_lambdas_symmetric(self):
        h, d, a = ps.outcome_probs(ps.score_matrix(1.4, 1.4))
        self.assertAlmostEqual(h, a, places=9)

    def test_stronger_home_wins_more(self):
        h, d, a = ps.outcome_probs(ps.score_matrix(2.2, 0.8))
        self.assertGreater(h, a)

    def test_dixon_coles_raises_draw(self):
        # Negative rho should increase the draw probability vs independent Poisson.
        plain = ps.outcome_probs(ps.score_matrix(1.3, 1.3, rho=0.0))
        corrected = ps.outcome_probs(ps.score_matrix(1.3, 1.3, rho=-0.13))
        self.assertGreater(corrected[1], plain[1])

    def test_correct_scores_sorted(self):
        cs = ps.correct_scores(ps.score_matrix(1.5, 1.2), top_n=5)
        probs = [p for _, p in cs]
        self.assertEqual(probs, sorted(probs, reverse=True))

    def test_over_under_complement(self):
        m = ps.score_matrix(1.5, 1.5)
        over, under = ps.over_under(m, 2.5)
        self.assertAlmostEqual(over + under, 1.0, places=9)

    def test_rescale_matches_target(self):
        m = ps.score_matrix(1.6, 1.0)
        target = (0.55, 0.25, 0.20)
        m2 = ps.rescale_to_1x2(m, *target)
        h, d, a = ps.outcome_probs(m2)
        self.assertAlmostEqual(h, target[0], places=6)
        self.assertAlmostEqual(d, target[1], places=6)
        self.assertAlmostEqual(a, target[2], places=6)


if __name__ == "__main__":
    unittest.main()

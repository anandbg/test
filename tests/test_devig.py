import unittest

from worldcup_predictor import devig


class TestDevig(unittest.TestCase):
    BALANCED = [2.10, 3.40, 3.60]
    LOPSIDED = [1.16, 8.0, 17.0]

    def test_overround_and_margin(self):
        self.assertGreater(devig.overround(self.BALANCED), 1.0)
        self.assertAlmostEqual(
            devig.margin(self.BALANCED), devig.overround(self.BALANCED) - 1.0
        )

    def test_all_methods_sum_to_one_and_in_range(self):
        for name, fn in devig.METHODS.items():
            for odds in (self.BALANCED, self.LOPSIDED):
                probs = fn(odds)
                self.assertAlmostEqual(sum(probs), 1.0, places=9, msg=name)
                for p in probs:
                    self.assertGreaterEqual(p, 0.0, msg=name)
                    self.assertLessEqual(p, 1.0, msg=name)

    def test_favourite_stays_favourite(self):
        # The lowest odds must map to the highest probability for every method.
        for name, fn in devig.METHODS.items():
            probs = fn(self.LOPSIDED)
            self.assertEqual(probs.index(max(probs)), 0, msg=name)

    def test_shin_lifts_favourite_vs_multiplicative(self):
        # Bias-correcting methods push probability toward the favourite on a
        # lopsided book relative to plain normalization.
        mult = devig.multiplicative(self.LOPSIDED)
        shin = devig.shin(self.LOPSIDED)
        self.assertGreaterEqual(shin[0], mult[0] - 1e-9)

    def test_methods_agree_on_balanced_book(self):
        # On a near-balanced book all methods should nearly coincide.
        ref = devig.multiplicative(self.BALANCED)
        for fn in (devig.power, devig.shin, devig.odds_ratio):
            probs = fn(self.BALANCED)
            for a, b in zip(ref, probs):
                self.assertLess(abs(a - b), 0.03)

    def test_rejects_bad_odds(self):
        with self.assertRaises(ValueError):
            devig.multiplicative([1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            devig.devig([2.0, 3.0], method="nope")


if __name__ == "__main__":
    unittest.main()

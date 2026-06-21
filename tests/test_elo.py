import unittest

from worldcup_predictor.elo import EloModel, expected_result, goal_difference_multiplier


class TestElo(unittest.TestCase):
    def test_expected_result_symmetry(self):
        self.assertAlmostEqual(expected_result(0.0), 0.5)
        self.assertAlmostEqual(
            expected_result(200) + expected_result(-200), 1.0, places=9
        )

    def test_stronger_team_higher_expectation(self):
        self.assertGreater(expected_result(150), 0.5)

    def test_goal_diff_multiplier(self):
        self.assertEqual(goal_difference_multiplier(1), 1.0)
        self.assertEqual(goal_difference_multiplier(2), 1.5)
        self.assertEqual(goal_difference_multiplier(3), 1.75)
        self.assertAlmostEqual(goal_difference_multiplier(4), 1.875)

    def test_home_advantage_applied(self):
        elo = EloModel({"A": 1500, "B": 1500}, home_advantage=100)
        self.assertGreater(elo.expected("A", "B"), 0.5)
        self.assertAlmostEqual(elo.expected("A", "B", neutral=True), 0.5)

    def test_update_is_zero_sum(self):
        elo = EloModel({"A": 1500, "B": 1500}, home_advantage=0)
        before = elo.rating("A") + elo.rating("B")
        elo.update_match("A", "B", 2, 0, importance="world_cup")
        after = elo.rating("A") + elo.rating("B")
        self.assertAlmostEqual(before, after, places=6)

    def test_winner_gains(self):
        elo = EloModel({"A": 1500, "B": 1500}, home_advantage=0)
        elo.update_match("A", "B", 3, 0, importance="world_cup")
        self.assertGreater(elo.rating("A"), 1500)
        self.assertLess(elo.rating("B"), 1500)

    def test_fit_orders_teams(self):
        matches = [
            {"home": "A", "away": "B", "home_goals": 3, "away_goals": 0,
             "importance": "world_cup", "neutral": True},
            {"home": "A", "away": "C", "home_goals": 2, "away_goals": 0,
             "importance": "world_cup", "neutral": True},
        ]
        elo = EloModel(home_advantage=0).fit(matches)
        self.assertGreater(elo.rating("A"), elo.rating("B"))


if __name__ == "__main__":
    unittest.main()

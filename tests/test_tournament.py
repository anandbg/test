import unittest

from worldcup_predictor.datasets import load_bracket_2026, load_groups_2026
from worldcup_predictor.report import build_engine
from worldcup_predictor import tournament as tmt


class TestTournamentData(unittest.TestCase):
    def test_groups_complete(self):
        gd = load_groups_2026()
        groups = gd["groups"]
        self.assertEqual(len(groups), 12)
        all_teams = [t for g in groups.values() for t in g]
        self.assertEqual(len(all_teams), 48)
        self.assertEqual(len(set(all_teams)), 48)  # no duplicates
        for g, teams in groups.items():
            self.assertEqual(len(teams), 4, msg=g)

    def test_bracket_match_count(self):
        br = load_bracket_2026()
        total = (len(br["r32"]) + len(br["r16"]) + len(br["qf"])
                 + len(br["sf"]) + 2)  # + final + third-place
        self.assertEqual(total, 32)  # knockout matches
        self.assertEqual(len(br["r32"]), 16)

    def test_every_team_has_a_rating(self):
        from worldcup_predictor.datasets import load_seed_ratings, RATINGS_2026
        ratings = load_seed_ratings(RATINGS_2026)
        gd = load_groups_2026()
        for g, teams in gd["groups"].items():
            for t in teams:
                self.assertIn(t, ratings, msg=f"{t} missing a rating")


class TestThirdPlaceAssignment(unittest.TestCase):
    def setUp(self):
        br = load_bracket_2026()
        self.slots = [(m["id"], set(m["b"]["t"])) for m in br["r32"] if "t" in m["b"]]

    def test_eight_third_slots(self):
        self.assertEqual(len(self.slots), 8)

    def test_assignment_is_valid_bijection(self):
        # Pick a plausible set of 8 qualifying groups and assign them.
        qualifying = {"A", "B", "C", "E", "F", "H", "I", "J"}
        assignment = tmt.assign_thirds(qualifying, self.slots)
        self.assertIsNotNone(assignment)
        self.assertEqual(len(assignment), 8)
        # every assigned group is distinct and within its slot's pool
        self.assertEqual(len(set(assignment.values())), 8)
        pools = dict(self.slots)
        for mid, grp in assignment.items():
            self.assertIn(grp, pools[mid])


class TestSimulation(unittest.TestCase):
    def test_probabilities_consistent(self):
        gd = load_groups_2026()
        br = load_bracket_2026()
        sim = tmt.simulate_tournament(build_engine(), gd, br, n_sims=300, seed=7)
        teams = sim["teams"]
        # exactly one champion, two finalists, 32 round-of-32 teams per sim
        self.assertAlmostEqual(sum(teams[t]["champion"] for t in teams), 1.0, places=6)
        self.assertAlmostEqual(sum(teams[t]["reach_final"] for t in teams), 2.0, places=6)
        self.assertAlmostEqual(sum(teams[t]["reach_r32"] for t in teams), 32.0, places=6)
        # monotonic: champion <= final <= ... <= reach_r32
        for t in teams:
            p = teams[t]
            self.assertLessEqual(p["champion"], p["reach_final"] + 1e-9)
            self.assertLessEqual(p["reach_final"], p["reach_sf"] + 1e-9)
            self.assertLessEqual(p["reach_sf"], p["reach_qf"] + 1e-9)
            self.assertLessEqual(p["reach_qf"], p["reach_r16"] + 1e-9)
            self.assertLessEqual(p["reach_r16"], p["reach_r32"] + 1e-9)

    def test_group_advance_two_per_group(self):
        gd = load_groups_2026()
        br = load_bracket_2026()
        sim = tmt.simulate_tournament(build_engine(), gd, br, n_sims=300, seed=3)
        for g, gteams in sim["groups"].items():
            win = sum(gteams[t]["win"] for t in gteams)
            self.assertAlmostEqual(win, 1.0, places=6, msg=g)  # one winner per group

    def test_group_stage_predictions_cover_all_matches(self):
        gd = load_groups_2026()
        preds = tmt.predict_group_stage(build_engine(), gd["groups"], hosts=gd["hosts"])
        total = sum(len(v) for v in preds.values())
        self.assertEqual(total, 72)  # 12 groups x 6 matches


if __name__ == "__main__":
    unittest.main()

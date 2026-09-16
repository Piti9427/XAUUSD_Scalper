import unittest

from scripts.smc.funnel import SetupFunnel


class SetupFunnelTests(unittest.TestCase):
    def test_funnel_tracks_stages_and_rejects(self):
        funnel = SetupFunnel()
        funnel.bump("detected")
        funnel.bump("structure_qualified")
        funnel.reject("nearest_r_below_1_5")
        funnel.reject("nearest_r_below_1_5")
        funnel.bump("closed")
        data = funnel.as_dict()
        self.assertEqual(data["counts"]["detected"], 1)
        self.assertEqual(data["counts"]["structure_qualified"], 1)
        self.assertEqual(data["counts"]["closed"], 1)
        self.assertEqual(data["reject_reasons"]["nearest_r_below_1_5"], 2)

    def test_unknown_stage_raises(self):
        funnel = SetupFunnel()
        with self.assertRaises(ValueError):
            funnel.bump("not_a_stage")


if __name__ == "__main__":
    unittest.main()

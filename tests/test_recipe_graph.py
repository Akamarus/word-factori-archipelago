import unittest

from word_factori.recipe_graph import RecipeGraph, minimal_capability_sets


class RecipeGraphTests(unittest.TestCase):
    def test_fixed_point_follows_machine_hyperedges(self):
        payload = {
            "oIFactory": {"I": "I"},
            "oBend": {"I": "C"},
            "oMerger2": {"C C01": "O"},
        }
        graph = RecipeGraph.from_payload(payload)
        self.assertNotIn("O", graph.reachable({"Bender Access", "Merger2 Access"}))
        self.assertIn("O", graph.reachable({"Bender Access", "Reflection Access", "Merger2 Access"}))

    def test_rotations_reflections_and_symmetries_are_deterministic(self):
        graph = RecipeGraph.from_payload({
            "oIFactory": {"I": "I"},
            "horizontal_symmetries": ["I"],
        })
        self.assertIn("I01", graph.reachable(set()))
        self.assertIn("I1", graph.reachable({"Rotation Access"}))
        reflected = graph.reachable({"Reflection Access"})
        self.assertIn("I21", reflected)

    def test_minimal_capability_enumeration_removes_supersets(self):
        graph = RecipeGraph.from_payload({
            "oIFactory": {"I": "I"},
            "oBend": {"I": "C"},
            "oMerger2": {"I I": "C"},
        })
        minima = minimal_capability_sets(graph, "C", {"Bender Access", "Merger2 Access"})
        self.assertEqual({frozenset({"Bender Access"}), frozenset({"Merger2 Access"})}, set(minima))

    def test_discovery_route_does_not_gain_unlisted_capabilities(self):
        graph = RecipeGraph.from_payload({
            "oIFactory": {"I": "I"},
            "oBend": {"I": "C"},
            "oMerger2": {"I I": "V"},
        })
        reachable = graph.reachable({"Bender Access"})
        self.assertIn("C", reachable)
        self.assertNotIn("V", reachable)


if __name__ == "__main__":
    unittest.main()

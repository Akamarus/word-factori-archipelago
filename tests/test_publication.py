import unittest

from tools.build_release import ROOT, include


class PublicationTests(unittest.TestCase):
    def test_release_excludes_temporary_live_rooms(self):
        generated_room = ROOT / "tests" / "live-room-example" / "AP_seed.archipelago"

        self.assertFalse(include(generated_room))


if __name__ == "__main__":
    unittest.main()

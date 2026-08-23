import json
import tempfile
import unittest
from pathlib import Path

from word_factori.save import find_save


class SaveDiscoveryTests(unittest.TestCase):
    def test_custom_campaign_save_is_scoped_to_account_and_mod(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            factori = local / "factori"
            account = factori / "test-account"
            account.mkdir(parents=True)
            (factori / "user_ref.json").write_text(
                json.dumps({"most_recent_steam": "test-account"}), encoding="utf-8"
            )
            base_save = account / "save.json"
            base_save.write_text("{}", encoding="utf-8")
            mod_save = account / "mods" / "word factori archipelago" / "save.json"
            mod_save.parent.mkdir(parents=True)
            mod_save.write_text("{}", encoding="utf-8")

            found = find_save(local, Path("mods") / "word factori archipelago")

            self.assertEqual(mod_save, found)


if __name__ == "__main__":
    unittest.main()

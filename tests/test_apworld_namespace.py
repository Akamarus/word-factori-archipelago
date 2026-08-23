import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class APWorldNamespaceTests(unittest.TestCase):
    def test_overlay_dependency_graph_loads_under_archipelago_world_namespace(self):
        script = textwrap.dedent(f"""
            import importlib
            import importlib.util
            import sys
            import types

            package_path = {str(ROOT / "word_factori")!r}
            worlds = types.ModuleType("worlds")
            worlds.__path__ = []
            spec = importlib.util.spec_from_file_location(
                "worlds.word_factori",
                package_path + "/__init__.py",
                submodule_search_locations=[package_path],
            )
            package = importlib.util.module_from_spec(spec)
            sys.modules["worlds"] = worlds
            sys.modules["worlds.word_factori"] = package

            renderer = importlib.import_module("worlds.word_factori.overlay_renderer")
            model = importlib.import_module("worlds.word_factori.overlay_model")
            supervisor = importlib.import_module("worlds.word_factori.overlay_supervisor")

            view = model.snapshot(model.OverlayState())
            assert view.ledger_rows == ()

            called = []
            renderer.overlay_process_main = lambda connection, config: called.append((connection, config))

            class Connection:
                def __init__(self):
                    self.closed = False

                def close(self):
                    self.closed = True

            connection = Connection()
            supervisor._default_renderer_target(connection, {{"enabled": True}})
            assert called == [(connection, {{"enabled": True}})]
            assert connection.closed
        """)

        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()

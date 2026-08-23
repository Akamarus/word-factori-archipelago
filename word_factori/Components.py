from worlds.LauncherComponents import Component, Type, components, launch

# Keep the spawn-only renderer visible to frozen launcher module discovery.
# The renderer is deliberately Kivy-free until its child entry point executes.
from . import overlay_renderer as _overlay_renderer


def run_client(*args: str) -> None:
    from .client import launch_client
    launch(launch_client, name="Word Factori Client", args=args)


components.append(Component("Word Factori Client", func=run_client, game_name="Word Factori", component_type=Type.CLIENT, supports_uri=True))

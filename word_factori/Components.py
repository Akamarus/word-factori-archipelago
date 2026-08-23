from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client import launch_client
    launch(launch_client, name="Word Factori Client", args=args)


components.append(Component("Word Factori Client", func=run_client, game_name="Word Factori", component_type=Type.CLIENT, supports_uri=True))

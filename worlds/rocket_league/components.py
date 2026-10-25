from worlds.LauncherComponents import Component, Type, components, icon_paths, launch


# The launcher looks up Component.icon in icon_paths before building its cards.
# APWorld resources use the "ap:" path format documented by Archipelago.
icon_paths["rocket_league"] = "ap:worlds.rocket_league/assets/rocket_league_archipelago.png"


def run_client(*args: str) -> None:
    from .client.launch import launch_client
    launch(launch_client, name="Rocket League Client", args=args)


components.append(Component(
    "Rocket League Client",
    func=run_client,
    icon="rocket_league",
    game_name="Rocket League",
    component_type=Type.CLIENT,
    supports_uri=True,
))

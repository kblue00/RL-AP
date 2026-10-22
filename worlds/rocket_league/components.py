from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client.launch import launch_client
    launch(launch_client, name="Rocket League Client", args=args)


components.append(Component(
    "Rocket League Client",
    func=run_client,
    game_name="Rocket League",
    component_type=Type.CLIENT,
    supports_uri=True,
))

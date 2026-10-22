BASE_LOCATION_ID = 12_345_000
GOAL_BASE_ID = 12_345_100
SHOT_BASE_ID = 12_345_200
DEMO_BASE_ID = 12_345_300
SAVE_BASE_ID = 12_345_400
ASSIST_BASE_ID = 12_345_500
VICTORY_LOCATION_ID = 12_345_999

WIN_LOCATION_NAMES = tuple(f"Win Match {i}" for i in range(1, 21))
GOAL_LOCATION_NAMES = tuple(f"Score Goal {i} in a Match" for i in range(1, 8))
SHOT_LOCATION_NAMES = tuple(f"Shot on Goal {i}" for i in range(1, 6))
DEMO_LOCATION_NAMES = tuple(f"Demo {i} in a Match" for i in range(1, 4))
SAVE_LOCATION_NAMES = tuple(f"Save {i} in a Match" for i in range(1, 6))
ASSIST_LOCATION_NAMES = tuple(f"Assist {i} in a Match" for i in range(1, 6))
VICTORY_LOCATION_NAME = "Final Challenge: Win Matches"

LOCATION_NAME_TO_ID = {
    **{name: BASE_LOCATION_ID + i for i, name in enumerate(WIN_LOCATION_NAMES, 1)},
    **{name: GOAL_BASE_ID + i for i, name in enumerate(GOAL_LOCATION_NAMES, 1)},
    **{name: SHOT_BASE_ID + i for i, name in enumerate(SHOT_LOCATION_NAMES, 1)},
    **{name: DEMO_BASE_ID + i for i, name in enumerate(DEMO_LOCATION_NAMES, 1)},
    **{name: SAVE_BASE_ID + i for i, name in enumerate(SAVE_LOCATION_NAMES, 1)},
    **{name: ASSIST_BASE_ID + i for i, name in enumerate(ASSIST_LOCATION_NAMES, 1)},
    VICTORY_LOCATION_NAME: VICTORY_LOCATION_ID,
}


def create_locations(world, region) -> None:
    from .world import RocketLeagueLocation

    names = list(WIN_LOCATION_NAMES[:world.options.win_checks.value])
    names.extend(GOAL_LOCATION_NAMES)
    names.extend(SHOT_LOCATION_NAMES)
    names.extend(DEMO_LOCATION_NAMES)
    names.extend(SAVE_LOCATION_NAMES)
    if world.options.non1v1_mode.value:
        names.extend(ASSIST_LOCATION_NAMES)
    names.append(VICTORY_LOCATION_NAME)
    for name in names:
        region.locations.append(RocketLeagueLocation(world.player, name, LOCATION_NAME_TO_ID[name], region))

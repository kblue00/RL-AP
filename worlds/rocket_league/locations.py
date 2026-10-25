BASE_LOCATION_ID = 12_345_000
GOAL_BASE_ID = 12_345_100
SHOT_BASE_ID = 12_345_200
DEMO_BASE_ID = 12_345_300
SAVE_BASE_ID = 12_345_400
ASSIST_BASE_ID = 12_345_500
MVP_BASE_ID = 12_345_600
MVP_LOCATION_ID = MVP_BASE_ID  # Legacy alias for the first MVP location.
VICTORY_LOCATION_ID = 12_345_999

WIN_LOCATION_NAMES = tuple(f"Win Match {i}" for i in range(1, 21))
GOAL_LOCATION_NAMES = tuple(f"Score Goal {i} in a Match" for i in range(1, 8))
SHOT_LOCATION_NAMES = tuple(f"Shot on Goal {i}" for i in range(1, 11))
DEMO_LOCATION_NAMES = tuple(f"Demo {i} in a Match" for i in range(1, 7))
SAVE_LOCATION_NAMES = tuple(f"Save {i} in a Match" for i in range(1, 7))
ASSIST_LOCATION_NAMES = tuple(f"Assist {i} in a Match" for i in range(1, 7))
MVP_LOCATION_NAMES = tuple(
    "Earn MVP in a Match" if i == 1 else f"Earn MVP {i} in a Match"
    for i in range(1, 21)
)
VICTORY_LOCATION_NAME = "Final Challenge: Win Matches"

LOCATION_NAME_TO_ID = {
    **{name: BASE_LOCATION_ID + i for i, name in enumerate(WIN_LOCATION_NAMES, 1)},
    **{name: GOAL_BASE_ID + i for i, name in enumerate(GOAL_LOCATION_NAMES, 1)},
    **{name: SHOT_BASE_ID + i for i, name in enumerate(SHOT_LOCATION_NAMES, 1)},
    **{name: DEMO_BASE_ID + i for i, name in enumerate(DEMO_LOCATION_NAMES, 1)},
    **{name: SAVE_BASE_ID + i for i, name in enumerate(SAVE_LOCATION_NAMES, 1)},
    **{name: ASSIST_BASE_ID + i for i, name in enumerate(ASSIST_LOCATION_NAMES, 1)},
    **{name: MVP_BASE_ID + i - 1 for i, name in enumerate(MVP_LOCATION_NAMES, 1)},
    VICTORY_LOCATION_NAME: VICTORY_LOCATION_ID,
}


def create_locations(world, region) -> None:
    from .world import RocketLeagueLocation

    names = list(WIN_LOCATION_NAMES[:world.options.win_checks.value])
    names.extend(GOAL_LOCATION_NAMES[:world.options.goals_per_match.value])
    names.extend(SHOT_LOCATION_NAMES[:world.options.shots_on_goal_per_match.value])
    names.extend(DEMO_LOCATION_NAMES[:world.options.demos_per_match.value])
    names.extend(SAVE_LOCATION_NAMES[:world.options.saves_per_match.value])
    if world.options.non1v1_mode.value:
        names.extend(ASSIST_LOCATION_NAMES[:world.options.assists_per_match.value])
        names.extend(MVP_LOCATION_NAMES[:world.options.mvp_checks.value])
    names.append(VICTORY_LOCATION_NAME)
    for name in names:
        region.locations.append(RocketLeagueLocation(world.player, name, LOCATION_NAME_TO_ID[name], region))


def count_fillable_locations(options) -> int:
    count = (
        options.win_checks.value
        + options.goals_per_match.value
        + options.shots_on_goal_per_match.value
        + options.demos_per_match.value
        + options.saves_per_match.value
    )
    if options.non1v1_mode.value:
        count += options.assists_per_match.value + options.mvp_checks.value
    return count

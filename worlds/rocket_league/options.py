from dataclasses import dataclass

from Options import OptionError, OptionGroup, PerGameCommonOptions, Range, Toggle


class WinChecks(Range):
    """How many matches won are locations"""
    display_name = "Win Checks"
    range_start = 1
    range_end = 20
    default = 5


class WinTicketsInPool(Range):
    """You must collect the specified amount of Win Tickets before achieving goal - How many Win Tickets are included in the item pool."""
    display_name = "Win Tickets in Pool"
    range_start = 0
    range_end = 35
    default = 10


class WinTicketsRequired(Range):
    """Tickets required to unlock the final match-win challenge."""
    display_name = "Win Tickets Required"
    range_start = 0
    range_end = 35
    default = 5


class MatchesToWin(Range):
    """Once specified amount of Win Tickets have be aquired, how many additional matches must be won to goal."""
    display_name = "Matches to Win"
    range_start = 1
    range_end = 20
    default = 3


class Non1v1Mode(Toggle):
    """Enables Assist checks for game modes with more than one teammate."""
    display_name = "Non1v1 Mode"
    description = 'Enables "Assists" as checks for playing non1v1 modes'


@dataclass
class RocketLeagueOptions(PerGameCommonOptions):
    win_checks: WinChecks
    win_tickets_in_pool: WinTicketsInPool
    win_tickets_required: WinTicketsRequired
    matches_to_win: MatchesToWin
    non1v1_mode: Non1v1Mode


option_groups = [
    OptionGroup("Goal and Item Pool", [WinChecks, WinTicketsInPool, WinTicketsRequired, MatchesToWin, Non1v1Mode])
]


def validate_options(options: RocketLeagueOptions, max_locations: int) -> None:
    if options.win_tickets_required.value > options.win_tickets_in_pool.value:
        raise OptionError("Win Tickets Required cannot exceed Win Tickets in Pool.")
    if options.win_tickets_in_pool.value > max_locations:
        raise OptionError(f"Win Tickets in Pool cannot exceed the {max_locations} item locations in this seed.")

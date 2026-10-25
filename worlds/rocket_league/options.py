from dataclasses import dataclass

from Options import DeathLink, OptionError, OptionGroup, PerGameCommonOptions, Range, Toggle


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


class GoalsPerMatch(Range):
    """Number of goal milestones checked in each match."""
    display_name = "Goals per Match"
    range_start = 3
    range_end = 7
    default = 7


class ShotsOnGoalPerMatch(Range):
    """Number of shot-on-goal milestones checked in each match."""
    display_name = "Shots on Goal per Match"
    range_start = 3
    range_end = 10
    default = 5


class SavesPerMatch(Range):
    """Number of save milestones checked in each match."""
    display_name = "Saves per Match"
    range_start = 1
    range_end = 6
    default = 5


class AssistsPerMatch(Range):
    """Number of assist milestones checked in each non-1v1 match.
         - Only included if non1v1-mode is enabled"""
    display_name = "Assists per Match"
    range_start = 1
    range_end = 6
    default = 5


class DemosPerMatch(Range):
    """Number of demolition milestones checked in each match."""
    display_name = "Demos per Match"
    range_start = 1
    range_end = 6
    default = 3


class MVPChecks(Range):
    """Number of MVP awards to earn across separate matches for MVP checks.
         - Only included if non1v1-mode is enabled"""
    display_name = "MVPs"
    description = "Number of MVP awards required for the MVP checks; each requires MVP in a separate match."
    range_start = 1
    range_end = 20
    default = 1


class Non1v1Mode(Toggle):
    """Enables Assist and MVP checks for non-1v1 game modes."""
    display_name = "Non1v1 Mode"
    description = 'Enables "Assists" and "MVP" checks for playing non1v1 modes'


class AbilityUnlocks(Toggle):
    """Include ability unlock items in the item pool.
         - Jump/Flip, Boost, Ball Cam, Air Roll, Brake"""
    display_name = "Ability Unlocks"
    default = 1


class TrapPercentage(Range):
    """Percentage of filler item slots that become traps."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 15


class ScoreboardTrapWeight(Range):
    display_name = "Scoreboard Trap Weight"
    range_start = 0
    range_end = 10
    default = 1


class BallCamTrapWeight(Range):
    display_name = "Ball Cam Trap Weight"
    range_start = 0
    range_end = 10
    default = 1


class JumpTrapWeight(Range):
    display_name = "Jump Trap Weight"
    range_start = 0
    range_end = 10
    default = 1


class BoostTrapWeight(Range):
    display_name = "Boost Trap Weight"
    range_start = 0
    range_end = 10
    default = 1


class SpinTrapWeight(Range):
    display_name = "Spin Trap Weight"
    range_start = 0
    range_end = 10
    default = 1


@dataclass
class RocketLeagueOptions(PerGameCommonOptions):
    win_checks: WinChecks
    win_tickets_in_pool: WinTicketsInPool
    win_tickets_required: WinTicketsRequired
    matches_to_win: MatchesToWin
    goals_per_match: GoalsPerMatch
    shots_on_goal_per_match: ShotsOnGoalPerMatch
    saves_per_match: SavesPerMatch
    assists_per_match: AssistsPerMatch
    demos_per_match: DemosPerMatch
    mvp_checks: MVPChecks
    non1v1_mode: Non1v1Mode
    ability_unlocks: AbilityUnlocks
    death_link: DeathLink
    trap_percentage: TrapPercentage
    scoreboard_trap_weight: ScoreboardTrapWeight
    ball_cam_trap_weight: BallCamTrapWeight
    jump_trap_weight: JumpTrapWeight
    boost_trap_weight: BoostTrapWeight
    spin_trap_weight: SpinTrapWeight


option_groups = [
    OptionGroup("Goal and Item Pool", [
        WinChecks, WinTicketsInPool, WinTicketsRequired, MatchesToWin, Non1v1Mode, AbilityUnlocks,
    ]),
    OptionGroup("Per-Match Checks", [
        GoalsPerMatch, ShotsOnGoalPerMatch, SavesPerMatch, AssistsPerMatch, DemosPerMatch, MVPChecks,
    ]),
    OptionGroup("DeathLink and Traps", [
        DeathLink, TrapPercentage, ScoreboardTrapWeight, BallCamTrapWeight,
        JumpTrapWeight, BoostTrapWeight, SpinTrapWeight,
    ]),
]


def validate_options(options: RocketLeagueOptions, max_locations: int) -> None:
    if options.win_tickets_required.value > options.win_tickets_in_pool.value:
        raise OptionError("Win Tickets Required cannot exceed Win Tickets in Pool.")
    ability_item_count = 5 if options.ability_unlocks.value else 0
    max_tickets = max_locations - ability_item_count
    if options.win_tickets_in_pool.value > max_tickets:
        raise OptionError(
            f"Win Tickets in Pool cannot exceed {max_tickets} with the selected Ability Unlocks setting."
        )
    if options.trap_percentage.value and not any((
        options.scoreboard_trap_weight.value,
        options.ball_cam_trap_weight.value,
        options.jump_trap_weight.value,
        options.boost_trap_weight.value,
        options.spin_trap_weight.value,
    )):
        raise OptionError("At least one trap weight must be greater than zero when Trap Percentage is above 0.")

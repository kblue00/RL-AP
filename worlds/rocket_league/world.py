from collections.abc import Mapping
from typing import Any

from BaseClasses import Item, Location, Region
from worlds.AutoWorld import World

from . import items, locations, web_world
from .options import RocketLeagueOptions, validate_options


class RocketLeagueLocation(Location):
    game = "Rocket League"


class RocketLeagueWorld(World):
    """Randomizes match milestones and Win Tickets for Rocket League."""

    game = "Rocket League"
    web = web_world.RocketLeagueWebWorld()
    origin_region_name = "Rocket League"
    options_dataclass = RocketLeagueOptions
    options: RocketLeagueOptions
    item_name_to_id = items.ITEM_NAME_TO_ID
    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_groups = {
        "Win Tickets": {"Win Ticket"},
        "Abilities": {"Boost", "Ball Cam", "Jump/Flip", "Air Roll", "Brake"},
        "Quick Chat Filler": set(items.FILLER_ITEMS),
        "Traps": set(items.TRAP_ITEMS),
    }
    location_name_groups = {
        "Match Wins": set(locations.WIN_LOCATION_NAMES),
        "Goals": set(locations.GOAL_LOCATION_NAMES),
        "Shots on Goal": set(locations.SHOT_LOCATION_NAMES),
        "Demolitions": set(locations.DEMO_LOCATION_NAMES),
        "Saves": set(locations.SAVE_LOCATION_NAMES),
        "Assists": set(locations.ASSIST_LOCATION_NAMES),
        "MVP": set(locations.MVP_LOCATION_NAMES),
        "Goal": {locations.VICTORY_LOCATION_NAME},
    }
    data_version = 4

    def generate_early(self) -> None:
        available = locations.count_fillable_locations(self.options)
        validate_options(self.options, available)

    def create_regions(self) -> None:
        region = Region("Rocket League", self.player, self.multiworld)
        self.multiworld.regions.append(region)
        locations.create_locations(self, region)

    def set_rules(self) -> None:
        final_location = self.multiworld.get_location(locations.VICTORY_LOCATION_NAME, self.player)
        required = self.options.win_tickets_required.value
        if required:
            final_location.access_rule = lambda state, count=required: state.has("Win Ticket", self.player, count)
        if self.options.ability_unlocks.value:
            for name in locations.DEMO_LOCATION_NAMES[:self.options.demos_per_match.value]:
                demo_location = self.multiworld.get_location(name, self.player)
                demo_location.access_rule = lambda state: (
                    state.has("Boost", self.player) or state.has("Jump/Flip", self.player)
                )
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def create_items(self) -> None:
        victory_location = self.multiworld.get_location(locations.VICTORY_LOCATION_NAME, self.player)
        victory_location.place_locked_item(self.create_item("Victory"))
        items.create_item_pool(self)

    def create_item(self, name: str) -> Item:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return self.random.choice(items.FILLER_ITEMS)

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            "win_checks": self.options.win_checks.value,
            "win_tickets_in_pool": self.options.win_tickets_in_pool.value,
            "win_tickets_required": self.options.win_tickets_required.value,
            "matches_to_win": self.options.matches_to_win.value,
            "goals_per_match": self.options.goals_per_match.value,
            "shots_on_goal_per_match": self.options.shots_on_goal_per_match.value,
            "saves_per_match": self.options.saves_per_match.value,
            "assists_per_match": self.options.assists_per_match.value,
            "demos_per_match": self.options.demos_per_match.value,
            "mvp_checks": self.options.mvp_checks.value,
            "non1v1_mode": bool(self.options.non1v1_mode.value),
            "death_link_enabled": bool(self.options.death_link.value),
            "trap_percentage": self.options.trap_percentage.value,
            "trap_weights": {
                "Scoreboard Trap": self.options.scoreboard_trap_weight.value,
                "Ball Cam Trap": self.options.ball_cam_trap_weight.value,
                "Jump Trap": self.options.jump_trap_weight.value,
                "Boost Trap": self.options.boost_trap_weight.value,
                "Spin Trap": self.options.spin_trap_weight.value,
            },
            "boost_unlock_enabled": bool(self.options.ability_unlocks.value),
            "ball_cam_unlock_enabled": bool(self.options.ability_unlocks.value),
            "jump_flip_unlock_enabled": bool(self.options.ability_unlocks.value),
            "air_roll_unlock_enabled": bool(self.options.ability_unlocks.value),
            "brake_unlock_enabled": bool(self.options.ability_unlocks.value),
        }

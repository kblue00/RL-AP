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
    item_name_groups = {"Win Tickets": {"Win Ticket"}, "Quick Chat Filler": set(items.FILLER_ITEMS)}
    location_name_groups = {
        "Match Wins": set(locations.WIN_LOCATION_NAMES),
        "Goals": set(locations.GOAL_LOCATION_NAMES),
        "Shots on Goal": set(locations.SHOT_LOCATION_NAMES),
        "Demolitions": set(locations.DEMO_LOCATION_NAMES),
        "Saves": set(locations.SAVE_LOCATION_NAMES),
        "Assists": set(locations.ASSIST_LOCATION_NAMES),
        "Goal": {locations.VICTORY_LOCATION_NAME},
    }
    data_version = 1

    def generate_early(self) -> None:
        available = self.options.win_checks.value + 20 + (5 if self.options.non1v1_mode.value else 0)
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
            "non1v1_mode": bool(self.options.non1v1_mode.value),
        }

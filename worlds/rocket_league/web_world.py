from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .options import option_groups


class RocketLeagueWebWorld(WebWorld):
    game = "Rocket League"
    theme = "grass"
    tutorials = [Tutorial(
        "Rocket League Setup Guide",
        "How to install the APWorld and connect the Rocket League client.",
        "English",
        "setup_en.md",
        "setup/en",
        ["OpenAI"],
    )]
    option_groups = option_groups

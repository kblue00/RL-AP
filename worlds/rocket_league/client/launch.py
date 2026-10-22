import asyncio

from CommonClient import get_base_parser, handle_url_arg


def launch_client(*args: str) -> None:
    from .rocket_league_client import main

    parser = get_base_parser()
    parser.add_argument("--name", default=None, help="Archipelago slot name")
    parser.add_argument("--player-name", default="DefaultMiserable",
                        help="Rocket League display name used to identify your car")
    parser.add_argument("--player-id", default=None,
                        help="Optional platform identity, e.g. Epic|...|0")
    parser.add_argument("--stats-host", default="127.0.0.1")
    parser.add_argument("--stats-port", default=49123, type=int)
    parser.add_argument("url", nargs="?", help="Archipelago connection URL")
    parsed = handle_url_arg(parser.parse_args(args))
    asyncio.run(main(parsed))

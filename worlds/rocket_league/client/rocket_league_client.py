from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from argparse import Namespace
from pathlib import Path
from typing import Any

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, gui_enabled, logger, server_loop
from MultiServer import mark_raw
from NetUtils import ClientStatus

from ..items import ITEM_NAME_TO_ID
from ..locations import (
    ASSIST_BASE_ID, BASE_LOCATION_ID, DEMO_BASE_ID, GOAL_BASE_ID, SAVE_BASE_ID, SHOT_BASE_ID,
    VICTORY_LOCATION_ID,
)


GAME = "Rocket League"
stats_logger = logging.getLogger("RocketLeagueStats")
stats_logger.propagate = False


class RocketLeagueCommandProcessor(ClientCommandProcessor):
    @mark_raw
    def _cmd_playername(self, name: str = "") -> bool:
        """Show or set the Rocket League display name matched in Stats API updates."""
        name = name.strip()
        if name:
            self.ctx.player_name = name
            self.ctx.unmatched_player_warning_matches.clear()
            self.output(f"Rocket League Stats API player name set to: {name}")
        else:
            self.output(f"Rocket League Stats API player name: {self.ctx.player_name}")
        return True


class RocketLeagueContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = RocketLeagueCommandProcessor

    def __init__(self, server_address: str | None, password: str | None, args: Namespace) -> None:
        super().__init__(server_address, password)
        self.player_name = args.player_name
        self.player_id = args.player_id
        self.stats_host = args.stats_host
        self.stats_port = args.stats_port
        self.slot_data: dict[str, Any] = {}
        self.earned_locations: set[int] = set()
        self.sent_locations: set[int] = set()
        self.player_team: int | None = None
        self.unmatched_player_warning_matches: set[str] = set()
        self.match_guid: str | None = None
        self.match_goals = 0
        self.match_demos = 0
        self.match_shots = 0
        self.match_saves = 0
        self.match_assists = 0
        self.wins = 0
        self.final_start_wins: int | None = None
        self.victory_sent = False
        self.goal_status_sent = False
        self.last_ended_match: str | None = None
        self.stats_task: asyncio.Task[None] | None = None
        self.state_path = Path(Utils.user_path("rocket_league_ap_state.json"))
        self.seed_name = ""
        self.progress_profiles: dict[str, dict[str, Any]] = {}
        self.load_progress()

    def progress_key(self, seed_name: str | None = None) -> str:
        identity = self.player_id or (self.auth.casefold() if self.auth else self.player_name.casefold())
        return f"{seed_name or self.seed_name or 'unassigned'}|{identity}"

    def load_progress(self) -> None:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.progress_profiles = state.get("profiles", {})
            # Do not restore progress until RoomInfo identifies the active seed.
            # Otherwise legacy/unassigned checks can be copied into a new seed.
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Could not read Rocket League progress file: %s", exc)

    def restore_profile(self, state: dict[str, Any]) -> None:
        self.wins = max(0, int(state.get("wins", 0)))
        self.final_start_wins = state.get("final_start_wins")
        self.victory_sent = bool(state.get("victory_sent", False))
        self.last_ended_match = state.get("last_ended_match")
        self.earned_locations = {int(value) for value in state.get("earned_locations", [])}

    def save_progress(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Each client process gets its own temp file. A fixed .tmp name lets two
        # running clients collide while one is replacing the shared state file.
        temporary = self.state_path.with_name(
            f"{self.state_path.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        self.progress_profiles[self.progress_key()] = {
            "wins": self.wins,
            "final_start_wins": self.final_start_wins,
            "victory_sent": self.victory_sent,
            "last_ended_match": self.last_ended_match,
            "earned_locations": sorted(self.earned_locations),
        }
        try:
            temporary.write_text(json.dumps({"profiles": self.progress_profiles}, indent=2), encoding="utf-8")
            for attempt in range(6):
                try:
                    temporary.replace(self.state_path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        except OSError as exc:
            # A state-file lock must not be mistaken for a dropped Stats API
            # socket; keep processing the live match and retry on the next save.
            logger.warning("Could not save Rocket League progress: %s", exc)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.sent_locations.clear()
            self.goal_status_sent = False
            logger.info("Authenticated to Archipelago slot %s; Stats API player name: %s",
                        self.auth, self.player_name)
            asyncio.create_task(self.sync_after_connect())
        elif cmd == "RoomInfo":
            room_seed = args.get("seed_name", "")
            if room_seed and room_seed != self.seed_name:
                self.seed_name = room_seed
                matching_profile = self.progress_profiles.get(self.progress_key(room_seed))
                # Progress is strictly scoped to the active Archipelago seed and slot.
                # Never migrate unassigned or previous-seed checks into a new profile.
                self.restore_profile(matching_profile or {})
            logger.info("Reached Archipelago room %s; authenticating the Rocket League slot",
                        args.get("seed_name", ""))

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect(game=self.game)

    async def sync_after_connect(self) -> None:
        await self.send_pending_checks()
        await self.maybe_start_final_challenge()

    def selected_player(self, player: dict[str, Any]) -> bool:
        if self.player_id:
            return player.get("PrimaryId") == self.player_id
        return player.get("Name", "").casefold() == self.player_name.casefold()

    async def earn(self, location_id: int, name: str) -> None:
        if location_id in self.earned_locations:
            return
        self.earned_locations.add(location_id)
        self.save_progress()
        await self.send_pending_checks()

    async def send_pending_checks(self) -> None:
        if (not self.server or not self.server.socket or not self.server.socket.open
                or self.server.socket.closed or not self.missing_locations):
            return
        pending = self.earned_locations & self.missing_locations - self.sent_locations
        if pending:
            sent = await self.check_locations(pending)
            self.sent_locations.update(sent)

    def ticket_count(self) -> int:
        ticket_id = ITEM_NAME_TO_ID["Win Ticket"]
        return sum(1 for item in self.items_received if item.item == ticket_id)

    async def handle_stats_message(self, message: dict[str, Any]) -> None:
        event = message.get("Event")
        data = message.get("Data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return
        if not isinstance(data, dict):
            return

        stats_logger.info("%s: %s", event or "Stats API event",
                          json.dumps(data, ensure_ascii=False, separators=(",", ":")))

        guid = data.get("MatchGuid")
        if guid and guid != self.match_guid:
            self.match_guid = guid
            self.match_goals = self.match_demos = self.match_shots = self.match_saves = self.match_assists = 0
            self.player_team = None
            stats_logger.info("Match detected: %s", guid)

        if event == "UpdateState":
            players = data.get("Players", [])
            player = next((entry for entry in players if self.selected_player(entry)), None)
            if player is None and players and self.match_guid not in self.unmatched_player_warning_matches:
                names = [entry.get("Name", "<unnamed>") for entry in players]
                logger.warning(
                    "Rocket League player '%s' was not found in this match's Stats API updates. "
                    "Players reported: %s. Use /playername <name> to select the correct player.",
                    self.player_name, ", ".join(names),
                )
                if self.match_guid:
                    self.unmatched_player_warning_matches.add(self.match_guid)
            if player:
                self.player_team = player.get("TeamNum", self.player_team)
                goals = int(player.get("Goals", 0) or 0)
                demos = int(player.get("Demos", 0) or 0)
                saves = int(player.get("Saves", 0) or 0)
                assists = int(player.get("Assists", 0) or 0)
                for count in range(self.match_goals + 1, min(goals, 7) + 1):
                    await self.earn(GOAL_BASE_ID + count, f"Score Goal {count} in a Match")
                for count in range(self.match_demos + 1, min(demos, 3) + 1):
                    await self.earn(DEMO_BASE_ID + count, f"Demo {count} in a Match")
                for count in range(self.match_saves + 1, min(saves, 5) + 1):
                    await self.earn(SAVE_BASE_ID + count, f"Save {count} in a Match")
                if self.slot_data.get("non1v1_mode", False):
                    for count in range(self.match_assists + 1, min(assists, 5) + 1):
                        await self.earn(ASSIST_BASE_ID + count, f"Assist {count} in a Match")
                self.match_goals = max(self.match_goals, goals)
                self.match_demos = max(self.match_demos, demos)
                self.match_saves = max(self.match_saves, saves)
                self.match_assists = max(self.match_assists, assists)

        elif event == "StatfeedEvent":
            target = data.get("MainTarget", {})
            is_player = target.get("Name", "").casefold() == self.player_name.casefold()
            if is_player and data.get("EventName") == "Shot" and data.get("Type") == "Shot on Goal":
                self.match_shots += 1
                if self.match_shots <= 5:
                    await self.earn(SHOT_BASE_ID + self.match_shots, f"Shot on Goal {self.match_shots}")

        elif event == "MatchEnded":
            if guid and guid == self.last_ended_match:
                return
            winner = data.get("WinnerTeamNum")
            if self.player_team is not None and winner == self.player_team:
                self.wins += 1
                self.save_progress()
                win_limit = int(self.slot_data.get("win_checks", 5))
                if self.wins <= win_limit:
                    await self.earn(BASE_LOCATION_ID + self.wins, f"Win Match {self.wins}")
            self.last_ended_match = guid
            self.save_progress()

    async def maybe_start_final_challenge(self) -> None:
        if self.victory_sent:
            await self.send_goal_status()
            return
        required = int(self.slot_data.get("win_tickets_required", 5))
        if self.final_start_wins is None and self.ticket_count() >= required:
            self.final_start_wins = self.wins
            self.save_progress()
            logger.info("Win Ticket requirement met. Final challenge: win %s more matches.",
                        self.slot_data.get("matches_to_win", 3))
        if self.final_start_wins is None or self.victory_sent:
            return
        matches_required = int(self.slot_data.get("matches_to_win", 3))
        if self.wins - self.final_start_wins >= matches_required:
            self.victory_sent = True
            self.save_progress()
            await self.earn(VICTORY_LOCATION_ID, "Final Challenge: Win Matches")
            await self.send_goal_status()
            logger.info("Goal complete: final match-win challenge cleared")

    async def send_goal_status(self) -> None:
        if self.server and not self.server.socket.closed and not self.goal_status_sent:
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self.goal_status_sent = True

    async def stats_loop(self) -> None:
        decoder = json.JSONDecoder()
        while not self.exit_event.is_set():
            try:
                stats_logger.info("Connecting to Rocket League Stats API at %s:%d",
                                  self.stats_host, self.stats_port)
                reader, writer = await asyncio.open_connection(self.stats_host, self.stats_port)
                stats_logger.info("Rocket League Stats API connected")
                buffer = ""
                while not self.exit_event.is_set():
                    chunk = await reader.read(65536)
                    if not chunk:
                        raise ConnectionError("Stats API connection closed")
                    buffer += chunk.decode("utf-8", errors="replace")
                    while buffer:
                        buffer = buffer.lstrip()
                        try:
                            message, end = decoder.raw_decode(buffer)
                        except json.JSONDecodeError:
                            break
                        buffer = buffer[end:]
                        if isinstance(message, dict):
                            await self.handle_stats_message(message)
                    await self.send_pending_checks()
                    await self.maybe_start_final_challenge()
                writer.close()
                await writer.wait_closed()
            except asyncio.CancelledError:
                raise
            except (OSError, ConnectionError) as exc:
                stats_logger.warning("Rocket League Stats API unavailable: %s; retrying in 5 seconds", exc)
                await asyncio.sleep(5)

    def make_gui(self):
        from kvui import GameManager, MDBoxLayout, MDLabel, dp

        class RocketLeagueManager(GameManager):
            base_title = "Archipelago Rocket League Client"
            logging_pairs = [("Client", "Archipelago"), ("RocketLeagueStats", "Stats")]

            def build(manager):
                root = super().build()
                manager.rocket_league_panel = MDBoxLayout(
                    orientation="vertical", spacing=dp(16), padding=dp(24),
                )
                manager.ticket_label = MDLabel(
                    text="Win Tickets: 0/0", size_hint_y=None, height=dp(48), font_size=dp(24),
                )
                manager.wins_label = MDLabel(
                    text="Matches Won: 0/0", size_hint_y=None, height=dp(48), font_size=dp(24),
                )
                manager.rocket_league_panel.add_widget(manager.ticket_label)
                manager.rocket_league_panel.add_widget(manager.wins_label)
                manager.add_client_tab("Rocket League", manager.rocket_league_panel)
                manager.update_rocket_league_stats()
                return root

            def update_rocket_league_stats(manager):
                ctx = manager.ctx
                tickets_required = int(ctx.slot_data.get("win_tickets_required", 5))
                matches_required = int(ctx.slot_data.get("matches_to_win", 3))
                tickets_received = ctx.ticket_count()
                matches_won = (max(0, ctx.wins - ctx.final_start_wins)
                               if ctx.final_start_wins is not None else 0)
                manager.ticket_label.text = f"Win Tickets: {tickets_received}/{tickets_required}"
                manager.wins_label.text = f"Matches Won: {matches_won}/{matches_required}"

            def update_texts(manager, dt):
                super().update_texts(dt)
                if hasattr(manager, "ticket_label"):
                    manager.update_rocket_league_stats()

        return RocketLeagueManager


async def main(args: Namespace) -> None:
    ctx = RocketLeagueContext(args.connect, args.password, args)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="Archipelago server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    ctx.stats_task = asyncio.create_task(ctx.stats_loop(), name="Rocket League Stats API loop")
    try:
        await ctx.exit_event.wait()
    finally:
        if ctx.stats_task:
            ctx.stats_task.cancel()
            await asyncio.gather(ctx.stats_task, return_exceptions=True)
        await ctx.shutdown()

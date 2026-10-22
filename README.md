# Rocket League Archipelago

An Archipelago world and client for Rocket League. The client connects to Archipelago normally and reads match events from Rocket League's local Stats API. It does not hook into the game process.

This is an early, playable version focused on match-stat checks and the Win Ticket goal. Input unlocks, traps, and DeathLink are not implemented.

## Features

- Win Ticket collection followed by a configurable final match-win challenge.
- Configurable match-win checks (1–20).
- Per-match checks for goals (up to 7), shots on goal (up to 5), demos (up to 3), and saves (up to 5).
- Optional **Non1v1 Mode** checks for assists (up to 5 per match).
- Quick-chat themed filler items. They have no in-game effect.
- Archipelago Launcher client with Stats API match detection and progress tracking.

## Install

Download `rocket_league.apworld` from Releases and install it in Archipelago's `custom_worlds` folder. Restart the Launcher after installation.

Enable Rocket League's Stats API before starting the game. In your RL install folder, `TAGame\Config\TAStatsAPI.ini`, set:

```ini
[TAGame.MatchStatsExporter_TA]
PacketSendRate=1
Port=49123
WebPort=49124
```

Restart Rocket League after editing the file. Then launch **Rocket League Client** from the Archipelago Launcher, check the Stats tab to ensure connection to the Rocket League API was successful, set `/setplayername YOURROCKETLEAGUENAME` to your display name within Rocket League (It must match exactly), and connect to the multiworld.

Play!

## ai-Usage Disclosure

This project is heavily vibe coded, using Codex/ChatGPT. However, everything has been thouroughly human tested before publishing.
AI was used to build the AP client, APworld, and file structure.



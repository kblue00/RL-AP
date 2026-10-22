# Rocket League Archipelago Setup

## Install the APWorld

Copy `rocket_league.apworld` into the Archipelago `custom_worlds` folder, then restart the Archipelago Launcher. Generate a Rocket League YAML template, set the options, and generate a multiworld as usual.

## Enable Rocket League Stats API

Before launching Rocket League, find your RL install foler, probably named `rocketleague`. Go to `TAGame\Config` and edit `TAStatsAPI.ini` (or create it if needed) and add:

```ini
[TAGame.MatchStatsExporter_TA]
PacketSendRate=1
Port=49123
WebPort=49124
```

Restart Rocket League after saving the file. The API emits match data over a local TCP stream while a match is active.

## Launch the AP client

Open the Archipelago Launcher and select **Rocket League Client**. If opened from a room slot link, the server and slot are filled in automatically. Set `/playername` to your Rocket League display name.
Check the Stats tab to ensure connection to the Rocket League API was successful.

Connect to the multiworld with the server & server port. Locations earned before connecting are saved locally and sent after the client connects.

## Current scope

- Win Ticket items count toward the configured ticket gate.
- Goal, shot-on-goal, demo, saves, and win milestones become checks. Enable **Non1v1 Mode** to add up to five per-match assist checks.
- Quick Chat items are filler and have no in-game effect.
- Control unlocks, input blocking, and traps are not part of this first integration.

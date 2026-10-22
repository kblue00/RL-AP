# Rocket League

This Archipelago integration uses Rocket League's local Stats API to recognize match wins, goals, shots on goal, demos, saves, and—when **Non1v1 Mode** is enabled—assists. It does not hook into the game process.

Collect the configured Win Tickets from randomized locations. Once the required ticket count is reached, win the configured number of additional matches to complete the goal.

Checks are tracked as per-match milestones: up to 7 goals, 5 shots on goal, 3 demos, and 5 saves. **Non1v1 Mode** adds up to 5 assist checks for modes where assists are possible. Save milestones use the game's `Saves` stat, which includes epic saves when the game counts them as saves.

Quick-chat themed items are filler and have no in-game effect. Input unlocks, traps, and DeathLink are not part of this first version.

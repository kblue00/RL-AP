# Rocket League Archipelago

An Archipelago world and client for Rocket League. The client connects to Archipelago normally and reads match events from Rocket League's local Stats API. It does not hook into the game process.

## Features

- Win Ticket collection followed by a configurable final match-win challenge.
   (Place "X" amount of Win Tickets in the item pool, determine how many of them are required to goal, then win "X" amount of additional matches after receiving them.)
- Configurable match-win checks (1–20).
   ("X" amount of matches won is a check)
- Per-match checks for goals (up to 7), shots on goal (up to 6), demos (up to 6), and saves (up to 6).
- Optional **Non1v1 Mode** checks for assists (up to 5 per match) and MVP checks (up to 20).
- Ability Unlocks (Boost, Jump/Flip, Ball Cam, Air Roll, and Brake)
- Quick-chat themed filler items.
- Up to 5 unique traps (Scoreboard, Boost, Spin, Ball Cam, and Jump)
- Archipelago Launcher client with Stats API match detection, progress tracking, and controller to keyboard mapping to allow for input blocking for traps and ability unlocks
- Deathlink support (Getting demoed sends a deathlink, receiving a deathlink disables forward and reverse input)

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

## Moveset Rando Setup

If you'd like to play with ability unlocks enabled (Boost, Jump, Ball Cam, etc), there are a few steps to get it setup to work alongside still allowing online play.
This setup consists of mapping keyboard inputs to the controller.
Real controller input needs to be hidden from Rocket League for this setup to work as well.

1. Download & install HidHide
   https://github.com/nefarius/hidhide
  - Once it is installed, open the application. On the main window, in the bottom right, click the + button. Go to `*RLINSTALLFOLDER*\Binaries\Win64` and select `RocketLeague.exe`
  - In the bottom left of the main window, check the __Inverse application cloak__ box - This makes it so that selected devices will *only* be hidden from whitelisted applications
  - Under the Devices tab, check the box on the controller you're using. This will lock it/hide it from your whitelisted applications

2.  Inside the Rocket League AP Client, in the `Binds ` tab, map each controller button to a keyboard key/mouse button. - These need to match your keyboard bindings within Rocket League. (I.e. if you want A on the controller to Boost, set A to the key that is set to Boost in-game - left_click by default.)
  - Then map the corresponding Rocket League action to each button, so the client will know which button to suppress for restricting each ability. 
  Note: If your keybindings in-game are set to defaults, you'll need to rebind the keys that are double binded. (I.e. driving forward and air pitching down both share W. Set Air Pitch Up to a separate key.)

3. Load into training in-game and test out the controls

Note: Controller inputs are only blocked during an active match and when the game is focused, physical keyboard inputs do not get blocked. Navigating menues with mouse is reccomended for simplicity.

## AI-Usage Disclosure

This project is heavily vibe coded, using Codex/ChatGPT. However, everything has been thouroughly human tested before publishing.
AI was used to build the AP client, APworld, and file structure.


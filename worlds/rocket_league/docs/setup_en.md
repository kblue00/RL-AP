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

Use the **Bindings** tab to set a keyboard or mouse key for each controller 1 button, trigger, D-pad direction, and cardinal stick direction. The action selector is optional: choose **Unassigned** to send the mapped key directly without labeling it as a Rocket League action. When an action is selected, its saved key is also used by that action's trap; controller inputs assigned to Boost are automatically withheld during an active match until the Boost item is received. Configure the separate Spin Trap handbrake / powerslide key in the same tab. Press **Save Controller Mappings** to persist changes. The tab shows whether the AP client detects controller 1. Mouse buttons can be entered as `mouse_left`, `mouse_right`, `mouse_middle`, `mouse_x1`, or `mouse_x2`.

Keyboard binds can still be viewed or changed with slash commands, but this is optional when using the Bindings tab.

## Ability Unlock Setup

1. Download & Install HidHide
2. Add `RocketLeague.exe` to whitelisted applications & enable `Inverse application cloak`
3. In the devices tab, lock your controller. This hides physical controller inputs from Rocket League.
4. In the RL AP Client, bind each controller to it's corresponding keyboard input, matching to how your key binds are set in-game
    - In-game, rebind buttons that are double binded (i.e. reverse and Air Pitch Up)
    - In the AP Client, select the ability that is binded to each button, so the client knows which button to suppress or not suppress.
5. Load into training in-game and test the controls.     

Connect to the multiworld with the server & server port. Locations earned before connecting are saved locally and sent after the client connects.
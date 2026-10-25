# Rocket League Input Bridge prototype

This is an experimental Windows companion for mapping Rocket League controls and blocking selected mapped controls only while the Archipelago client reports an active match.

## Current scope

- Captures keyboard keys and buttons, triggers, and stick directions from XInput controller slots 1–4.
- Allows multiple bindings for Air Roll (and other actions).
- Forwards an XInput controller through a virtual Xbox 360 controller created by HIDMaestro.
- Filters selected controller controls from the virtual output and selected keyboard keys with a low-level Windows keyboard hook.
- Receives match-state heartbeats from the AP client on `127.0.0.1:49125`. If the heartbeat stops for three seconds, blocking is disabled.
- Restriction checkboxes start unchecked. Bindings/settings are stored in `%AppData%\RocketLeagueInputBridge\settings.json`.

This first prototype supports XInput-compatible controllers only. It does not yet read Rocket League's actual binding files, support generic DirectInput-only controllers, or change restrictions based on AP inventory/DeathLink items. Restrictions are selected manually in the prototype window.

## Requirements

- Windows 10/11 x64.
- .NET 10 SDK.
- HIDMaestro source checkout at `tools\HIDMaestro` (sibling to this project) and the build prerequisites described by that project. HIDMaestro's SDK project reference builds its native driver payloads; installing the runtime alone does not provide the SDK assembly needed by this prototype.
- HidHide installed and configured for controller suppression. Hide the physical controller from Rocket League while allowing `RocketLeagueInputBridge.exe` to read it. The bridge does not configure HidHide automatically.

The AP client source in `worlds\rocket_league\client\rocket_league_client.py` sends the local match heartbeat. Rebuild/install the APWorld from this checkout to use the integration. The companion opens the virtual controller and installs the HIDMaestro driver on first run, so Windows will ask for administrator approval.

## Build and run

From the repository root, with the HIDMaestro source placed in `tools\HIDMaestro` and its build prerequisites installed:

```powershell
dotnet run --project tools\RocketLeagueInputBridge\RocketLeagueInputBridge.csproj
```

The app requests administrator rights because Windows requires them to create a virtual controller. Select the controller slot, use **Controller** or **Keyboard** to capture each in-game binding, and check **Block** for actions to restrict. Air Roll can be captured more than once by pressing its capture button again.

For the first controller test, verify pass-through before enabling HidHide. To test suppression, configure HidHide so Rocket League sees only the virtual device and the bridge can still read the physical one. Turn HidHide's device hiding off before closing the bridge or if the bridge crashes; this prototype does not yet restore HidHide configuration automatically.

Blocking is gated by the AP client's active-match heartbeat. Keep both the AP client and this app running during a match. Keyboard suppression is limited to key presses while the foreground process is Rocket League.

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes
import json
import logging
import os
import random
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
    ASSIST_BASE_ID, ASSIST_LOCATION_NAMES, BASE_LOCATION_ID, DEMO_BASE_ID, DEMO_LOCATION_NAMES,
    GOAL_BASE_ID, GOAL_LOCATION_NAMES, MVP_BASE_ID, MVP_LOCATION_NAMES, SAVE_BASE_ID, SAVE_LOCATION_NAMES,
    SHOT_BASE_ID, SHOT_LOCATION_NAMES, VICTORY_LOCATION_ID,
)


GAME = "Rocket League"
DEATHLINK_DURATION = 10.0
DEMO_DEATHLINK_CAUSES = (
    "got their axels broken",
    "got wrekt",
    "went boom",
    "got demoed",
    "was yeeted from existence",
)
BOOST_ITEM_ID = ITEM_NAME_TO_ID["Boost"]
BALL_CAM_ITEM_ID = ITEM_NAME_TO_ID["Ball Cam"]
JUMP_FLIP_ITEM_ID = ITEM_NAME_TO_ID["Jump/Flip"]
AIR_ROLL_ITEM_ID = ITEM_NAME_TO_ID["Air Roll"]
BRAKE_ITEM_ID = ITEM_NAME_TO_ID["Brake"]
TRAP_ITEM_IDS = {
    ITEM_NAME_TO_ID["Scoreboard Trap"]: "Scoreboard Trap",
    ITEM_NAME_TO_ID["Ball Cam Trap"]: "Ball Cam Trap",
    ITEM_NAME_TO_ID["Jump Trap"]: "Jump Trap",
    ITEM_NAME_TO_ID["Boost Trap"]: "Boost Trap",
    ITEM_NAME_TO_ID["Spin Trap"]: "Spin Trap",
}
KEY_VIRTUAL_CODES = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "escape": 0x1B,
    "backspace": 0x08, "capslock": 0x14,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "minus": 0xBD, "equals": 0xBB, "comma": 0xBC, "period": 0xBE,
    "slash": 0xBF, "semicolon": 0xBA, "apostrophe": 0xDE,
    "bracketleft": 0xDB, "bracketright": 0xDD, "backslash": 0xDC, "grave": 0xC0,
    "leftshift": 0xA0, "rightshift": 0xA1,
    "leftctrl": 0xA2, "rightctrl": 0xA3,
    "leftalt": 0xA4, "rightalt": 0xA5,
    **{f"f{i}": 0x70 + i - 1 for i in range(1, 13)},
}
MOUSE_BUTTON_FLAGS = {
    "mouse_left": (0x0002, 0x0004, 0),
    "mouse_right": (0x0008, 0x0010, 0),
    "mouse_middle": (0x0020, 0x0040, 0),
    "mouse_x1": (0x0080, 0x0100, 1),
    "mouse_x2": (0x0080, 0x0100, 2),
}


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD), ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG), ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD), ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InjectedInputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyboardInput), ("mi", _MouseInput)]


class _InjectedInput(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("data", _InjectedInputUnion)]


XINPUT_BUTTON_MASKS = {
    "A": 0x1000, "B": 0x2000, "X": 0x4000, "Y": 0x8000,
    "Left Bumper": 0x0100, "Right Bumper": 0x0200,
    "Back": 0x0020, "Start": 0x0010,
    "Left Stick Click": 0x0040, "Right Stick Click": 0x0080,
    "D-Pad Up": 0x0001, "D-Pad Down": 0x0002,
    "D-Pad Left": 0x0004, "D-Pad Right": 0x0008,
}
XINPUT_ERROR_SUCCESS = 0
INPUT_MOUSE = 0


class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.wintypes.DWORD), ("Gamepad", _XInputGamepad)]


CONTROLLER_CONTROLS = [
    *XINPUT_BUTTON_MASKS,
    "Left Trigger", "Right Trigger",
    "Left Stick Up", "Left Stick Down", "Left Stick Left", "Left Stick Right",
    "Right Stick Up", "Right Stick Down", "Right Stick Left", "Right Stick Right",
]
DEFAULT_CONTROLLER_ACTIONS = {control: "" for control in CONTROLLER_CONTROLS}
DEFAULT_CONTROLLER_ACTIONS["A"] = "boost"
XINPUT_TRIGGER_THRESHOLD = 30
XINPUT_STICK_DEADZONE = 18000


def _active_xinput_controls(state: _XInputState) -> set[str]:
    gamepad = state.Gamepad
    active = {name for name, mask in XINPUT_BUTTON_MASKS.items() if gamepad.wButtons & mask}
    if gamepad.bLeftTrigger >= XINPUT_TRIGGER_THRESHOLD:
        active.add("Left Trigger")
    if gamepad.bRightTrigger >= XINPUT_TRIGGER_THRESHOLD:
        active.add("Right Trigger")
    for prefix, x, y in (
        ("Left Stick", gamepad.sThumbLX, gamepad.sThumbLY),
        ("Right Stick", gamepad.sThumbRX, gamepad.sThumbRY),
    ):
        if y >= XINPUT_STICK_DEADZONE:
            active.add(prefix + " Up")
        elif y <= -XINPUT_STICK_DEADZONE:
            active.add(prefix + " Down")
        if x <= -XINPUT_STICK_DEADZONE:
            active.add(prefix + " Left")
        elif x >= XINPUT_STICK_DEADZONE:
            active.add(prefix + " Right")
    return active


def _load_xinput_get_state():
    if os.name != "nt":
        return None
    for library in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            dll = ctypes.WinDLL(library)
            get_state = dll.XInputGetState
            get_state.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(_XInputState)]
            get_state.restype = ctypes.wintypes.DWORD
            return get_state
        except (AttributeError, OSError):
            continue
    return None


def set_injected_input(binding: str, pressed: bool) -> bool:
    """Send a configured keyboard or mouse input for the existing trap effects."""
    if os.name != "nt":
        return False
    event = _InjectedInput()
    if binding in MOUSE_BUTTON_FLAGS:
        down_flag, up_flag, mouse_data = MOUSE_BUTTON_FLAGS[binding]
        event.type = INPUT_MOUSE
        event.data.mi = _MouseInput(0, 0, mouse_data, down_flag if pressed else up_flag, 0, 0)
    else:
        key = KEY_VIRTUAL_CODES.get(binding)
        if key is None and len(binding) == 1 and binding.isascii() and binding.isalnum():
            key = ord(binding.upper())
        if key is None:
            return False
        event.type = 1  # INPUT_KEYBOARD
        event.data.ki = _KeyboardInput(key, 0, 0 if pressed else 0x0002, 0, 0)
    try:
        send_input = ctypes.WinDLL("user32", use_last_error=True).SendInput
        send_input.argtypes = [ctypes.wintypes.UINT, ctypes.POINTER(_InjectedInput), ctypes.c_int]
        send_input.restype = ctypes.wintypes.UINT
        return send_input(1, ctypes.byref(event), ctypes.sizeof(event)) == 1
    except (AttributeError, OSError):
        return False


_foreground_cache_value = False
_foreground_cache_until = 0.0


def rocket_league_is_foreground() -> bool:
    """Avoid forwarding controller clicks to another app or the desktop."""
    global _foreground_cache_value, _foreground_cache_until
    now = time.monotonic()
    if now < _foreground_cache_until:
        return _foreground_cache_value

    def cache(value: bool) -> bool:
        global _foreground_cache_value, _foreground_cache_until
        _foreground_cache_value = value
        _foreground_cache_until = time.monotonic() + 0.05
        return value

    if os.name != "nt":
        return cache(False)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return cache(False)
    process_id = ctypes.wintypes.DWORD()
    get_pid = user32.GetWindowThreadProcessId
    get_pid.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
    get_pid.restype = ctypes.wintypes.DWORD
    get_pid(hwnd, ctypes.byref(process_id))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
    open_process.restype = ctypes.wintypes.HANDLE
    handle = open_process(0x1000, False, process_id.value)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return cache(False)
    try:
        image = ctypes.create_unicode_buffer(32768)
        size = ctypes.wintypes.DWORD(len(image))
        query = kernel32.QueryFullProcessImageNameW
        query.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD,
                          ctypes.wintypes.LPWSTR, ctypes.POINTER(ctypes.wintypes.DWORD)]
        query.restype = ctypes.wintypes.BOOL
        return cache(bool(query(handle, 0, image, ctypes.byref(size))
                           and Path(image.value).name.casefold() == "rocketleague.exe"))
    finally:
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.wintypes.HANDLE]
        close_handle.restype = ctypes.wintypes.BOOL
        close_handle(handle)

stats_logger = logging.getLogger("RocketLeagueStats")
stats_logger.propagate = False

DEFAULT_CONTROL_BINDINGS = {
    "ballcam": "space",
    "jump": "mouse_right",
    "boost": "mouse_left",
    "scoreboard": "tab",
    "handbrake": "leftshift",
    "airroll": "leftshift",
    "forward": "w",
    "left": "a",
    "right": "d",
    "reverse": "s",
}
CONTROL_BINDING_NAMES = {
    "ballcam": "Ball Cam",
    "jump": "Jump",
    "boost": "Boost",
    "scoreboard": "Scoreboard",
    "handbrake": "Handbrake / Powerslide",
    "airroll": "Air Roll",
    "forward": "Forward",
    "left": "Steer Left",
    "right": "Steer Right",
    "reverse": "Reverse",
}
CONTROLLER_ACTION_TO_BINDING = {
    "boost": "boost",
    "jump": "jump",
    # The Brake ability means the ability to reverse, as in the game design.
    # Handbrake / powerslide remains reserved for the Spin Trap.
    "brake": "reverse",
    "ballcam": "ballcam",
    "scoreboard": "scoreboard",
    "airroll": "airroll",
    "forward": "forward",
    "backward": "reverse",
    "steer_left": "left",
    "steer_right": "right",
}
CONTROLLER_ACTION_LABELS = {
    "": "Unassigned",
    "boost": "Boost",
    "jump": "Jump",
    "brake": "Brake / Reverse",
    "ballcam": "Ball Cam",
    "scoreboard": "Scoreboard",
    "airroll": "Air Roll",
    "forward": "Forward",
    "backward": "Backward",
    "steer_left": "Steer Left",
    "steer_right": "Steer Right",
}
CONTROLLER_ACTION_BY_LABEL = {label: action for action, label in CONTROLLER_ACTION_LABELS.items()}
DEFAULT_CONTROLLER_KEYS = {
    control: DEFAULT_CONTROL_BINDINGS[CONTROLLER_ACTION_TO_BINDING[action]]
    if action in CONTROLLER_ACTION_TO_BINDING else ""
    for control, action in DEFAULT_CONTROLLER_ACTIONS.items()
}
VALID_BINDING_NAMES = {
    "space", "tab", "enter", "escape", "backspace", "capslock",
    "left", "up", "right", "down", "insert", "delete", "home", "end", "pageup", "pagedown",
    "minus", "equals", "comma", "period", "slash", "semicolon", "apostrophe",
    "bracketleft", "bracketright", "backslash", "grave",
    "leftshift", "rightshift", "leftctrl", "rightctrl", "leftalt", "rightalt",
    "mouse_left", "mouse_right", "mouse_middle", "mouse_x1", "mouse_x2",
    *(f"f{i}" for i in range(1, 13)),
    *(f"{letter}" for letter in "abcdefghijklmnopqrstuvwxyz0123456789"),
}
BINDING_ALIASES = {
    "spacebar": "space", "esc": "escape",
    "arrowleft": "left", "arrowup": "up", "arrowright": "right", "arrowdown": "down",
    "shift": "leftshift", "ctrl": "leftctrl", "control": "leftctrl", "alt": "leftalt",
    "lmb": "mouse_left", "rmb": "mouse_right", "mmb": "mouse_middle",
    "mouse1": "mouse_left", "mouse2": "mouse_right", "mouse3": "mouse_middle",
    "mouse4": "mouse_x1", "mouse5": "mouse_x2",
}


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

    def _set_control_binding(self, action: str, binding: str = "") -> bool:
        binding = binding.strip().casefold().replace(" ", "")
        binding = BINDING_ALIASES.get(binding, binding)
        label = CONTROL_BINDING_NAMES[action]
        current = self.ctx.control_bindings[action]
        if not binding:
            self.output(f"{label} key: {current}. Set with /{action} <key>; reset with /{action} reset.")
            return True
        if binding == "reset":
            binding = DEFAULT_CONTROL_BINDINGS[action]
        if binding not in VALID_BINDING_NAMES:
            self.output(
                f"Unsupported key '{binding}'. Use a letter, number, space, tab, enter, escape, "
                "shift, ctrl, alt, f1-f12, or mouse_left/mouse_right/mouse_middle/mouse_x1/mouse_x2."
            )
            return False
        self.ctx.control_bindings[action] = binding
        self.ctx.save_control_bindings()
        self.output(f"{label} key set to {binding}.")
        return True

    @mark_raw
    def _cmd_ballcam(self, binding: str = "") -> bool:
        """Show or set the Ball Cam key, for example /ballcam b."""
        return self._set_control_binding("ballcam", binding)

    @mark_raw
    def _cmd_jump(self, binding: str = "") -> bool:
        """Show or set the Jump key, for example /jump space."""
        return self._set_control_binding("jump", binding)

    @mark_raw
    def _cmd_boost(self, binding: str = "") -> bool:
        """Show or set the Boost key, for example /boost b."""
        return self._set_control_binding("boost", binding)

    @mark_raw
    def _cmd_scoreboard(self, binding: str = "") -> bool:
        """Show or set the Scoreboard key, for example /scoreboard tab."""
        return self._set_control_binding("scoreboard", binding)

    @mark_raw
    def _cmd_handbrake(self, binding: str = "") -> bool:
        """Show or set the Handbrake/Powerslide key, for example /handbrake leftshift."""
        return self._set_control_binding("handbrake", binding)

    @mark_raw
    def _cmd_airroll(self, binding: str = "") -> bool:
        """Show or set the Air Roll key, for example /airroll leftshift."""
        return self._set_control_binding("airroll", binding)

    @mark_raw
    def _cmd_forward(self, binding: str = "") -> bool:
        """Show or set the Forward key, for example /forward w."""
        return self._set_control_binding("forward", binding)

    @mark_raw
    def _cmd_left(self, binding: str = "") -> bool:
        """Show or set the Steer Left key, for example /left a."""
        return self._set_control_binding("left", binding)

    @mark_raw
    def _cmd_steerright(self, binding: str = "") -> bool:
        """Show or set the Steer Right key, for example /steerright d."""
        return self._set_control_binding("right", binding)

    @mark_raw
    def _cmd_reverse(self, binding: str = "") -> bool:
        """Show or set the Reverse key, for example /reverse s."""
        return self._set_control_binding("reverse", binding)

    @mark_raw
    def _cmd_backward(self, binding: str = "") -> bool:
        """Alias for /reverse."""
        return self._set_control_binding("reverse", binding)

    @mark_raw
    def _cmd_bindings(self, action: str = "") -> bool:
        """Show all Rocket League keyboard bindings used by trap effects."""
        if action:
            self.output("Usage: /bindings")
            return False
        self.output("Rocket League keyboard bindings:")
        for name, label in CONTROL_BINDING_NAMES.items():
            self.output(f"  {label}: {self.ctx.control_bindings[name]}")
        self.output("Controller 1 outputs and ability-lock selections are configured in the Bindings tab.")
        self.output("Set one with /<action> <key> (for example /ballcam b); use /<action> reset to restore its default.")
        return True


class RocketLeagueContext(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = RocketLeagueCommandProcessor

    def __init__(self, server_address: str | None, password: str | None, args: Namespace) -> None:
        super().__init__(server_address, password)
        self.tags.add("DeathLink")
        self.player_name = args.player_name
        self.player_id = args.player_id
        self.stats_host = args.stats_host
        self.stats_port = args.stats_port
        self.slot_data: dict[str, Any] = {}
        self.death_link_enabled = True
        self.earned_locations: set[int] = set()
        self.sent_locations: set[int] = set()
        self.player_team: int | None = None
        self.unmatched_player_warning_matches: set[str] = set()
        self.match_guid: str | None = None
        self.match_active = False
        self.pending_traps: list[tuple[int, str]] = []
        self.received_trap_item_indices: set[int] = set()
        self.trap_task: asyncio.Task[None] | None = None
        self.active_injected_bindings: set[str] = set()
        self.match_goals = 0
        self.match_demos = 0
        self.match_shots = 0
        self.match_saves = 0
        self.match_assists = 0
        self.match_players: list[dict[str, Any]] = []
        self.mvp_checks_earned = 0
        self.deathlink_lock_until = 0.0
        self.wins = 0
        self.final_start_wins: int | None = None
        self.victory_sent = False
        self.goal_status_sent = False
        self.last_ended_match: str | None = None
        self.stats_task: asyncio.Task[None] | None = None
        self.controller_task: asyncio.Task[None] | None = None
        self.controller_status = "Waiting for XInput controller 1"
        self.input_bridge_writer: asyncio.StreamWriter | None = None
        self.input_bridge_active = False
        self.input_bridge_last_send = 0.0
        self.input_bridge_retry_after = 0.0
        self.state_path = Path(Utils.user_path("rocket_league_ap_state.json"))
        self.control_bindings_path = Path(Utils.user_path("rocket_league_control_bindings.json"))
        self.control_bindings = dict(DEFAULT_CONTROL_BINDINGS)
        self.controller_action_bindings = dict(DEFAULT_CONTROLLER_ACTIONS)
        self.controller_key_bindings = dict(DEFAULT_CONTROLLER_KEYS)
        self.active_controller_output_bindings: set[str] = set()
        self.load_control_bindings()
        self.boost_unlock_enabled: bool | None = None
        self.boost_unlocked = False
        self.ball_cam_unlock_enabled: bool | None = None
        self.ball_cam_unlocked = False
        self.jump_flip_unlock_enabled: bool | None = None
        self.jump_flip_unlocked = False
        self.air_roll_unlock_enabled: bool | None = None
        self.air_roll_unlocked = False
        self.brake_unlock_enabled: bool | None = None
        self.brake_unlocked = False
        # ReceivedItems can arrive before RoomInfo identifies the seed. Buffer
        # ability receipts so restoring that seed's profile cannot lose them.
        self.ability_items_received_before_room: set[int] = set()
        self.ball_cam_initial_reset_done = False
        self.ball_cam_reset_match_guid: str | None = None
        self.ball_cam_reset_task: asyncio.Task[None] | None = None
        self.seed_name = ""
        self.progress_profiles: dict[str, dict[str, Any]] = {}
        self.load_progress()

    def load_control_bindings(self) -> None:
        try:
            saved = json.loads(self.control_bindings_path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                mapping_version = int(saved.get("mapping_version", 1))
                for action in DEFAULT_CONTROL_BINDINGS:
                    value = str(saved.get(action, "")).casefold().replace(" ", "")
                    value = BINDING_ALIASES.get(value, value)
                    if value in VALID_BINDING_NAMES:
                        self.control_bindings[action] = value
                saved_controller = saved.get("controller_mappings")
                if isinstance(saved_controller, dict):
                    uses_actions = any(
                        isinstance(entry, dict) and "action" in entry
                        for entry in saved_controller.values()
                    )
                    if uses_actions:
                        for control in CONTROLLER_CONTROLS:
                            entry = saved_controller.get(control, {})
                            if not isinstance(entry, dict):
                                continue
                            action = str(entry.get("action", "")).casefold()
                            if action in CONTROLLER_ACTION_LABELS:
                                self.controller_action_bindings[control] = action
                            key = str(entry.get("key", "")).casefold().replace(" ", "")
                            key = BINDING_ALIASES.get(key, key)
                            if action == "brake" and mapping_version < 2:
                                # Older client versions treated Brake as
                                # handbrake. Migrate those controller outputs
                                # to the configured backward/reverse key.
                                self.controller_key_bindings[control] = self.control_bindings["reverse"]
                            elif "key" in entry and not key:
                                self.controller_key_bindings[control] = ""
                            elif key in VALID_BINDING_NAMES:
                                self.controller_key_bindings[control] = key
                            elif "key" not in entry and action in CONTROLLER_ACTION_TO_BINDING:
                                self.controller_key_bindings[control] = self.control_bindings[
                                    CONTROLLER_ACTION_TO_BINDING[action]
                                ]
                    else:
                        # Migrate the previous controller-to-key table to its matching action.
                        for control in CONTROLLER_CONTROLS:
                            entry = saved_controller.get(control, {})
                            if not isinstance(entry, dict):
                                continue
                            key = str(entry.get("key", "")).casefold().replace(" ", "")
                            key = BINDING_ALIASES.get(key, key)
                            if not key:
                                continue
                            if key in VALID_BINDING_NAMES:
                                self.controller_key_bindings[control] = key
                            if bool(entry.get("boost_locked", False)):
                                self.controller_action_bindings[control] = "boost"
                                continue
                            for action, binding_name in CONTROLLER_ACTION_TO_BINDING.items():
                                if self.control_bindings[binding_name] == key:
                                    self.controller_action_bindings[control] = action
                                    break
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Could not read Rocket League control bindings: %s", exc)

    def save_control_bindings(self) -> None:
        temporary: Path | None = None
        try:
            self.control_bindings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.control_bindings_path.with_name(
                f"{self.control_bindings_path.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
            )
            saved = dict(self.control_bindings)
            saved["mapping_version"] = 2
            saved["controller_mappings"] = {
                control: {
                    "action": self.controller_action_bindings[control],
                    "key": self.controller_key_bindings[control],
                }
                for control in CONTROLLER_CONTROLS
            }
            temporary.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            temporary.replace(self.control_bindings_path)
        except OSError as exc:
            logger.warning("Could not save Rocket League control bindings: %s", exc)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    async def controller_input_loop(self) -> None:
        """Translate configured XInput controls to keyboard or mouse input."""
        get_state = _load_xinput_get_state()
        if get_state is None:
            self.controller_status = "XInput unavailable"
            logger.warning("Controller-to-keyboard mapping unavailable: could not load XInput")
            return
        try:
            while not self.exit_event.is_set():
                state = _XInputState()
                connected = get_state(0, ctypes.byref(state)) == XINPUT_ERROR_SUCCESS
                if connected:
                    self.controller_status = "Controller 1 connected"
                    held_controls = _active_xinput_controls(state)
                else:
                    self.controller_status = "Waiting for XInput controller 1"
                    held_controls = set()
                game_focused = rocket_league_is_foreground()
                boost_locked = self.match_active and self.boost_unlock_enabled is True and not self.boost_unlocked
                ball_cam_locked = (self.match_active and self.ball_cam_unlock_enabled is True
                                   and not self.ball_cam_unlocked)
                jump_flip_locked = (self.match_active and self.jump_flip_unlock_enabled is True
                                    and not self.jump_flip_unlocked)
                air_roll_locked = (self.match_active and self.air_roll_unlock_enabled is True
                                   and not self.air_roll_unlocked)
                brake_locked = (self.match_active and self.brake_unlock_enabled is True
                                and not self.brake_unlocked)
                deathlink_locked = (
                    self.match_active and time.monotonic() < self.deathlink_lock_until
                )
                blocked_driving_outputs = set()
                if deathlink_locked:
                    blocked_driving_outputs = {
                        self.controller_key_bindings[control]
                        for control in CONTROLLER_CONTROLS
                        if self.controller_action_bindings[control] in {"forward", "backward", "brake"}
                        and self.controller_key_bindings[control]
                    }
                wanted_outputs = set()
                if game_focused:
                    for control in held_controls:
                        action = self.controller_action_bindings[control]
                        if deathlink_locked and action in {"forward", "backward", "brake"}:
                            continue
                        if action == "boost" and boost_locked:
                            continue
                        if action == "ballcam" and ball_cam_locked:
                            continue
                        if action == "jump" and jump_flip_locked:
                            continue
                        if action == "airroll" and air_roll_locked:
                            continue
                        if action in {"brake", "backward"} and brake_locked:
                            continue
                        output = self.controller_key_bindings[control]
                        if output and output not in blocked_driving_outputs:
                            wanted_outputs.add(output)
                for binding in self.active_controller_output_bindings - wanted_outputs:
                    if set_injected_input(binding, False):
                        self.active_controller_output_bindings.discard(binding)
                for binding in wanted_outputs - self.active_controller_output_bindings:
                    if set_injected_input(binding, True):
                        self.active_controller_output_bindings.add(binding)
                await asyncio.sleep(0.008)
        finally:
            for binding in tuple(self.active_controller_output_bindings):
                set_injected_input(binding, False)
            self.active_controller_output_bindings.clear()

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
        legacy_mvp_count = max(
            (location_id - MVP_BASE_ID + 1 for location_id in self.earned_locations
             if MVP_BASE_ID <= location_id < MVP_BASE_ID + len(MVP_LOCATION_NAMES)),
            default=0,
        )
        self.mvp_checks_earned = max(0, int(state.get("mvp_checks_earned", legacy_mvp_count)), legacy_mvp_count)
        pending_traps = state.get("pending_traps")
        if pending_traps is None:
            pending_traps = [
                {"index": value, "name": "Scoreboard Trap"}
                for value in state.get("pending_scoreboard_traps", [])
            ]
        self.pending_traps = [
            (int(value["index"]), str(value["name"]))
            for value in pending_traps
            if isinstance(value, dict) and value.get("name") in TRAP_ITEM_IDS.values()
        ]
        self.received_trap_item_indices = {
            int(value) for value in state.get(
                "received_trap_item_indices", state.get("received_scoreboard_trap_indices", [])
            )
        }
        self.boost_unlocked = bool(state.get("boost_unlocked", False))
        self.ball_cam_unlocked = bool(state.get("ball_cam_unlocked", False))
        self.jump_flip_unlocked = bool(state.get("jump_flip_unlocked", False))
        self.air_roll_unlocked = bool(state.get("air_roll_unlocked", False))
        self.brake_unlocked = bool(state.get("brake_unlocked", False))
        self.ball_cam_initial_reset_done = bool(state.get("ball_cam_initial_reset_done", False))
        pending_count = len(self.pending_traps)
        if not self.ball_cam_unlocked:
            self.pending_traps = [
                (index, name) for index, name in self.pending_traps if name != "Ball Cam Trap"
            ]
        if len(self.pending_traps) != pending_count:
            self.save_progress()

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
            "mvp_checks_earned": self.mvp_checks_earned,
            "earned_locations": sorted(self.earned_locations),
            "pending_traps": [
                {"index": item_index, "name": trap_name}
                for item_index, trap_name in self.pending_traps
            ],
            "received_trap_item_indices": sorted(self.received_trap_item_indices),
            "boost_unlocked": self.boost_unlocked,
            "ball_cam_unlocked": self.ball_cam_unlocked,
            "jump_flip_unlocked": self.jump_flip_unlocked,
            "air_roll_unlocked": self.air_roll_unlocked,
            "brake_unlocked": self.brake_unlocked,
            "ball_cam_initial_reset_done": self.ball_cam_initial_reset_done,
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

    def apply_ability_item_receipts(self, item_ids: set[int]) -> None:
        unlocked = {
            BOOST_ITEM_ID: "boost_unlocked",
            BALL_CAM_ITEM_ID: "ball_cam_unlocked",
            JUMP_FLIP_ITEM_ID: "jump_flip_unlocked",
            AIR_ROLL_ITEM_ID: "air_roll_unlocked",
            BRAKE_ITEM_ID: "brake_unlocked",
        }
        changed = False
        for item_id in item_ids:
            attribute = unlocked.get(item_id)
            if attribute and not getattr(self, attribute):
                setattr(self, attribute, True)
                changed = True
        if changed:
            self.save_progress()

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.death_link_enabled = bool(self.slot_data.get("death_link_enabled", True))
            asyncio.create_task(self.update_death_link(self.death_link_enabled))
            self.boost_unlock_enabled = bool(self.slot_data.get("boost_unlock_enabled", False))
            self.ball_cam_unlock_enabled = bool(self.slot_data.get("ball_cam_unlock_enabled", False))
            self.jump_flip_unlock_enabled = bool(self.slot_data.get("jump_flip_unlock_enabled", False))
            self.air_roll_unlock_enabled = bool(self.slot_data.get("air_roll_unlock_enabled", False))
            self.brake_unlock_enabled = bool(self.slot_data.get("brake_unlock_enabled", False))
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
            if self.ability_items_received_before_room:
                self.apply_ability_item_receipts(self.ability_items_received_before_room)
                self.ability_items_received_before_room.clear()
            logger.info("Reached Archipelago room %s; authenticating the Rocket League slot",
                        args.get("seed_name", ""))
        elif cmd == "ReceivedItems":
            start_index = int(args.get("index", 0))
            for offset, network_item in enumerate(args.get("items", [])):
                item_id = (network_item.get("item") if isinstance(network_item, dict)
                           else getattr(network_item, "item", None))
                if item_id is None:
                    try:
                        item_id = network_item[0]
                    except (IndexError, KeyError, TypeError):
                        continue
                if not self.seed_name and item_id in {
                    BOOST_ITEM_ID, BALL_CAM_ITEM_ID, JUMP_FLIP_ITEM_ID,
                    AIR_ROLL_ITEM_ID, BRAKE_ITEM_ID,
                }:
                    self.ability_items_received_before_room.add(item_id)
                if item_id == BOOST_ITEM_ID and not self.boost_unlocked:
                    self.boost_unlocked = True
                    self.save_progress()
                if item_id == BALL_CAM_ITEM_ID and not self.ball_cam_unlocked:
                    self.ball_cam_unlocked = True
                    self.save_progress()
                if item_id == JUMP_FLIP_ITEM_ID and not self.jump_flip_unlocked:
                    self.jump_flip_unlocked = True
                    self.save_progress()
                if item_id == AIR_ROLL_ITEM_ID and not self.air_roll_unlocked:
                    self.air_roll_unlocked = True
                    self.save_progress()
                if item_id == BRAKE_ITEM_ID and not self.brake_unlocked:
                    self.brake_unlocked = True
                    self.save_progress()
                trap_name = TRAP_ITEM_IDS.get(item_id)
                if trap_name is not None:
                    item_index = start_index + offset
                    if item_index not in self.received_trap_item_indices:
                        self.received_trap_item_indices.add(item_index)
                        if trap_name != "Ball Cam Trap" or self.ball_cam_unlocked:
                            self.pending_traps.append((item_index, trap_name))
                        self.save_progress()
            if self.pending_traps and self.match_active:
                self.start_trap_queue()

    def set_match_active(self, active: bool) -> None:
        self.match_active = active
        if active:
            self.start_trap_queue()
            return
        reset_task = self.ball_cam_reset_task
        if reset_task is not None and not reset_task.done():
            reset_task.cancel()
        self.ball_cam_reset_task = None
        task = self.trap_task
        for binding in self.active_injected_bindings:
            set_injected_input(binding, False)
        self.active_injected_bindings.clear()
        if task is not None and not task.done():
            task.cancel()
            task.add_done_callback(self.trap_task_finished)
        else:
            self.trap_task = None

    async def force_ball_cam_off(self, match_guid: str) -> None:
        """Toggle Ball Cam once at the first live round, assuming RL starts it enabled."""
        bindings = self.trap_action_bindings("ballcam")
        if not bindings:
            return
        binding = bindings[0]
        pressed = False
        try:
            while (self.match_active and self.match_guid == match_guid
                   and not self.ball_cam_unlocked and not rocket_league_is_foreground()):
                await asyncio.sleep(0.1)
            if (not self.match_active or self.match_guid != match_guid
                    or self.ball_cam_unlocked or not rocket_league_is_foreground()):
                return
            if not set_injected_input(binding, True):
                logger.warning("Could not toggle Ball Cam off at match start")
                return
            pressed = True
            self.ball_cam_initial_reset_done = True
            self.save_progress()
            self.active_injected_bindings.add(binding)
            await asyncio.sleep(0.12)
        except asyncio.CancelledError:
            raise
        finally:
            if pressed:
                set_injected_input(binding, False)
                self.active_injected_bindings.discard(binding)
            if self.ball_cam_reset_task is asyncio.current_task():
                self.ball_cam_reset_task = None

    def trap_task_finished(self, task: asyncio.Task[None]) -> None:
        if self.trap_task is task:
            self.trap_task = None
        if self.match_active:
            self.start_trap_queue()

    def start_trap_queue(self) -> None:
        if (self.match_active and self.pending_traps
                and (self.trap_task is None or self.trap_task.done())):
            self.trap_task = asyncio.create_task(self.run_trap_queue())

    async def run_trap_queue(self) -> None:
        while self.match_active and self.pending_traps:
            if not self.ball_cam_unlocked:
                remaining = [
                    (index, name) for index, name in self.pending_traps if name != "Ball Cam Trap"
                ]
                if len(remaining) != len(self.pending_traps):
                    self.pending_traps = remaining
                    self.save_progress()
                    if not self.pending_traps:
                        return
            while self.match_active and not rocket_league_is_foreground():
                await asyncio.sleep(0.1)
            if not self.match_active:
                return
            item_index, trap_name = self.pending_traps.pop(0)
            self.save_progress()
            await self.apply_trap(trap_name)

    async def apply_trap(self, trap_name: str) -> None:
        if trap_name == "Scoreboard Trap":
            await self.hold_trap_keys(["scoreboard"], 5.0)
        elif trap_name == "Boost Trap":
            await self.hold_trap_keys(["boost"], 6.0)
        elif trap_name == "Spin Trap":
            await self.hold_trap_keys(["brake", "forward", "steer_left"], 5.0)
        elif trap_name == "Ball Cam Trap" and self.ball_cam_unlocked:
            await self.tap_trap_key("ballcam")
        elif trap_name == "Jump Trap":
            await self.tap_trap_key("jump")

    def trap_action_bindings(self, action: str) -> list[str]:
        """Resolve trap keys from action-labeled controller rows, then saved action binds."""
        mapped = list(dict.fromkeys(
            self.controller_key_bindings[control]
            for control in CONTROLLER_CONTROLS
            if (self.controller_action_bindings[control] == action
                and self.controller_key_bindings[control])
        ))
        if mapped:
            return mapped
        binding_name = CONTROLLER_ACTION_TO_BINDING.get(action, action)
        fallback = self.control_bindings.get(binding_name, "")
        return [fallback] if fallback else []

    async def hold_trap_keys(self, actions: list[str], duration: float) -> None:
        bindings = list(dict.fromkeys(
            binding
            for action in actions
            for binding in self.trap_action_bindings(action)
        ))
        if not bindings:
            return
        pressed: list[str] = []
        try:
            for binding in bindings:
                if not set_injected_input(binding, True):
                    return
                pressed.append(binding)
                self.active_injected_bindings.add(binding)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + duration
            while self.match_active and loop.time() < deadline and rocket_league_is_foreground():
                await asyncio.sleep(min(0.1, max(0.0, deadline - loop.time())))
        finally:
            for binding in pressed:
                set_injected_input(binding, False)
                self.active_injected_bindings.discard(binding)

    async def tap_trap_key(self, action: str) -> None:
        bindings = self.trap_action_bindings(action)
        if not bindings:
            return
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        while self.match_active and loop.time() < deadline:
            if not rocket_league_is_foreground():
                return
            pressed = []
            for binding in bindings:
                if not set_injected_input(binding, True):
                    for active_binding in pressed:
                        set_injected_input(active_binding, False)
                        self.active_injected_bindings.discard(active_binding)
                    return
                pressed.append(binding)
                self.active_injected_bindings.add(binding)
            try:
                await asyncio.sleep(0.12)
            finally:
                for binding in pressed:
                    set_injected_input(binding, False)
                    self.active_injected_bindings.discard(binding)
            remaining = deadline - loop.time()
            if remaining > 0:
                await asyncio.sleep(min(random.uniform(0.45, 1.15), remaining))

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect(game=self.game)

    async def sync_after_connect(self) -> None:
        await self.send_pending_checks()
        await self.maybe_start_final_challenge()

    async def publish_input_bridge_state(self, match_active: bool, force: bool = False) -> None:
        """Send a short-lived match-state heartbeat to the optional local input bridge."""
        now = time.monotonic()
        if not force and match_active == self.input_bridge_active:
            if not match_active or now - self.input_bridge_last_send < 1.0:
                return
        if self.input_bridge_writer is None or self.input_bridge_writer.is_closing():
            if now < self.input_bridge_retry_after:
                return
            try:
                _, self.input_bridge_writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", 49125), timeout=0.2
                )
            except (OSError, asyncio.TimeoutError):
                self.input_bridge_writer = None
                self.input_bridge_retry_after = now + 3.0
                return
        try:
            self.input_bridge_writer.write(
                (json.dumps({"match_active": bool(match_active)}) + "\n").encode("utf-8")
            )
            await asyncio.wait_for(self.input_bridge_writer.drain(), timeout=0.2)
            self.input_bridge_active = match_active
            self.input_bridge_last_send = now
            self.input_bridge_retry_after = 0.0
        except (OSError, asyncio.TimeoutError):
            self.input_bridge_writer.close()
            self.input_bridge_writer = None
            self.input_bridge_active = False
            self.input_bridge_retry_after = now + 1.0

    async def close_input_bridge(self) -> None:
        await self.publish_input_bridge_state(False, force=True)
        if self.input_bridge_writer is not None:
            self.input_bridge_writer.close()
            try:
                await self.input_bridge_writer.wait_closed()
            except OSError:
                pass
            self.input_bridge_writer = None

    def selected_player(self, player: dict[str, Any]) -> bool:
        if self.player_id:
            return player.get("PrimaryId") == self.player_id
        return player.get("Name", "").casefold() == self.player_name.casefold()

    def on_deathlink(self, data: dict[str, Any]) -> None:
        if not self.death_link_enabled:
            return
        previous_deathlink_time = self.last_death_link
        super().on_deathlink(data)
        if data.get("time", 0) <= previous_deathlink_time:
            return
        self.deathlink_lock_until = max(
            self.deathlink_lock_until,
            time.monotonic() + DEATHLINK_DURATION,
        )
        logger.info("DeathLink received: forward and reverse are blocked for 10 seconds")

    async def send_death(self, death_text: str = "") -> None:
        if not self.death_link_enabled:
            return
        await super().send_death(death_text)

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

        if event in {"MatchCreated", "MatchInitialized", "UpdateState"} and data.get("MatchGuid"):
            self.set_match_active(True)
            await self.publish_input_bridge_state(True, force=event != "UpdateState")
        elif event in {"MatchEnded", "MatchDestroyed"}:
            self.set_match_active(False)
            await self.publish_input_bridge_state(False, force=True)

        guid = data.get("MatchGuid")
        if guid and guid != self.match_guid:
            self.match_guid = guid
            self.ball_cam_reset_match_guid = None
            self.match_goals = self.match_demos = self.match_shots = self.match_saves = self.match_assists = 0
            self.match_players = []
            self.player_team = None
            stats_logger.info("Match detected: %s", guid)

        if (event == "RoundStarted" and self.match_active and self.ball_cam_unlock_enabled is True
                and not self.ball_cam_unlocked and not self.ball_cam_initial_reset_done and guid
                and self.ball_cam_reset_match_guid != guid):
            self.ball_cam_reset_match_guid = guid
            self.ball_cam_reset_task = asyncio.create_task(self.force_ball_cam_off(guid))

        if event == "UpdateState":
            players = data.get("Players", [])
            if isinstance(players, list) and players:
                self.match_players = [entry for entry in players if isinstance(entry, dict)]
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
                goal_limit = int(self.slot_data.get("goals_per_match", 7))
                demo_limit = int(self.slot_data.get("demos_per_match", 3))
                save_limit = int(self.slot_data.get("saves_per_match", 5))
                assist_limit = int(self.slot_data.get("assists_per_match", 5))
                shot_limit = int(self.slot_data.get("shots_on_goal_per_match", 5))
                for count in range(self.match_goals + 1, min(goals, goal_limit) + 1):
                    await self.earn(GOAL_BASE_ID + count, GOAL_LOCATION_NAMES[count - 1])
                for count in range(self.match_demos + 1, min(demos, demo_limit) + 1):
                    await self.earn(DEMO_BASE_ID + count, DEMO_LOCATION_NAMES[count - 1])
                for count in range(self.match_saves + 1, min(saves, save_limit) + 1):
                    await self.earn(SAVE_BASE_ID + count, SAVE_LOCATION_NAMES[count - 1])
                if self.slot_data.get("non1v1_mode", False):
                    for count in range(self.match_assists + 1, min(assists, assist_limit) + 1):
                        await self.earn(ASSIST_BASE_ID + count, ASSIST_LOCATION_NAMES[count - 1])
                self.match_goals = max(self.match_goals, goals)
                self.match_demos = max(self.match_demos, demos)
                self.match_saves = max(self.match_saves, saves)
                self.match_assists = max(self.match_assists, assists)

        elif event == "StatfeedEvent":
            target = data.get("MainTarget", {})
            is_player = target.get("Name", "").casefold() == self.player_name.casefold()
            secondary_target = data.get("SecondaryTarget")
            if is_player and data.get("EventName") == "Shot" and data.get("Type") == "Shot on Goal":
                self.match_shots += 1
                shot_limit = int(self.slot_data.get("shots_on_goal_per_match", 5))
                if self.match_shots <= shot_limit:
                    await self.earn(SHOT_BASE_ID + self.match_shots, SHOT_LOCATION_NAMES[self.match_shots - 1])
            elif (self.match_active
                  and str(data.get("EventName", "")).casefold() in {"demolish", "demolition"}
                  and isinstance(secondary_target, dict)
                  and str(secondary_target.get("Name", "")).casefold()
                  == self.player_name.casefold()):
                player_name = self.player_name or self.auth or "Player"
                cause = f"{player_name} {random.choice(DEMO_DEATHLINK_CAUSES)}"
                await self.send_death(cause)

        elif event == "MatchEnded":
            if guid and guid == self.last_ended_match:
                return
            winner = data.get("WinnerTeamNum")
            if self.slot_data.get("non1v1_mode", False) and winner is not None:
                candidates = [
                    entry for entry in self.match_players
                    if entry.get("TeamNum") == winner
                ]
                player = next((entry for entry in candidates if self.selected_player(entry)), None)
                if player is not None and len(candidates) > 1:
                    def mvp_rank(entry: dict[str, Any]) -> tuple[int, int, int, int, int]:
                        return tuple(int(entry.get(key, 0) or 0)
                                     for key in ("Score", "Goals", "Assists", "Saves", "Shots"))

                    player_rank = mvp_rank(player)
                    top_rank = max((mvp_rank(entry) for entry in candidates), default=None)
                    # If every listed tie-break stat is equal, the API provides
                    # no explicit MVP marker, so avoid awarding an ambiguous check.
                    if (top_rank == player_rank and sum(
                            1 for entry in candidates if mvp_rank(entry) == player_rank
                    ) == 1 and self.mvp_checks_earned < int(self.slot_data.get("mvp_checks", 1))):
                        self.mvp_checks_earned += 1
                        self.save_progress()
                        await self.earn(
                            MVP_BASE_ID + self.mvp_checks_earned - 1,
                            MVP_LOCATION_NAMES[self.mvp_checks_earned - 1],
                        )
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
                self.set_match_active(False)
                await self.publish_input_bridge_state(False, force=True)
                stats_logger.warning("Rocket League Stats API unavailable: %s; retrying in 5 seconds", exc)
                await asyncio.sleep(5)

    def make_gui(self):
        from kvui import GameManager, MDBoxLayout, MDLabel, dp
        from kivy.uix.button import Button
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.spinner import Spinner
        from kivy.uix.textinput import TextInput

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
                manager.match_status_label = MDLabel(
                    text="No active match | Game not focused",
                    size_hint_y=None, height=dp(36),
                )
                manager.rocket_league_panel.add_widget(manager.match_status_label)
                manager.add_client_tab("Rocket League", manager.rocket_league_panel)
                manager.bindings_panel = MDBoxLayout(
                    orientation="vertical", spacing=dp(12), padding=dp(24),
                )
                manager.controller_status_label = MDLabel(
                    text=manager.ctx.controller_status, size_hint_y=None, height=dp(40),
                )
                manager.bindings_panel.add_widget(manager.controller_status_label)
                manager.controller_action_spinners = {}
                manager.controller_key_fields = {}
                manager.controller_key_draft = dict(manager.ctx.controller_key_bindings)
                manager.action_key_draft = dict(manager.ctx.control_bindings)
                manager.syncing_action_keys = False
                mapping_grid = GridLayout(
                    cols=3, spacing=(dp(8), dp(4)), size_hint_y=None,
                    row_default_height=dp(38), row_force_default=True,
                )
                mapping_grid.bind(minimum_height=mapping_grid.setter("height"))
                for heading in ("Controller input", "Rocket League action", "Keyboard mapping"):
                    mapping_grid.add_widget(MDLabel(text=heading, size_hint_y=None, height=dp(36)))
                for control in CONTROLLER_CONTROLS:
                    mapping_grid.add_widget(MDLabel(text=control, size_hint_y=None, height=dp(38)))
                    selected_action = manager.ctx.controller_action_bindings[control]
                    action_picker = Spinner(
                        text=CONTROLLER_ACTION_LABELS[selected_action],
                        values=tuple(CONTROLLER_ACTION_LABELS.values()),
                        size_hint_y=None, height=dp(38),
                    )
                    manager.controller_action_spinners[control] = action_picker
                    mapping_grid.add_widget(action_picker)
                    key_field = TextInput(
                        text=manager.controller_key_draft[control],
                        multiline=False, size_hint_y=None, height=dp(38),
                        hint_text="keyboard or mouse key",
                    )
                    manager.controller_key_fields[control] = key_field
                    mapping_grid.add_widget(key_field)
                    action_picker.bind(
                        text=lambda _spinner, _value, control=control:
                            manager.controller_action_changed(control),
                    )
                    key_field.bind(
                        text=lambda _field, value, control=control:
                            manager.controller_key_changed(control, value),
                    )
                mapping_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
                mapping_scroll.add_widget(mapping_grid)
                manager.bindings_panel.add_widget(mapping_scroll)
                manager.spin_trap_key_field = TextInput(
                    text=manager.ctx.control_bindings["handbrake"], multiline=False,
                    size_hint_y=None, height=dp(38),
                )
                manager.bindings_panel.add_widget(MDLabel(
                    text="Spin Trap handbrake / powerslide key:", size_hint_y=None, height=dp(28),
                ))
                manager.bindings_panel.add_widget(manager.spin_trap_key_field)
                manager.spin_trap_key_field.bind(text=manager.spin_trap_key_changed)
                manager.mapping_save_status = MDLabel(text="", size_hint_y=None, height=dp(30))
                manager.bindings_panel.add_widget(manager.mapping_save_status)
                manager.mapping_save_button = Button(
                    text="Save Controller Mappings", size_hint_y=None, height=dp(44),
                )
                manager.mapping_save_button.bind(on_release=manager.save_controller_mappings)
                manager.bindings_panel.add_widget(manager.mapping_save_button)
                manager.add_client_tab("Bindings", manager.bindings_panel)
                manager.update_rocket_league_stats()
                return root

            def controller_action_changed(manager, control):
                label = manager.controller_action_spinners[control].text
                action = CONTROLLER_ACTION_BY_LABEL[label]
                binding_name = CONTROLLER_ACTION_TO_BINDING.get(action)
                field = manager.controller_key_fields[control]
                if binding_name:
                    manager.syncing_action_keys = True
                    field.text = manager.action_key_draft.get(binding_name, "")
                    manager.controller_key_draft[control] = field.text
                    if binding_name == "handbrake":
                        manager.spin_trap_key_field.text = field.text
                    manager.syncing_action_keys = False

            def controller_key_changed(manager, control, value):
                if manager.syncing_action_keys:
                    return
                manager.controller_key_draft[control] = value

            def spin_trap_key_changed(manager, _field, value):
                if manager.syncing_action_keys:
                    return
                manager.action_key_draft["handbrake"] = value

            def save_controller_mappings(manager, *_args):
                controller_keys = {}
                for control, raw_value in manager.controller_key_draft.items():
                    value = raw_value.strip().casefold().replace(" ", "")
                    value = BINDING_ALIASES.get(value, value)
                    if value and value not in VALID_BINDING_NAMES:
                        manager.mapping_save_status.text = (
                            f"Unsupported keyboard mapping for controller input {control}: {raw_value}"
                        )
                        return
                    controller_keys[control] = value
                action_keys = {}
                for binding_name, raw_value in manager.action_key_draft.items():
                    value = raw_value.strip().casefold().replace(" ", "")
                    value = BINDING_ALIASES.get(value, value)
                    if value and value not in VALID_BINDING_NAMES:
                        manager.mapping_save_status.text = (
                            f"Unsupported keyboard mapping for {CONTROL_BINDING_NAMES[binding_name]}: {raw_value}"
                        )
                        return
                    action_keys[binding_name] = value
                spin_key = manager.spin_trap_key_field.text.strip().casefold().replace(" ", "")
                spin_key = BINDING_ALIASES.get(spin_key, spin_key)
                if spin_key and spin_key not in VALID_BINDING_NAMES:
                    manager.mapping_save_status.text = "Unsupported Spin Trap handbrake / powerslide key."
                    return
                manager.ctx.control_bindings.update(action_keys)
                manager.ctx.control_bindings["handbrake"] = spin_key
                manager.ctx.controller_key_bindings = controller_keys
                manager.ctx.controller_action_bindings = {
                    control: CONTROLLER_ACTION_BY_LABEL[manager.controller_action_spinners[control].text]
                    for control in CONTROLLER_CONTROLS
                }
                manager.ctx.save_control_bindings()
                manager.mapping_save_status.text = "Controller actions and keyboard mappings saved."

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
                    manager.controller_status_label.text = manager.ctx.controller_status
                    ctx = manager.ctx
                    match = "Active match" if ctx.match_active else "No active match"
                    focus = "Game focused" if rocket_league_is_foreground() else "Game not focused"
                    manager.match_status_label.text = f"{match} | {focus}"

        return RocketLeagueManager


async def main(args: Namespace) -> None:
    ctx = RocketLeagueContext(args.connect, args.password, args)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="Archipelago server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    ctx.stats_task = asyncio.create_task(ctx.stats_loop(), name="Rocket League Stats API loop")
    ctx.controller_task = asyncio.create_task(
        ctx.controller_input_loop(), name="Rocket League controller input loop"
    )
    try:
        await ctx.exit_event.wait()
    finally:
        ctx.set_match_active(False)
        if ctx.stats_task:
            ctx.stats_task.cancel()
            await asyncio.gather(ctx.stats_task, return_exceptions=True)
        if ctx.controller_task:
            ctx.controller_task.cancel()
            await asyncio.gather(ctx.controller_task, return_exceptions=True)
        await ctx.close_input_bridge()
        await ctx.shutdown()

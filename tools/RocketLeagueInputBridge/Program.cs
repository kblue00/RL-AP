using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text.Json;
using HIDMaestro;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new BridgeForm());
    }
}

internal sealed class BridgeForm : Form
{
    private static readonly string[] Actions = ["Jump", "Boost", "Ball Cam", "Air Roll", "Reverse", "Forward"];
    private readonly Dictionary<string, List<string>> _bindings = Actions.ToDictionary(a => a, _ => new List<string>());
    private readonly Dictionary<string, CheckBox> _restrict = new();
    private readonly Dictionary<string, TextBox> _bindText = new();
    private readonly ComboBox _device = new();
    private readonly Label _deviceStatus = new() { AutoSize = true };
    private readonly Label _matchStatus = new() { AutoSize = true };
    private readonly Label _restrictionStatus = new() { AutoSize = true };
    private readonly System.Windows.Forms.Timer _poll = new() { Interval = 8 };
    private readonly CancellationTokenSource _stop = new();
    private readonly HashSet<string> _previousPadControls = new(StringComparer.OrdinalIgnoreCase);
    private readonly string _settingsPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "RocketLeagueInputBridge", "settings.json");
    private HashSet<string> _configuredRestrictions = new(StringComparer.OrdinalIgnoreCase);
    private HMContext? _hmContext;
    private HMController? _virtualPad;
    private string? _captureAction;
    private string _captureSource = "";
    private bool _matchActive;
    private DateTime _lastHeartbeatUtc = DateTime.MinValue;
    private IntPtr _keyboardHook;
    private NativeMethods.LowLevelKeyboardProc? _keyboardProc;
    private TcpListener? _bridgeListener;

    public BridgeForm()
    {
        Text = "Rocket League Input Bridge (Prototype)";
        Width = 940;
        Height = 570;
        MinimumSize = new System.Drawing.Size(800, 480);
        StartPosition = FormStartPosition.CenterScreen;
        LoadSettings();
        BuildUi();
        Shown += (_, _) => StartBridge();
        FormClosing += (_, _) => StopBridge();
        _poll.Tick += PollInput;
        _poll.Start();
        _keyboardProc = KeyboardHook;
        _keyboardHook = NativeMethods.SetWindowsHookEx(NativeMethods.WH_KEYBOARD_LL,
            _keyboardProc, NativeMethods.GetModuleHandle(null), 0);
        if (_keyboardHook == IntPtr.Zero)
            _deviceStatus.Text = "Keyboard filter could not start; controller setup may still work.";
    }

    private void BuildUi()
    {
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(14) };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        Controls.Add(root);

        var intro = new Label
        {
            AutoSize = true,
            Text = "Choose the controls Rocket League uses for each action. Checked actions are blocked only while the AP client reports an active match. " +
                   "Controller blocking requires HidHide to hide the physical controller from Rocket League while allowing this bridge to read it.",
            MaximumSize = new System.Drawing.Size(870, 0),
            Padding = new Padding(0, 0, 0, 10),
        };
        root.Controls.Add(intro, 0, 0);

        var header = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
        header.Controls.Add(new Label { Text = "Physical XInput controller:", AutoSize = true, Padding = new Padding(0, 7, 0, 0) });
        _device.DropDownStyle = ComboBoxStyle.DropDownList;
        for (int i = 0; i < 4; i++) _device.Items.Add($"Controller {i + 1}");
        _device.SelectedIndex = 0;
        _device.Width = 145;
        _device.SelectedIndexChanged += (_, _) => _previousPadControls.Clear();
        header.Controls.Add(_device);
        header.Controls.Add(_deviceStatus);
        root.Controls.Add(header, 0, 1);

        var table = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 5, RowCount = Actions.Length + 1, AutoScroll = true };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 130));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 112));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 112));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 105));
        table.Controls.Add(new Label { Text = "Action", AutoSize = true, Font = new System.Drawing.Font(Font, System.Drawing.FontStyle.Bold) }, 0, 0);
        table.Controls.Add(new Label { Text = "Mapped controls", AutoSize = true, Font = new System.Drawing.Font(Font, System.Drawing.FontStyle.Bold) }, 1, 0);
        table.Controls.Add(new Label { Text = "Capture", AutoSize = true, Font = new System.Drawing.Font(Font, System.Drawing.FontStyle.Bold) }, 2, 0);
        table.Controls.Add(new Label { Text = "Capture", AutoSize = true, Font = new System.Drawing.Font(Font, System.Drawing.FontStyle.Bold) }, 3, 0);
        table.Controls.Add(new Label { Text = "Restrict", AutoSize = true, Font = new System.Drawing.Font(Font, System.Drawing.FontStyle.Bold) }, 4, 0);
        for (int i = 0; i < Actions.Length; i++)
        {
            var action = Actions[i];
            int row = i + 1;
            table.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
            table.Controls.Add(new Label { Text = action, AutoSize = true, Anchor = AnchorStyles.Left, Padding = new Padding(0, 8, 0, 0) }, 0, row);
            var mapping = new TextBox { ReadOnly = true, Dock = DockStyle.Fill, Text = string.Join(", ", _bindings[action]) };
            _bindText[action] = mapping;
            table.Controls.Add(mapping, 1, row);
            var pad = new Button { Text = "Controller", Dock = DockStyle.Fill, Tag = action };
            pad.Click += (_, _) => BeginCapture(action, "Pad");
            table.Controls.Add(pad, 2, row);
            var key = new Button { Text = "Keyboard", Dock = DockStyle.Fill, Tag = action };
            key.Click += (_, _) => BeginCapture(action, "Key");
            table.Controls.Add(key, 3, row);
            var check = new CheckBox { Text = "Block", AutoSize = true, Anchor = AnchorStyles.Left, Checked = _configuredRestrictions.Contains(action), Tag = action };
            check.CheckedChanged += (_, _) => SaveSettings();
            _restrict[action] = check;
            table.Controls.Add(check, 4, row);
        }
        root.Controls.Add(table, 0, 2);

        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
        footer.Controls.Add(_matchStatus);
        footer.Controls.Add(new Label { Text = "  |  ", AutoSize = true });
        footer.Controls.Add(_restrictionStatus);
        footer.Controls.Add(new Label { Text = "  |  Local AP bridge: 127.0.0.1:49125", AutoSize = true });
        root.Controls.Add(footer, 0, 3);
        UpdateStatus();
    }

    private void BeginCapture(string action, string source)
    {
        _captureAction = action;
        _captureSource = source;
        _deviceStatus.Text = source == "Pad"
            ? $"Press the {action} controller control now."
            : $"Press the {action} keyboard key now.";
        if (source == "Pad") _previousPadControls = CurrentPadControls();
    }

    private void PollInput(object? sender, EventArgs e)
    {
        if (_lastHeartbeatUtc != DateTime.MinValue && DateTime.UtcNow - _lastHeartbeatUtc > TimeSpan.FromSeconds(3))
            _matchActive = false;

        int index = Math.Max(0, _device.SelectedIndex);
        if (XInput.GetState((uint)index, out var state) != 0)
        {
            _deviceStatus.Text = "No XInput controller in the selected slot.";
            _previousPadControls.Clear();
            SubmitNeutralIfUnavailable();
            UpdateStatus();
            return;
        }

        _deviceStatus.Text = $"Controller {index + 1} connected. Hold each mapped control to confirm its bind.";
        var held = GetControls(state);
        if (_captureAction is not null && _captureSource == "Pad")
        {
            var newlyPressed = held.Except(_previousPadControls, StringComparer.OrdinalIgnoreCase).FirstOrDefault();
            if (newlyPressed is not null) AddBinding(_captureAction, "Pad:" + newlyPressed);
        }
        _previousPadControls.Clear();
        _previousPadControls.UnionWith(held);

        if (_virtualPad is not null)
        {
            var blocked = ActiveBlockedControls();
            var buttons = ConvertButtons(state.Gamepad.Buttons, blocked);
            var axes = HMGamepadStateHelpers.StandardAxes(_virtualPad.Profile,
                leftStickX: Axis(state.Gamepad.LeftThumbX),
                leftStickY: Axis(state.Gamepad.LeftThumbY),
                rightStickX: Axis(state.Gamepad.RightThumbX),
                rightStickY: Axis(state.Gamepad.RightThumbY),
                leftTrigger: Trigger(state.Gamepad.LeftTrigger, "LeftTrigger", blocked),
                rightTrigger: Trigger(state.Gamepad.RightTrigger, "RightTrigger", blocked));
            ApplyStickBlocks(state.Gamepad, axes, blocked);
            var output = new HMGamepadState { Axes = axes, Buttons = buttons, Hat = ConvertHat(state.Gamepad.Buttons, blocked) };
            _virtualPad.SubmitState(in output);
        }
        UpdateStatus();
    }

    private void SubmitNeutralIfUnavailable()
    {
        if (_virtualPad is null) return;
        var axes = HMGamepadStateHelpers.StandardAxes(_virtualPad.Profile);
        var neutral = new HMGamepadState { Axes = axes, Buttons = HMButton.None, Hat = HMHat.None };
        _virtualPad.SubmitState(in neutral);
    }

    private HMButton ConvertButtons(ushort raw, HashSet<string> blocked)
    {
        HMButton result = HMButton.None;
        Add(0x1000, "A", HMButton.A); Add(0x2000, "B", HMButton.B);
        Add(0x4000, "X", HMButton.X); Add(0x8000, "Y", HMButton.Y);
        Add(0x0100, "LeftBumper", HMButton.LeftBumper); Add(0x0200, "RightBumper", HMButton.RightBumper);
        Add(0x0020, "Back", HMButton.Back); Add(0x0010, "Start", HMButton.Start);
        Add(0x0040, "LeftStick", HMButton.LeftStick); Add(0x0080, "RightStick", HMButton.RightStick);
        return result;
        void Add(ushort mask, string name, HMButton mapped)
        {
            if ((raw & mask) != 0 && !blocked.Contains("Pad:" + name)) result |= mapped;
        }
    }

    private static HMHat ConvertHat(ushort raw, HashSet<string> blocked)
    {
        bool up = (raw & 0x0001) != 0, down = (raw & 0x0002) != 0;
        bool left = (raw & 0x0004) != 0, right = (raw & 0x0008) != 0;
        if (up && !blocked.Contains("Pad:DPadUp")) return left && !blocked.Contains("Pad:DPadLeft") ? HMHat.NorthWest : right && !blocked.Contains("Pad:DPadRight") ? HMHat.NorthEast : HMHat.North;
        if (down && !blocked.Contains("Pad:DPadDown")) return left && !blocked.Contains("Pad:DPadLeft") ? HMHat.SouthWest : right && !blocked.Contains("Pad:DPadRight") ? HMHat.SouthEast : HMHat.South;
        if (left && !blocked.Contains("Pad:DPadLeft")) return HMHat.West;
        if (right && !blocked.Contains("Pad:DPadRight")) return HMHat.East;
        return HMHat.None;
    }

    private static void ApplyStickBlocks(XInput.Gamepad pad, Dictionary<HMAxis, float> axes, HashSet<string> blocked)
    {
        Apply("LeftStick", pad.LeftThumbX, pad.LeftThumbY, HMAxis.X, HMAxis.Y);
        Apply("RightStick", pad.RightThumbX, pad.RightThumbY, HMAxis.Rx, HMAxis.Ry);
        void Apply(string prefix, short x, short y, HMAxis xAxis, HMAxis yAxis)
        {
            if (blocked.Contains($"Pad:{prefix}Left") && x < 0) axes[xAxis] = 0.5f;
            if (blocked.Contains($"Pad:{prefix}Right") && x > 0) axes[xAxis] = 0.5f;
            if (blocked.Contains($"Pad:{prefix}Up") && y > 0) axes[yAxis] = 0.5f;
            if (blocked.Contains($"Pad:{prefix}Down") && y < 0) axes[yAxis] = 0.5f;
        }
    }

    private static float Trigger(byte value, string name, HashSet<string> blocked) =>
        blocked.Contains("Pad:" + name) ? 0f : value / 255f;

    private static float Axis(short value)
    {
        float normalized = Math.Clamp(value / 65535f + 0.5f, 0f, 1f);
        return normalized;
    }

    private HashSet<string> CurrentPadControls()
    {
        int index = Math.Max(0, _device.SelectedIndex);
        return XInput.GetState((uint)index, out var state) == 0 ? GetControls(state) : new HashSet<string>();
    }

    private static HashSet<string> GetControls(XInput.State state)
    {
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        ushort b = state.Gamepad.Buttons;
        Add(0x1000, "A"); Add(0x2000, "B"); Add(0x4000, "X"); Add(0x8000, "Y");
        Add(0x0100, "LeftBumper"); Add(0x0200, "RightBumper"); Add(0x0020, "Back"); Add(0x0010, "Start");
        Add(0x0040, "LeftStick"); Add(0x0080, "RightStick");
        Add(0x0001, "DPadUp"); Add(0x0002, "DPadDown"); Add(0x0004, "DPadLeft"); Add(0x0008, "DPadRight");
        if (state.Gamepad.LeftTrigger > 60) result.Add("LeftTrigger");
        if (state.Gamepad.RightTrigger > 60) result.Add("RightTrigger");
        AddAxis("LeftStick", state.Gamepad.LeftThumbX, state.Gamepad.LeftThumbY);
        AddAxis("RightStick", state.Gamepad.RightThumbX, state.Gamepad.RightThumbY);
        return result;
        void Add(ushort mask, string name) { if ((b & mask) != 0) result.Add(name); }
        void AddAxis(string prefix, short x, short y)
        {
            if (x < -18000) result.Add(prefix + "Left");
            if (x > 18000) result.Add(prefix + "Right");
            if (y > 18000) result.Add(prefix + "Up");
            if (y < -18000) result.Add(prefix + "Down");
        }
    }

    private HashSet<string> ActiveBlockedControls()
    {
        var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (!_matchActive) return result;
        foreach (var action in Actions)
            if (_restrict[action].Checked)
                result.UnionWith(_bindings[action]);
        return result;
    }

    private void AddBinding(string action, string binding)
    {
        if (!_bindings[action].Contains(binding, StringComparer.OrdinalIgnoreCase))
            _bindings[action].Add(binding);
        _captureAction = null;
        _bindText[action].Text = string.Join(", ", _bindings[action]);
        _deviceStatus.Text = $"Mapped {action} to {binding}.";
        SaveSettings();
    }

    private void LoadSettings()
    {
        try
        {
            if (!File.Exists(_settingsPath)) return;
            using var doc = JsonDocument.Parse(File.ReadAllText(_settingsPath));
            foreach (var action in Actions)
            {
                if (doc.RootElement.TryGetProperty("bindings", out var bindings) && bindings.TryGetProperty(action, out var values))
                    _bindings[action] = values.EnumerateArray().Select(v => v.GetString() ?? "").Where(v => v.Length > 0).ToList();
            }
            if (doc.RootElement.TryGetProperty("restrict", out var restricted) && restricted.ValueKind == JsonValueKind.Array)
                _configuredRestrictions = restricted.EnumerateArray().Select(v => v.GetString() ?? "")
                    .ToHashSet(StringComparer.OrdinalIgnoreCase);
        }
        catch { }
    }

    private void SaveSettings()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_settingsPath)!);
            var restricted = Actions.Where(a => _restrict.TryGetValue(a, out var c) && c.Checked).ToArray();
            _configuredRestrictions = restricted.ToHashSet(StringComparer.OrdinalIgnoreCase);
            File.WriteAllText(_settingsPath, JsonSerializer.Serialize(new { bindings = _bindings, restrict = restricted }, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch (Exception ex) { _deviceStatus.Text = "Could not save settings: " + ex.Message; }
    }

    private void StartBridge()
    {
        try
        {
            _hmContext = new HMContext();
            _hmContext.LoadDefaultProfiles();
            _hmContext.InstallDriver();
            var profile = _hmContext.GetProfile("xbox-360-wired") ?? throw new InvalidOperationException("HIDMaestro profile xbox-360-wired was not found.");
            _virtualPad = _hmContext.CreateController(profile, "rocket-league-input-bridge");
            _deviceStatus.Text = "HIDMaestro virtual Xbox controller ready. Configure HidHide before testing blocked controller binds.";
        }
        catch (Exception ex)
        {
            _deviceStatus.Text = "Virtual controller unavailable: " + ex.Message;
        }
        _ = Task.Run(ListenForApClientAsync);
    }

    private async Task ListenForApClientAsync()
    {
        _bridgeListener = new TcpListener(IPAddress.Loopback, 49125);
        try
        {
            _bridgeListener.Start();
            while (!_stop.IsCancellationRequested)
            {
                using var client = await _bridgeListener.AcceptTcpClientAsync(_stop.Token);
                using var reader = new StreamReader(client.GetStream());
                while (!_stop.IsCancellationRequested && await reader.ReadLineAsync(_stop.Token) is { } line)
                {
                    try
                    {
                        using var doc = JsonDocument.Parse(line);
                        _matchActive = doc.RootElement.TryGetProperty("match_active", out var active) && active.GetBoolean();
                        _lastHeartbeatUtc = DateTime.UtcNow;
                    }
                    catch (JsonException) { }
                }
            }
        }
        catch (OperationCanceledException) { }
        catch (SocketException) when (_stop.IsCancellationRequested) { }
        catch (Exception ex) { BeginInvoke(new Action(() => _deviceStatus.Text = "AP bridge listener stopped: " + ex.Message)); }
    }

    private void StopBridge()
    {
        _poll.Stop();
        _stop.Cancel();
        _bridgeListener?.Stop();
        if (_keyboardHook != IntPtr.Zero) NativeMethods.UnhookWindowsHookEx(_keyboardHook);
        _virtualPad?.Dispose();
        _hmContext?.Dispose();
    }

    private IntPtr KeyboardHook(int code, IntPtr wParam, IntPtr lParam)
    {
        if (code >= 0 && (wParam.ToInt32() == NativeMethods.WM_KEYDOWN || wParam.ToInt32() == NativeMethods.WM_SYSKEYDOWN))
        {
            var key = Marshal.PtrToStructure<NativeMethods.KbdLlHookStruct>(lParam).vkCode;
            string keyName = Enum.IsDefined(typeof(Keys), (int)key) ? ((Keys)key).ToString() : "VK_" + key.ToString("X2");
            if (_captureAction is not null && _captureSource == "Key")
            {
                var action = _captureAction;
                BeginInvoke(new Action(() => AddBinding(action, "Key:" + keyName)));
                return new IntPtr(1);
            }
            if (_matchActive && IsRocketLeagueForeground() && ActiveBlockedControls().Contains("Key:" + keyName))
                return new IntPtr(1);
        }
        return NativeMethods.CallNextHookEx(_keyboardHook, code, wParam, lParam);
    }

    private static bool IsRocketLeagueForeground()
    {
        var window = NativeMethods.GetForegroundWindow();
        if (window == IntPtr.Zero) return false;
        NativeMethods.GetWindowThreadProcessId(window, out uint pid);
        try { return Process.GetProcessById((int)pid).ProcessName.Contains("RocketLeague", StringComparison.OrdinalIgnoreCase); }
        catch { return false; }
    }

    private void UpdateStatus()
    {
        _matchStatus.Text = _matchActive ? "AP match: ACTIVE" : "AP match: inactive (input passes through)";
        var restricted = Actions.Where(a => _restrict[a].Checked).ToArray();
        _restrictionStatus.Text = _matchActive ? "Selected restrictions: " + string.Join(", ", restricted) : "Restrictions are armed but inactive";
    }
}

internal static class XInput
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct State { public uint PacketNumber; public Gamepad Gamepad; }
    [StructLayout(LayoutKind.Sequential)]
    internal struct Gamepad
    {
        public ushort Buttons;
        public byte LeftTrigger, RightTrigger;
        public short LeftThumbX, LeftThumbY, RightThumbX, RightThumbY;
    }
    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetState")]
    internal static extern uint GetState(uint userIndex, out State state);
}

internal static class NativeMethods
{
    internal const int WH_KEYBOARD_LL = 13, WM_KEYDOWN = 0x0100, WM_SYSKEYDOWN = 0x0104;
    [StructLayout(LayoutKind.Sequential)] internal struct KbdLlHookStruct { public uint vkCode, scanCode, flags, time; public IntPtr dwExtraInfo; }
    internal delegate IntPtr LowLevelKeyboardProc(int nCode, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", SetLastError = true)] internal static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc callback, IntPtr module, uint threadId);
    [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] internal static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] internal static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr wParam, IntPtr lParam);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] internal static extern IntPtr GetModuleHandle(string? name);
    [DllImport("user32.dll")] internal static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
}

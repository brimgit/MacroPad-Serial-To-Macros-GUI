# MacroPad

A full-featured desktop app for controlling a custom ESP32-based macropad over serial. Built with a **React + Vite** frontend running inside a **pywebview** frameless window, backed by a pure-Python layer for serial communication, audio control, and macro execution.

---

## Features

### Macros
- Assign **press** and **hold** actions to all 8 keys and 4 encoder buttons
- **Configurable hold duration** per key (100–3000 ms, default 500 ms)
- **Drag keys to swap** their assignments directly on the grid
- **Copy / Paste** macros between keys with one click
- **Undo** the last macro edit with a single button
- Supported macro types:

  | Type | Description |
  |---|---|
  | Keyboard Key | Any letter, number, or special key |
  | Media Control | Play/pause, next/prev track, volume up/down, mute |
  | Function Key | F1–F24 |
  | Modifier Key | Ctrl, Shift, Alt, Win, and combos (Ctrl+C, Alt+Tab, etc.) |
  | Type Text | Types a free-form string |
  | Launch | Opens a file, folder, application, or URL |
  | System | Lock screen, sleep, shutdown, or restart |
  | Mute App | Toggles mute for the encoder's assigned audio source |
  | Recorded | Records a full keyboard sequence and replays it with original timing |
  | Multi Action | Chains multiple macro steps into a single key press |

### Encoders
- Each of the 4 encoders independently controls a volume source:
  - **Any audio app** (Discord, Spotify, browsers, games, etc.)
  - **🔊 Master Volume** — system-wide output level
  - **🎤 Microphone** — default capture device input level
- Each app can only be assigned to **one encoder at a time** — assigning it elsewhere automatically clears the previous one
- **Offline indicator** — encoder card shows a yellow **● OFFLINE** badge if the assigned app is not currently running
- Encoder **button macros** (press + hold) assignable per encoder, same types as keys
- **Mute toggle**: pressing the encoder button mutes/unmutes the source
  - LED ring turns **solid red** while muted
  - Turning while muted **flashes red continuously**, then gives 3 final blinks to confirm still muted
  - Mute state is **read on connect** so the ring reflects reality immediately

### LED Ring
Each encoder card shows a live **10-LED ring preview** that mirrors the physical device:
- **Volume display** — LEDs fill proportional to current volume %, shown for 2 s after each turn
- **Idle animations**:

  | Effect | Description |
  |---|---|
  | Off | Strip turns off after timeout |
  | Breathe | All LEDs pulse in and out (smootherstep curve) |
  | Wave | Brightness ripples across the ring |
  | Rainbow | Hue band scrolls around the ring |
  | Chase | Bright spot bounces with fade trail |
  | Color Cycle | All LEDs drift through the full spectrum |
  | Sparkle | Random LEDs flash in the encoder's color |

- **LED modes** (color while active):
  - **Default** — green→red gradient tracking volume
  - **Solid** — single custom color
  - **Fade** — gradient between two custom colors

### Profiles
- **Create, rename, duplicate, and delete** named profiles
- Each profile stores: all key macros, encoder button macros, encoder app assignments, LED mode/colors/effects
- **Import / Export** profiles as `.json` files
- Profiles are stored as **individual files** (`Data/profiles/{name}.json`) — easy to back up, diff, and share
- **Auto profile switching** — configure a list of trigger apps per profile; the active profile switches automatically when that app comes into focus

### Settings
| Setting | Description |
|---|---|
| Serial Port & Baud Rate | Connect to the MacroPad over any COM port |
| LED Brightness | Global brightness (0–100%) sent to device on change |
| Enc LED Off | Idle timeout before encoder strip turns off (2 / 5 / 10 s) |
| Effect Speed | Animation frame rate: 5 ms (Ultra) → 50 ms (Light) |
| Export / Import Profile | Save or load the active profile as a `.json` file |
| Start with Windows | Adds MacroPad to the Windows startup registry key |

### Other
- **Device auto-detection** — on startup the app sends a `PING` to the configured port and looks for `MACROPAD_OK`; if the wrong port is saved it scans all available ports automatically and updates the setting
- **Frameless window** with a custom title bar — minimize, maximize, and close buttons blend into the app's colour scheme; the bar is draggable
- **Collapsible sidebar** — collapse to icon-only mode to save screen space; hover tooltips identify each page
- **Auto-reconnect** — if the device is unplugged the app reconnects automatically and restores all LED state
- **Test Mode** — shows all 8 key assignments with live flash highlighting and a scrolling event log when keys are pressed
- **Firmware Upload** — compile and flash `.ino` sketches directly from the app via Arduino CLI with a live log output
- **Update checker** — checks GitHub for a newer version on the Settings page

---

## Hardware

PCB designed in **KiCad** — schematic, board files, and Gerber files are in `PCB_files/`. Order directly from any PCB manufacturer with the Gerbers.

**ESP32** microcontroller with:
- 4× rotary encoders with push button (A/B/C/D)
- 8× mechanical keys (1–8)
- 4× NeoPixel LED strips (10 LEDs each, surrounding each encoder knob)

---

## Running from Source

### Requirements
- Python 3.10+
- Node.js 18+ (for building the frontend)

### Install dependencies

```bash
git clone https://github.com/brimgit/MacroPad-Serial-To-Macros-GUI
cd MacroPad-Serial-To-Macros-GUI

# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### Development mode (hot-reload)

```bash
# Terminal 1 — Vite dev server
cd frontend
npm run dev

# Terminal 2 — Python backend (connects to Vite at localhost:5173)
python src/main_webview.py --dev
```

### Production mode (no Node.js needed at runtime)

```bash
# Build the frontend once
cd frontend
npm run build
cd ..

# Run the app
python src/main_webview.py
```

### Python dependencies

| Package | Purpose |
|---|---|
| pywebview | Native frameless window hosting the React frontend |
| pyserial | Serial communication with ESP32 |
| keyboard | Macro execution and keystroke recording |
| pycaw | Windows audio session / endpoint volume control |
| psutil | Process name lookup for auto profile switching |

### Frontend stack

| Package | Purpose |
|---|---|
| React 19 | UI framework |
| Vite | Build tool and dev server |

---

## Project Structure

```
src/
  main_webview.py      # Entry point — creates frameless pywebview window
  api.py               # Python API exposed to React via pywebview JS bridge
  macro_manager.py     # Macro storage, persistence, and execution
  profile_manager.py   # Profile CRUD, per-file JSON persistence
  serial_manager.py    # Serial connection, device identification, auto-reconnect
  volume_manager.py    # Per-app, master, and microphone volume control (pycaw)
  foreground_watcher.py# Polls foreground window for auto profile switching
  utils.py             # Path helpers for PyInstaller and data directory

frontend/
  src/
    App.jsx                     # Root component, state, event listeners
    components/
      Sidebar.jsx               # Navigation, profile management, theme toggle, collapse
      TitleBar.jsx              # Custom frameless title bar with window controls
      MacroModal.jsx            # Shared macro assignment modal (all types + Multi Action)
    pages/
      MacrosPage.jsx            # 2×4 key grid — drag/swap, copy/paste, undo
      EncodersPage.jsx          # Encoder cards with LED ring, volume, button macros
      SettingsPage.jsx          # Serial, brightness, LED, startup, import/export
      UploadPage.jsx            # Arduino CLI firmware upload with live log
      TestPage.jsx              # Live key-press display and event log

Data/
  profiles/            # One .json file per profile + _meta.json for active pointer
  settings_serial.json # Serial port, brightness, LED timeout, effect speed

PCB_files/             # KiCad schematic, board, and Gerber files
MacroPad_Arduino_Code/ # ESP32 firmware
```

---

## Firmware

The Arduino sketch is in `MacroPad_Arduino_Code/`. Upload it via the **Upload Firmware** page in the app (requires Arduino CLI) or via the Arduino IDE.

The firmware handles:
- Encoder tick detection → `E:{id}:{+/-}` serial output (0-indexed)
- Key press/release with hold-duration reporting → `KP:{key}:DOWN` / `KP:{key}:UP:{ms}`
- Device identification → responds to `PING` with `MACROPAD_OK`
- NeoPixel LED control: color modes, brightness, idle animations, effect speed, timeout
- Serial command protocol: `BRIGHT:`, `{n}:color(r,g,b)`, `{n}:colorfade(...)`, `EFFECT:{n}:{id}`, `ENC_TIMEOUT:`, `EFFECT_SPEED:`
- EEPROM persistence of LED color/mode settings across power cycles

---

## License

[MIT License](https://opensource.org/license/MIT)

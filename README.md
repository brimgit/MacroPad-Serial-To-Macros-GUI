# MacroPad Serial GUI

A full-featured Python desktop app for controlling a custom ESP32-based macropad over serial. Configure macros, encoder volume control, RGB LED effects, and profiles — all from a clean dark UI.

---

## Features

### Macros
- Assign **press** and **hold** actions to all 8 keys and 4 encoder buttons independently
- Supported macro types:
  - **Keyboard Key** — any letter, number, or special key
  - **Media Control** — play/pause, next/previous track, stop, volume up/down
  - **Function Key** — F1–F24
  - **Modifier Key** — Ctrl, Shift, Alt, Win, and common combos (Ctrl+C, Alt+Tab, etc.)
  - **Type Text** — types a free-form string of text
  - **Mute App** — toggles mute for the app assigned to that encoder
  - **Recorded** — records and replays a full keyboard sequence

### Encoders
- Each of the 4 encoders controls the volume of a **selectable audio app**
- Volume percentage shown live next to the LED bar
- **Default mode**: encoder button auto-mutes/unmutes the assigned app with no macro needed
- **Mute visual feedback**:
  - LED ring turns **solid red** when muted
  - Turning the encoder while muted **flashes red 3 times** to indicate it's muted
  - Mute state is **detected on startup** — if the app is already muted, the ring shows red immediately

### LED Lighting
**Per-encoder LED modes** (color shown while encoder is active):
- **Default** — green→red gradient bar showing volume level
- **Solid** — custom single color
- **Fade** — two-color gradient with adjustable blend point

**Idle animations** (plays when the encoder hasn't been turned recently):
- **Off** — strip turns off after the configured timeout
- **Breathe** — smooth sine pulse using a natural easing curve
- **Wave** — ripple effect rolling across the strip
- **Rainbow** — scrolling hue band across all LEDs
- **Chase** — glowing dot with a fading trail
- **Color Cycle** — all LEDs slowly drift through the full color spectrum together
- **Sparkle** — random twinkling in the encoder's assigned color

### Profiles
- Create, switch, and delete **named profiles**
- Each profile stores: all key macros, encoder button macros, encoder app assignments, LED mode/colors, and idle animation
- **Auto-switch by app** — assign `.exe` names to a profile; the profile activates automatically when that app gains focus
- **Import / Export** profiles as `.json` files to share or back up
- Profile selector in the sidebar with quick-switch from the **system tray**

### Settings
| Setting | Description |
|---|---|
| Serial Port & Baud Rate | Connect to the MacroPad over any COM port |
| LED Brightness | Global brightness slider (1–100%) |
| Enc LED Off | How long after last turn before the encoder strip turns off (2 / 5 / 10 s) |
| Effect Speed | Animation update rate: 5 ms (Ultra) → 50 ms (Light) |
| Start with Windows | Adds the app to the Windows registry startup key |
| Export / Import Profile | Save or load a profile as a `.json` file |

### Other
- **System tray** — closing the window minimizes to tray; right-click to switch profiles or quit
- **Auto-reconnect** — if the device is unplugged, the app reconnects automatically and restores LED state
- **Test Mode** — dedicated page showing all key assignments with live highlighting and an event log when keys are pressed
- **Firmware Upload** — upload `.ino` sketches directly from within the app via Arduino CLI

---

## Hardware

The PCB was designed in **KiCad**. Schematic and board files are included in `PCB_files/`. Gerber files are also provided so you can order directly from any PCB manufacturer.

**ESP32** microcontroller with:
- 4× rotary encoders (with push button)
- 8× mechanical keys (3×4 matrix)
- 4× NeoPixel LED strips (10 LEDs each)

---

## Running from Source

**Requirements:** Python 3.10+

```bash
git clone https://github.com/brimgit/MacroPad-Serial-To-Macros-GUI
cd MacroPad-Serial-To-Macros-GUI
pip install -r requirements.txt
python MacroPad.pyw
```

Or on Windows, double-click `Launch MacroPad.vbs` to run without a console window.

### Dependencies
| Package | Purpose |
|---|---|
| PyQt5 | GUI framework |
| pyserial | Serial communication with ESP32 |
| keyboard | Macro execution |
| pycaw | Windows audio session control |
| psutil | Process name detection for auto-profile switching |

---

## Firmware

The Arduino sketch is in `MacroPad_Arduino_Code/`. Upload it to your ESP32 using the **Upload** page in the app (requires Arduino CLI installed) or via the Arduino IDE.

The firmware handles:
- Encoder tick detection and serial output
- Key matrix scanning with hold-duration reporting
- NeoPixel LED control with 6 idle animation effects at configurable frame rate
- Serial command protocol for color, brightness, effects, and timeouts

---

## Development

```bash
# Clone and set up
git clone https://github.com/brimgit/MacroPad-Serial-To-Macros-GUI
cd MacroPad-Serial-To-Macros-GUI
pip install -r requirements.txt

# Source layout
src/
  gui.py            # Main window, pages, MacroPadApp
  widgets.py        # EncoderCard, KeyCard, MacroAssignDialog, LEDPreview
  macro_manager.py  # Macro storage and execution
  profile_manager.py# Profile CRUD and persistence
  serial_manager.py # Serial connection and auto-reconnect
  volume_manager.py # Windows audio session control
  auto_profile.py   # Foreground window watcher for auto profile switching
  theme.py          # Colors and stylesheet
```

Pull requests are welcome. Please test changes against a live device before submitting.

---

## License

This project is licensed under the [MIT License](https://opensource.org/license/MIT).

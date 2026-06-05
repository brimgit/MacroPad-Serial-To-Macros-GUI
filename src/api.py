"""
Python API exposed to the React frontend via pywebview.
All public methods are callable from JS as:
    await window.pywebview.api.method_name(args)
"""
import json
import logging
import os
import threading
import time
import subprocess
import urllib.request
import urllib.error
import macro_manager
import profile_manager
from utils import get_data_path

log = logging.getLogger(__name__)

_DEFAULT_ENCODER = {
    'app': '', 'app_shift': '', 'mode': 'default',
    'color': [6, 182, 212], 'color2': [255, 100, 0],
    'blend_start': 0, 'effect': 'Off',
}

_EFFECT_MAP = {
    'Off': 0, 'Breathe': 1, 'Wave': 2,
    'Rainbow': 3, 'Chase': 4, 'Color Cycle': 5, 'Sparkle': 6,
}


def _color_cmd(enc_id: int, enc: dict) -> str:
    """Build the Arduino color command for one encoder (1-indexed on the wire)."""
    n    = enc_id + 1
    mode = enc.get('mode', 'default')
    r,  g,  b  = enc.get('color',  [6, 182, 212])
    r2, g2, b2 = enc.get('color2', [255, 100, 0])
    bl         = enc.get('blend_start', 0)
    if mode == 'default':
        return f'{n}:colorfade(0,200,0,200,0,0,0)'
    elif mode == 'fade':
        return f'{n}:colorfade({r},{g},{b},{r2},{g2},{b2},{bl})'
    else:  # solid
        return f'{n}:color({r},{g},{b})'


def _effect_cmd(enc_id: int, enc: dict) -> str:
    val = _EFFECT_MAP.get(enc.get('effect', 'Off'), 0)
    return f'EFFECT:{enc_id + 1}:{val}'


class MacroPadAPI:
    def __init__(self):
        self._window        = None
        self._serial_mgr    = None
        self._connected     = False
        self._port          = ''
        self._profile_data  = {}
        self._settings      = {}
        self._connect_lock        = threading.Lock()
        self._key_down_times      = {}
        self._enc_muted           = {0:False,1:False,2:False,3:False}
        self._enc_muted_last_turn = {}
        self._enc_muted_flashing  = {}
        self._recording_buf       = None
        self._shift_active        = False   # encoder layer shift
        self._shift_turned        = False   # encoder turned while shift held
        self._fw                  = None    # ForegroundWatcher

    # ── window reference ──────────────────────────────────────────────────────
    def set_window(self, window):
        self._window = window
        self._maximized = False

    def minimize_window(self):
        if self._window: self._window.minimize()
        return {'ok': True}

    def toggle_maximize_window(self):
        if self._window:
            if self._maximized:
                self._window.restore()
            else:
                self._window.maximize()
            self._maximized = not self._maximized
        return {'ok': True, 'maximized': self._maximized}

    def close_window(self):
        if self._window: self._window.destroy()
        return {'ok': True}

    def _push(self, event: str, payload):
        if self._window:
            safe = json.dumps(payload).replace("'", "\\'")
            self._window.evaluate_js(
                f"window.__macropadEvent && window.__macropadEvent('{event}', {safe})",
                callback=lambda _: None,
            )

    def _default_encoders(self):
        return [dict(_DEFAULT_ENCODER) for _ in range(4)]

    def _serial_send(self, cmd: str):
        if self._serial_mgr:
            self._serial_mgr.send_data(cmd + '\n')

    # ── Startup ───────────────────────────────────────────────────────────────
    def startup(self):
        existing = macro_manager.reload_macros()
        self._profile_data = profile_manager.load(existing)
        active = profile_manager.get_active(self._profile_data)
        macro_manager.macros.clear()
        macro_manager.macros.update(active.get('macros', existing))

        settings = self._load_settings()
        self._settings = settings

        port  = settings.get('port', 'COM6')
        baud  = int(settings.get('baud_rate', 115200))
        threading.Thread(target=self._do_connect, args=(port, baud), daemon=True).start()

        # Start foreground watcher for auto profile switching
        from foreground_watcher import ForegroundWatcher
        self._fw = ForegroundWatcher(self._on_foreground_change)
        self._fw.start()

        return {
            'macros':      macro_manager.macros,
            'profiles':    profile_manager.get_names(self._profile_data),
            'active':      profile_manager.get_active_name(self._profile_data),
            'settings':    settings,
            'encoders':    active.get('encoders', self._default_encoders()),
            'trigger_apps': profile_manager.get_active(self._profile_data).get('trigger_apps', []),
        }

    # ── Serial ────────────────────────────────────────────────────────────────
    def get_ports(self):
        from serial_manager import list_ports
        return list_ports()

    def connect(self, port, baud):
        threading.Thread(target=self._do_connect, args=(port, int(baud)), daemon=True).start()
        return {'ok': True}

    def disconnect(self):
        if self._serial_mgr:
            self._serial_mgr.stop()
            self._serial_mgr = None
        self._connected = False
        self._push('connection', {'connected': False, 'port': ''})
        return {'ok': True}

    def _do_connect(self, port, baud):
        if not self._connect_lock.acquire(blocking=False):
            return  # another connect call is already in progress — ignore this one
        try:
            if self._serial_mgr:
                try:
                    self._serial_mgr.stop()
                except Exception as e:
                    log.debug(f'Error stopping previous serial manager: {e}')
                self._serial_mgr = None
            from serial_manager import SerialManager
            self._serial_mgr = SerialManager(
                data_callback=self._on_serial_data,
                connected_callback=self._on_connection_changed,
                port=port,
                baud_rate=baud,
            )
            self._connected = True
            self._port = port
            self._push('connection', {'connected': True, 'port': port})
            self._save_settings_field('port', port)
            self._save_settings_field('baud_rate', str(baud))
        except Exception as e:
            self._connected = False
            self._push('connection', {'connected': False, 'port': '', 'error': str(e)})
        finally:
            self._connect_lock.release()

    def _on_connection_changed(self, connected):
        self._connected = connected
        if connected and self._serial_mgr:
            actual = self._serial_mgr.port
            if actual != self._port:
                log.info(f'Auto-connected to {actual} (was configured for {self._port})')
                self._port = actual
                self._save_settings_field('port', actual)
        self._push('connection', {'connected': connected, 'port': self._port if connected else ''})
        if connected:
            # Delay slightly so the ESP32 finishes booting before we flood it
            threading.Thread(target=self._send_initial_state, daemon=True).start()

    def _send_initial_state(self):
        """Send brightness, LED colors, effects, and volume levels on connect."""
        time.sleep(2.5)
        s = self._load_settings()
        brightness_pct = s.get('brightness_pct', 10)
        self._serial_send(f'BRIGHT:{round(brightness_pct * 255 / 100)}')
        time.sleep(0.05)
        active   = profile_manager.get_active(self._profile_data)
        encoders = active.get('encoders', self._default_encoders())

        enc_timeout = s.get('enc_led_timeout', 2)
        self._serial_send(f'ENC_TIMEOUT:{enc_timeout}')
        time.sleep(0.05)
        effect_speed = s.get('effect_speed_ms', 10)
        self._serial_send(f'EFFECT_SPEED:{effect_speed}')
        time.sleep(0.05)

        from volume_manager import MASTER_APP, MIC_APP
        for enc_id, enc in enumerate(encoders):
            n   = enc_id + 1
            app = enc.get('app', '')
            vm  = self._serial_mgr.volume_manager if self._serial_mgr else None

            # Read mute state (master/mic don't support per-app mute)
            muted = False
            if vm and app and app not in (MASTER_APP, MIC_APP):
                try:
                    muted = bool(vm.get_mute(app))
                except Exception as e:
                    log.debug(f'Could not read mute state for {app}: {e}')
            self._enc_muted[enc_id] = muted

            if muted:
                self._serial_send(f'{n}:color(200,0,0)')
                time.sleep(0.06)
                self._serial_send(f'{n}:100')
            else:
                self._serial_send(_color_cmd(enc_id, enc))
                time.sleep(0.06)
                if vm and app:
                    pct = 0
                    try:
                        if app == MASTER_APP:
                            pct = vm.get_master_volume() or 0
                        elif app == MIC_APP:
                            pct = vm.get_mic_volume() or 0
                        else:
                            pct = vm.get_volume(app) or 0
                    except Exception as e:
                        log.debug(f'Could not read volume for {app}: {e}')
                    self._serial_send(f'{n}:{pct}')
            time.sleep(0.06)
            self._serial_send(_effect_cmd(enc_id, enc))
            time.sleep(0.06)

    def _on_serial_data(self, data):
        data = data.strip()
        if not data:
            return
        parts = data.split(':')

        # Encoder rotation — adjust volume and update LED ring
        if parts[0] == 'E' and len(parts) == 3:
            try:
                enc_id    = int(parts[1])
                direction = parts[2]
                increase  = direction == '+'
                active    = profile_manager.get_active(self._profile_data)
                encoders  = active.get('encoders', [])
                enc       = encoders[enc_id] if enc_id < len(encoders) else {}
                # Use shifted app if shift key is held and a shift app is configured
                if self._shift_active and enc.get('app_shift'):
                    app = enc['app_shift']
                    self._shift_turned = True
                else:
                    app = enc.get('app', '')
                pct       = -1
                if self._enc_muted.get(enc_id, False):
                    # Record this turn's time; start the flash thread only if not already running
                    self._enc_muted_last_turn[enc_id] = time.monotonic()
                    if not self._enc_muted_flashing.get(enc_id, False):
                        threading.Thread(
                            target=self._muted_continuous_flash,
                            args=(enc_id,), daemon=True,
                        ).start()
                    self._push('encoder_turn', {'id': enc_id, 'direction': direction, 'app': app, 'pct': -1, 'muted': True})
                elif app and self._serial_mgr:
                    vm  = self._serial_mgr.volume_manager
                    from volume_manager import MASTER_APP, MIC_APP
                    if app == MASTER_APP:
                        val = vm.adjust_master_volume(increase)
                    elif app == MIC_APP:
                        val = vm.adjust_mic_volume(increase)
                    else:
                        val = vm.adjust_volume(app, increase=increase)
                    if val is not None:
                        pct = val
                        self._serial_send(f'{enc_id + 1}:{pct}')
                    self._push('encoder_turn', {'id': enc_id, 'direction': direction, 'app': app, 'pct': pct})
                else:
                    self._push('encoder_turn', {'id': enc_id, 'direction': direction, 'app': app, 'pct': pct})
            except Exception as e:
                log.warning(f'Error processing encoder event: {e}')
            return

        # Key event
        if parts[0] == 'KP' and len(parts) >= 3:
            key   = parts[1]
            event = parts[2]
            shift_key = self._settings.get('shift_key', '')
            if event == 'DOWN':
                self._key_down_times[key] = time.monotonic()
                if shift_key and key == shift_key:
                    self._shift_active  = True
                    self._shift_turned  = False
            elif event == 'UP':
                if shift_key and key == shift_key:
                    self._shift_active = False
                    if self._shift_turned:
                        self._shift_turned = False
                        return  # suppress macro fire — key was used as shift
                # Use firmware-provided duration if present, else calculate from DOWN timestamp
                if len(parts) >= 4:
                    try:
                        ms = int(parts[3])
                    except ValueError:
                        ms = 0
                else:
                    down_t = self._key_down_times.pop(key, None)
                    ms = round((time.monotonic() - down_t) * 1000) if down_t else 0
                hold_entry = macro_manager.macros.get(f'KP:{key}:HOLD')
                threshold  = hold_entry.get('hold_ms', 500) if hold_entry else 500
                macro_key  = f'KP:{key}:HOLD' if ms >= threshold else f'KP:{key}'
                macro      = macro_manager.macros.get(macro_key)
                if macro and macro.get('type') == 'Mute App':
                    self._execute_mute_app(key)
                else:
                    macro_manager.execute_macro(macro_key)
                self._push('key_press', {'key': key, 'macro_key': macro_key, 'macro': macro, 'ms': ms})

    def send_command(self, cmd):
        if self._serial_mgr:
            self._serial_mgr.send_data(cmd + '\n')
        return {'ok': True}

    # ── Macros ────────────────────────────────────────────────────────────────
    def get_macros(self):
        return dict(macro_manager.macros)

    def set_macro(self, key, macro_type, action, hold_ms=None):
        macro_manager.set_macro(key, macro_type, action,
                                hold_ms=int(hold_ms) if hold_ms is not None else None)
        macro_manager.save_macros()
        self._queue_profile_save()
        return {'ok': True}

    def delete_macro(self, key):
        try:
            macro_manager.delete_macro(key)
        except KeyError:
            pass
        self._queue_profile_save()
        return {'ok': True}

    # ── Profiles ──────────────────────────────────────────────────────────────
    def get_profiles(self):
        return {
            'names':  profile_manager.get_names(self._profile_data),
            'active': profile_manager.get_active_name(self._profile_data),
        }

    def switch_profile(self, name):
        profile_manager.switch(self._profile_data, name)
        active = profile_manager.get_active(self._profile_data)
        macro_manager.macros.clear()
        macro_manager.macros.update(active.get('macros', {}))
        macro_manager.save_macros()
        profile_manager.save(self._profile_data)
        # Re-send LED state for new profile's encoder configs
        threading.Thread(target=self._send_initial_state, daemon=True).start()
        return {
            'ok': True,
            'macros':   dict(macro_manager.macros),
            'encoders': active.get('encoders', self._default_encoders()),
        }

    def new_profile(self, name):
        if name in profile_manager.get_names(self._profile_data):
            return {'ok': False, 'error': 'Profile already exists'}
        profile_manager.create(self._profile_data, name)
        profile_manager.save(self._profile_data)
        return {'ok': True}

    def delete_profile(self, name):
        if len(profile_manager.get_names(self._profile_data)) <= 1:
            return {'ok': False, 'error': 'Cannot delete the last profile'}
        profile_manager.delete(self._profile_data, name)
        profile_manager.save(self._profile_data)
        return {'ok': True}

    def duplicate_profile(self, name: str):
        new_name = profile_manager.duplicate(self._profile_data, name)
        if not new_name:
            return {'ok': False, 'error': 'Profile not found'}
        profile_manager.save(self._profile_data)
        return {
            'ok':    True,
            'name':  new_name,
            'names': profile_manager.get_names(self._profile_data),
        }

    def rename_profile(self, old_name: str, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            return {'ok': False, 'error': 'Name cannot be empty'}
        if new_name in profile_manager.get_names(self._profile_data):
            return {'ok': False, 'error': 'Name already exists'}
        if not profile_manager.rename(self._profile_data, old_name, new_name):
            return {'ok': False, 'error': 'Rename failed'}
        profile_manager.save(self._profile_data)
        return {
            'ok':     True,
            'names':  profile_manager.get_names(self._profile_data),
            'active': profile_manager.get_active_name(self._profile_data),
        }

    def export_profile(self, name: str):
        return profile_manager.export_profile(self._profile_data, name)

    def import_profile(self, exported: dict):
        new_name = profile_manager.import_profile(self._profile_data, exported)
        profile_manager.save(self._profile_data)
        return {'ok': True, 'name': new_name}

    def _queue_profile_save(self):
        active         = profile_manager.get_active(self._profile_data)
        encoder_states = active.get('encoders', self._default_encoders())
        profile_manager.update_profile(self._profile_data, macro_manager.macros, encoder_states)
        profile_manager.save(self._profile_data)

    # ── Encoders ──────────────────────────────────────────────────────────────
    def get_encoders(self):
        active = profile_manager.get_active(self._profile_data)
        return active.get('encoders', self._default_encoders())

    def set_encoder(self, idx: int, config: dict):
        active_name = profile_manager.get_active_name(self._profile_data)
        if active_name not in self._profile_data['profiles']:
            return {'ok': False}
        prof     = self._profile_data['profiles'][active_name]
        enc_list = prof.setdefault('encoders', self._default_encoders())
        while len(enc_list) <= idx:
            enc_list.append(dict(_DEFAULT_ENCODER))

        # Enforce uniqueness: if this app is already on another encoder, clear it there
        new_app = config.get('app', enc_list[idx].get('app', ''))
        if new_app:
            for i, other in enumerate(enc_list):
                if i != idx and other.get('app') == new_app:
                    other['app'] = ''
                    # Reset that encoder's LED on the device
                    self._serial_send(_color_cmd(i, other))
                    self._serial_send(_effect_cmd(i, other))

        enc_list[idx].update(config)
        profile_manager.save(self._profile_data)

        # Push updated color/effect to device
        enc = enc_list[idx]
        self._restore_encoder_led(idx)
        self._serial_send(_effect_cmd(idx, enc))

        return {'ok': True, 'encoders': [dict(e) for e in enc_list]}

    # ── Trigger apps (auto profile switching) ────────────────────────────────
    def get_trigger_apps(self, profile_name: str):
        return self._profile_data.get('profiles', {}).get(profile_name, {}).get('trigger_apps', [])

    def set_trigger_apps(self, profile_name: str, apps: list):
        profile_manager.set_trigger_apps(self._profile_data, profile_name, list(apps))
        profile_manager.save(self._profile_data)
        return {'ok': True}

    def _on_foreground_change(self, app_name: str):
        found = profile_manager.find_profile_for_app(self._profile_data, app_name)
        if not found:
            return
        current = profile_manager.get_active_name(self._profile_data)
        if found == current:
            return
        log.info(f'Auto-switching to profile {found!r} (foreground: {app_name})')
        profile_manager.switch(self._profile_data, found)
        active = profile_manager.get_active(self._profile_data)
        macro_manager.macros.clear()
        macro_manager.macros.update(active.get('macros', {}))
        self._push('profile_switch', {
            'active':      found,
            'macros':      dict(macro_manager.macros),
            'encoders':    active.get('encoders', self._default_encoders()),
            'trigger_apps': active.get('trigger_apps', []),
        })
        threading.Thread(target=self._send_initial_state, daemon=True).start()

    # ── Startup with Windows ──────────────────────────────────────────────────
    def get_startup(self):
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r'Software\Microsoft\Windows\CurrentVersion\Run',
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, 'MacroPad')
            winreg.CloseKey(key)
            return {'ok': True, 'enabled': True}
        except Exception:
            return {'ok': True, 'enabled': False}

    def set_startup(self, enabled: bool):
        import winreg
        import sys
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        try:
            reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                exe    = sys.executable.replace('python.exe', 'pythonw.exe')
                script = os.path.normpath(os.path.join(os.path.dirname(__file__), 'main_webview.py'))
                winreg.SetValueEx(reg, 'MacroPad', 0, winreg.REG_SZ, f'"{exe}" "{script}"')
            else:
                try:
                    winreg.DeleteValue(reg, 'MacroPad')
                except FileNotFoundError:
                    pass
            winreg.CloseKey(reg)
            return {'ok': True, 'enabled': enabled}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ── Encoder shift key ─────────────────────────────────────────────────────
    def get_shift_key(self):
        return self._settings.get('shift_key', '')

    def set_shift_key(self, key: str):
        self._settings['shift_key'] = key
        self._save_settings_field('shift_key', key)
        return {'ok': True}

    # ── Settings ──────────────────────────────────────────────────────────────
    def get_settings(self):
        return self._load_settings()

    def save_settings(self, settings: dict):
        try:
            with open(get_data_path('settings_serial.json'), 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        return {'ok': True}

    def set_brightness(self, pct: int):
        self._serial_send(f'BRIGHT:{round(pct * 255 / 100)}')
        self._save_settings_field('brightness_pct', pct)
        return {'ok': True}

    def set_enc_led_timeout(self, secs: int):
        self._serial_send(f'ENC_TIMEOUT:{secs}')
        self._save_settings_field('enc_led_timeout', secs)
        return {'ok': True}

    def set_effect_speed(self, ms: int):
        self._serial_send(f'EFFECT_SPEED:{ms}')
        self._save_settings_field('effect_speed_ms', ms)
        return {'ok': True}

    def get_audio_apps(self):
        if self._serial_mgr:
            try:
                return self._serial_mgr.volume_manager.get_available_processes()
            except Exception as e:
                log.warning(f'get_audio_apps via serial_mgr failed: {e}')
        try:
            from volume_manager import VolumeManager
            return VolumeManager().get_available_processes()
        except Exception as e:
            log.warning(f'get_audio_apps fallback failed: {e}')
            return []

    # ── Macro Recording ───────────────────────────────────────────────────────
    def start_recording(self):
        try:
            import keyboard as kb
            self._recording_buf = kb.start_recording()
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_recording_status(self):
        count = len(self._recording_buf) if self._recording_buf is not None else 0
        return {'ok': True, 'count': count}

    def stop_recording(self):
        try:
            import keyboard as kb
            events = kb.stop_recording()
            self._recording_buf = None
            # Normalise timestamps so the first event starts at t=0
            t0 = events[0].time if events else 0
            data = [
                {
                    'event_type': e.event_type,
                    'scan_code':  int(e.scan_code or 0),
                    'name':       e.name,
                    'time':       round(e.time - t0, 4),
                }
                for e in events
            ]
            return {'ok': True, 'events': json.dumps(data), 'count': len(data)}
        except Exception as e:
            self._recording_buf = None
            return {'ok': False, 'error': str(e)}

    # ── Firmware Upload ───────────────────────────────────────────────────────
    def upload_firmware(self, ino_path: str, cli_path: str, action: str, board: str, port: str):
        def _run():
            if self._serial_mgr:
                self._serial_mgr.stop()
            try:
                compile_cmd = f'"{cli_path}" compile --fqbn {board} "{ino_path}"'
                r = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True, timeout=120)
                self._push('upload_log', {'line': r.stdout or r.stderr or 'Compile done', 'ok': r.returncode == 0})
                if r.returncode != 0:
                    self._push('upload_done', {'ok': False, 'error': 'Compilation failed'})
                    return
                if action == 'upload':
                    upload_cmd = f'"{cli_path}" upload --fqbn {board} --port {port} "{ino_path}"'
                    r2 = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True, timeout=120)
                    self._push('upload_log', {'line': r2.stdout or r2.stderr or 'Upload done', 'ok': r2.returncode == 0})
                    self._push('upload_done', {'ok': r2.returncode == 0})
                else:
                    self._push('upload_done', {'ok': True})
            except Exception as e:
                self._push('upload_done', {'ok': False, 'error': str(e)})
            finally:
                if self._serial_mgr:
                    self._serial_mgr.start()

        threading.Thread(target=_run, daemon=True).start()
        return {'ok': True, 'started': True}

    # ── Mute App helper ───────────────────────────────────────────────────────
    _BTN_TO_ENC = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

    def _execute_mute_app(self, btn_key: str):
        enc_id = self._BTN_TO_ENC.get(btn_key, -1)
        if enc_id < 0 or not self._serial_mgr:
            return
        active   = profile_manager.get_active(self._profile_data)
        encoders = active.get('encoders', [])
        if enc_id >= len(encoders):
            return
        app = encoders[enc_id].get('app', '')
        if not app:
            return
        from volume_manager import MASTER_APP, MIC_APP
        vm = self._serial_mgr.volume_manager
        if app == MASTER_APP:
            muted = vm.toggle_master_mute()
        elif app == MIC_APP:
            muted = vm.toggle_mic_mute()
        else:
            muted = vm.toggle_mute(app)
        self._enc_muted[enc_id] = bool(muted)
        n = enc_id + 1
        if muted:
            self._serial_send(f'{n}:color(200,0,0)')
            self._serial_send(f'{n}:100')
        else:
            # Restore normal LED — use shared helper so flash thread also benefits
            self._restore_encoder_led(enc_id)
        self._push('mute_change', {'id': enc_id, 'muted': bool(muted), 'app': app})

    def _muted_continuous_flash(self, enc_id: int):
        """
        Continuous fast blink while the encoder is being turned.
        Transitions to 3 slow final blinks once turns stop for 500 ms.
        Exits immediately if the encoder is unmuted mid-flash.
        """
        IDLE_TIMEOUT = 0.50
        FAST_ON      = 0.10
        FAST_OFF     = 0.10
        FINAL_ON     = 0.25
        FINAL_OFF    = 0.20

        n = enc_id + 1
        self._enc_muted_flashing[enc_id] = True

        def still_muted():
            return self._enc_muted.get(enc_id, False)

        try:
            # ── continuous phase ──────────────────────────────────────────────
            while still_muted():
                if time.monotonic() - self._enc_muted_last_turn.get(enc_id, 0) >= IDLE_TIMEOUT:
                    break
                self._serial_send(f'{n}:color(200,0,0)')
                self._serial_send(f'{n}:100')
                time.sleep(FAST_ON)
                if not still_muted():
                    return
                self._serial_send(f'{n}:0')
                time.sleep(FAST_OFF)

            # ── 3 final blinks (only if still muted) ─────────────────────────
            for _ in range(3):
                if not still_muted():
                    return
                self._serial_send(f'{n}:color(200,0,0)')
                self._serial_send(f'{n}:100')
                time.sleep(FINAL_ON)
                if not still_muted():
                    return
                self._serial_send(f'{n}:0')
                time.sleep(FINAL_OFF)

            # Settle to solid red if still muted
            if still_muted():
                self._serial_send(f'{n}:color(200,0,0)')
                self._serial_send(f'{n}:100')
        finally:
            self._enc_muted_flashing[enc_id] = False
            # Guard against the race where a red command was sent just before
            # _execute_mute_app toggled the mute state — re-send normal LED state.
            if not still_muted():
                self._restore_encoder_led(enc_id)

    def _restore_encoder_led(self, enc_id: int):
        """Re-send the configured color + current volume (or mute red) for an encoder."""
        try:
            active   = profile_manager.get_active(self._profile_data)
            encoders = active.get('encoders', [])
            if enc_id >= len(encoders):
                return
            enc = encoders[enc_id]
            n   = enc_id + 1
            if self._enc_muted.get(enc_id, False):
                self._serial_send(f'{n}:color(200,0,0)')
                self._serial_send(f'{n}:100')
                return
            self._serial_send(_color_cmd(enc_id, enc))
            app = enc.get('app', '')
            if app and self._serial_mgr:
                from volume_manager import MASTER_APP, MIC_APP
                vm = self._serial_mgr.volume_manager
                if app == MASTER_APP:
                    vol = vm.get_master_volume() or 0
                elif app == MIC_APP:
                    vol = vm.get_mic_volume() or 0
                else:
                    vol = vm.get_volume(app) or 0
                self._serial_send(f'{n}:{vol}')
        except Exception as e:
            log.debug(f'_restore_encoder_led failed for enc {enc_id}: {e}')

    # ── Update check ──────────────────────────────────────────────────────────
    _REPO      = 'brimgit/MacroPad-Serial-To-Macros-GUI'
    _RAW_URL   = f'https://raw.githubusercontent.com/{_REPO}/main/version.txt'
    _REPO_URL  = f'https://github.com/{_REPO}'

    def check_for_update(self):
        """Fetch version.txt from GitHub and compare with the local version."""
        try:
            local = self._local_version()
        except Exception as e:
            return {'ok': False, 'error': f'Could not read local version: {e}'}

        try:
            req = urllib.request.Request(
                self._RAW_URL,
                headers={'User-Agent': 'MacroPad-version-check/1.0'},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                remote = resp.read().decode().strip()
        except urllib.error.URLError as e:
            return {'ok': False, 'error': f'Could not reach GitHub: {e.reason}', 'current': local}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'current': local}

        return {
            'ok':              True,
            'current':         local,
            'latest':          remote,
            'update_available': self._version_gt(remote, local),
            'repo_url':        self._REPO_URL,
        }

    def _local_version(self) -> str:
        import sys
        if getattr(sys, 'frozen', False):
            path = os.path.join(sys._MEIPASS, 'version.txt')
        else:
            path = os.path.join(os.path.dirname(__file__), '..', 'version.txt')
        with open(os.path.normpath(path), 'r') as f:
            return f.read().strip()

    @staticmethod
    def _version_gt(a: str, b: str) -> bool:
        """Return True if version string a is strictly greater than b."""
        def parts(v):
            return [int(x) for x in v.lstrip('v').split('.')]
        try:
            ap, bp = parts(a), parts(b)
            # Pad to equal length
            while len(ap) < len(bp): ap.append(0)
            while len(bp) < len(ap): bp.append(0)
            return ap > bp
        except Exception:
            return a != b

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _load_settings(self):
        try:
            with open(get_data_path('settings_serial.json'), 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'port': 'COM6', 'baud_rate': '115200', 'brightness_pct': 10}
        except Exception as e:
            log.warning(f'Failed to load settings, using defaults: {e}')
            return {'port': 'COM6', 'baud_rate': '115200', 'brightness_pct': 10}

    def _save_settings_field(self, key, value):
        s = self._load_settings()
        s[key] = value
        self.save_settings(s)

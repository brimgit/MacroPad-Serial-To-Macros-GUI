import json
import os
import time
import logging
import keyboard
from utils import get_data_path

log = logging.getLogger(__name__)

macros = {}

SYSTEM_ACTIONS = ['lock', 'sleep', 'shutdown', 'restart']


def set_macro(command, action_type, action, hold_ms=None):
    entry = {'type': action_type, 'action': action}
    if hold_ms is not None:
        entry['hold_ms'] = int(hold_ms)
    macros[command] = entry
    log.info(f'Macro set: {command} → {action_type}: {action}')


def save_macros():
    path = get_data_path('macros.json')
    try:
        with open(path, 'w') as f:
            json.dump(macros, f, indent=4)
    except IOError as e:
        log.error(f'Failed to save macros: {e}')
        raise


def reload_macros():
    path = get_data_path('macros.json')
    try:
        with open(path, 'r') as f:
            loaded = json.load(f)
        macros.update(loaded)
        log.info(f'Loaded {len(loaded)} macros')
        return loaded
    except FileNotFoundError:
        log.info('macros.json not found — starting empty')
        return {}
    except json.JSONDecodeError as e:
        log.error(f'macros.json is corrupted: {e}')
        return {}


def delete_macro(command):
    if command not in macros:
        raise KeyError(f'No macro for key {command!r}')
    del macros[command]
    save_macros()


def _execute_system(action):
    import ctypes
    if action == 'lock':
        ctypes.windll.user32.LockWorkStation()
    elif action == 'sleep':
        os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
    elif action == 'shutdown':
        os.system('shutdown /s /t 0')
    elif action == 'restart':
        os.system('shutdown /r /t 0')
    else:
        log.warning(f'Unknown system action: {action!r}')


def _execute_step(mtype, action):
    """Execute a single macro step — used by execute_macro and Multi Action."""
    if mtype in ('Keyboard Key', 'Media Control', 'Function Key'):
        keyboard.send(action)
    elif mtype == 'Modifier Key':
        keyboard.press_and_release(action)
    elif mtype == 'Type Text':
        keyboard.write(action)
    elif mtype == 'Launch':
        try:
            os.startfile(action)
        except Exception:
            subprocess.Popen(action, shell=True)
    elif mtype == 'System':
        _execute_system(action)
    elif mtype == 'Delay':
        try:
            time.sleep(max(0.0, min(10.0, float(action))))
        except (ValueError, TypeError):
            pass
    elif mtype == 'Recorded':
        events_data = json.loads(action)
        events = [
            keyboard.KeyboardEvent(
                event_type=e['event_type'],
                scan_code=e.get('scan_code') or 0,
                name=e.get('name'),
                time=e.get('time', 0),
            )
            for e in events_data
        ]
        keyboard.play(events, speed_factor=1)
    elif mtype in ('Mute App', ''):
        pass  # handled in api.py or intentionally empty
    else:
        log.warning(f'Unknown macro type {mtype!r}')


def execute_macro(command):
    macro = macros.get(command)
    if not macro:
        log.debug(f'No macro assigned to {command!r}')
        return

    mtype  = macro.get('type', '')
    action = macro.get('action', '')

    try:
        if mtype == 'Multi Action':
            steps = json.loads(action)
            for step in steps:
                _execute_step(step.get('type', ''), step.get('action', ''))
        else:
            _execute_step(mtype, action)
    except Exception as e:
        log.error(f'Failed to execute {mtype} macro for {command!r}: {e}')
        return

    log.info(f'Executed [{mtype}] {command!r}: {str(action)[:60]}')


import subprocess  # noqa: E402 — after _execute_step definition to avoid circular use

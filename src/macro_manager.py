import json
import logging
import keyboard
from utils import get_data_path

log = logging.getLogger(__name__)

macros = {}


def set_macro(command, action_type, action):
    macros[command] = {'type': action_type, 'action': action}
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


def execute_macro(command):
    macro = macros.get(command)
    if not macro:
        log.debug(f'No macro assigned to {command!r}')
        return

    mtype  = macro.get('type', '')
    action = macro.get('action', '')

    try:
        if mtype in ('Keyboard Key', 'Media Control', 'Function Key'):
            keyboard.send(action)
        elif mtype == 'Modifier Key':
            keyboard.press_and_release(action)
        elif mtype == 'Type Text':
            keyboard.write(action)
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
        elif mtype == 'Mute App':
            pass   # handled in api.py where encoder context is available
        else:
            log.warning(f'Unknown macro type {mtype!r} for key {command!r}')
            return
    except Exception as e:
        log.error(f'Failed to execute {mtype} macro for {command!r}: {e}')
        return

    log.info(f'Executed [{mtype}] {command!r}: {str(action)[:40]}')

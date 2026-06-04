import json
import os
from utils import get_data_path

_DEFAULT_ENCODER = {
    'app': '',
    'mode': 'default',
    'color': [6, 182, 212],
    'color2': [255, 100, 0],
    'blend_start': 0,
}


def _path():
    return get_data_path('profiles.json')


def _default_profile(macros=None):
    return {
        'macros': macros or {},
        'encoders': [dict(_DEFAULT_ENCODER) for _ in range(4)],
        'trigger_apps': [],
    }


def load(existing_macros=None):
    """Load profiles.json. On first run, seed Default from existing_macros."""
    try:
        with open(_path(), 'r') as f:
            data = json.load(f)
        if 'profiles' not in data or not data['profiles']:
            raise ValueError
        if data.get('active') not in data['profiles']:
            data['active'] = next(iter(data['profiles']))
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError, StopIteration):
        data = {
            'active': 'Default',
            'profiles': {'Default': _default_profile(existing_macros)},
        }
        save(data)
        return data


def save(data):
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def get_names(data):
    return list(data['profiles'].keys())


def get_active_name(data):
    return data.get('active', '')


def get_active(data):
    return data['profiles'].get(data.get('active', ''), {})


def switch(data, name):
    if name in data['profiles']:
        data['active'] = name
    return data


def create(data, name):
    if name and name not in data['profiles']:
        data['profiles'][name] = _default_profile()
        data['active'] = name
    return data


def delete(data, name):
    if name in data['profiles'] and len(data['profiles']) > 1:
        del data['profiles'][name]
        if data['active'] == name:
            data['active'] = next(iter(data['profiles']))
    return data


def update_profile(data, macros, encoder_states):
    name = data.get('active', '')
    if name in data['profiles']:
        data['profiles'][name]['macros'] = dict(macros)
        data['profiles'][name]['encoders'] = encoder_states
    return data


def set_trigger_apps(data, name, apps):
    if name in data['profiles']:
        data['profiles'][name]['trigger_apps'] = list(apps)
    return data


def find_profile_for_app(data, app_name):
    """Return the profile name whose trigger_apps contains app_name, or None."""
    if not app_name:
        return None
    for name, profile in data['profiles'].items():
        if app_name in profile.get('trigger_apps', []):
            return name
    return None


def duplicate(data, name):
    """Duplicate a profile, returning the new name."""
    if name not in data['profiles']:
        return None
    import copy
    base     = f'{name} (copy)'
    new_name = base
    counter  = 1
    while new_name in data['profiles']:
        new_name = f'{base} {counter}'
        counter += 1
    data['profiles'][new_name] = copy.deepcopy(data['profiles'][name])
    return new_name


def rename(data, old_name, new_name):
    if old_name not in data['profiles'] or not new_name or new_name == old_name:
        return False
    if new_name in data['profiles']:
        return False
    data['profiles'][new_name] = data['profiles'].pop(old_name)
    if data['active'] == old_name:
        data['active'] = new_name
    return True


def export_profile(data, name):
    """Return a standalone dict for the named profile (for file export)."""
    return {'name': name, 'profile': data['profiles'].get(name, {})}


def import_profile(data, exported):
    """Import an exported profile dict. Returns the new profile name."""
    name = exported.get('name', 'Imported')
    profile = exported.get('profile', {})
    base = name
    counter = 1
    while name in data['profiles']:
        name = f'{base} ({counter})'
        counter += 1
    data['profiles'][name] = profile
    return name

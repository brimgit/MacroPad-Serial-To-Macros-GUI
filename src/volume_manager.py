import time

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    _PYCAW_AVAILABLE = True
except ImportError:
    _PYCAW_AVAILABLE = False


class VolumeManager:
    _CACHE_TTL = 4.0
    _STEP = 0.05  # 5% per encoder tick

    def __init__(self):
        self._cache = None
        self._cache_ts = 0.0

    def _sessions(self, force=False):
        if not _PYCAW_AVAILABLE:
            return []
        now = time.monotonic()
        if force or self._cache is None or (now - self._cache_ts) > self._CACHE_TTL:
            try:
                self._cache = AudioUtilities.GetAllSessions()
                self._cache_ts = now
            except Exception:
                self._cache = []
        return self._cache

    def adjust_volume(self, app_name, increase=True):
        if not app_name:
            return None
        for session in self._sessions():
            if session.Process and session.Process.name() == app_name:
                try:
                    vol = session.SimpleAudioVolume
                    current = vol.GetMasterVolume()
                    new_vol = min(1.0, current + self._STEP) if increase else max(0.0, current - self._STEP)
                    vol.SetMasterVolume(new_vol, None)
                    return round(new_vol * 100)
                except Exception:
                    pass
        # Cache miss — force refresh and retry once
        for session in self._sessions(force=True):
            if session.Process and session.Process.name() == app_name:
                try:
                    vol = session.SimpleAudioVolume
                    current = vol.GetMasterVolume()
                    new_vol = min(1.0, current + self._STEP) if increase else max(0.0, current - self._STEP)
                    vol.SetMasterVolume(new_vol, None)
                    return round(new_vol * 100)
                except Exception:
                    pass
        return None

    def get_mute(self, app_name):
        if not app_name:
            return False
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        return bool(session.SimpleAudioVolume.GetMute())
                    except Exception:
                        pass
            break
        return False

    def get_volume(self, app_name):
        """Return current volume 0-100 without changing it, or None if not found."""
        if not app_name:
            return None
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        return round(session.SimpleAudioVolume.GetMasterVolume() * 100)
                    except Exception:
                        pass
            break
        return None

    def toggle_mute(self, app_name):
        """Toggle mute for a specific app. Returns new mute state or None on failure."""
        if not app_name:
            return None
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        vol = session.SimpleAudioVolume
                        new_state = not vol.GetMute()
                        vol.SetMute(new_state, None)
                        return new_state
                    except Exception:
                        pass
            break  # only retry on cache miss (second iteration handles it)
        return None

    def get_available_processes(self):
        names = []
        for s in self._sessions(force=True):
            if s.Process:
                try:
                    names.append(s.Process.name())
                except Exception:
                    pass
        return sorted(set(names))

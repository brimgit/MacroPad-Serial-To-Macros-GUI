import time
import logging

log = logging.getLogger(__name__)

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER
    _PYCAW_AVAILABLE = True
except ImportError:
    _PYCAW_AVAILABLE = False
    log.warning('pycaw not available — volume control disabled')

# Sentinel values used as the encoder "app" field for special sources
MASTER_APP = '__MASTER__'
MIC_APP    = '__MIC__'


class VolumeManager:
    _CACHE_TTL = 4.0
    _STEP = 0.05  # 5% per encoder tick

    def __init__(self):
        self._cache    = None
        self._cache_ts = 0.0

    # ── per-app (session) volume ───────────────────────────────────────────────

    def _sessions(self, force=False):
        if not _PYCAW_AVAILABLE:
            return []
        now = time.monotonic()
        if force or self._cache is None or (now - self._cache_ts) > self._CACHE_TTL:
            try:
                self._cache    = AudioUtilities.GetAllSessions()
                self._cache_ts = now
            except Exception as e:
                log.warning(f'Failed to enumerate audio sessions: {e}')
                self._cache = []
        return self._cache

    def adjust_volume(self, app_name, increase=True):
        if not app_name:
            return None
        for session in self._sessions():
            if session.Process and session.Process.name() == app_name:
                try:
                    vol = session.SimpleAudioVolume
                    new_vol = min(1.0, vol.GetMasterVolume() + self._STEP) if increase \
                              else max(0.0, vol.GetMasterVolume() - self._STEP)
                    vol.SetMasterVolume(new_vol, None)
                    return round(new_vol * 100)
                except Exception as e:
                    log.debug(f'adjust_volume failed for {app_name}: {e}')
        for session in self._sessions(force=True):
            if session.Process and session.Process.name() == app_name:
                try:
                    vol = session.SimpleAudioVolume
                    new_vol = min(1.0, vol.GetMasterVolume() + self._STEP) if increase \
                              else max(0.0, vol.GetMasterVolume() - self._STEP)
                    vol.SetMasterVolume(new_vol, None)
                    return round(new_vol * 100)
                except Exception as e:
                    log.debug(f'adjust_volume retry failed for {app_name}: {e}')
        return None

    def get_volume(self, app_name):
        if not app_name:
            return None
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        return round(session.SimpleAudioVolume.GetMasterVolume() * 100)
                    except Exception as e:
                        log.debug(f'get_volume failed for {app_name}: {e}')
            break
        return None

    def get_mute(self, app_name):
        if not app_name:
            return False
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        return bool(session.SimpleAudioVolume.GetMute())
                    except Exception as e:
                        log.debug(f'get_mute failed for {app_name}: {e}')
            break
        return False

    def toggle_mute(self, app_name):
        if not app_name:
            return None
        for sessions in (self._sessions(), self._sessions(force=True)):
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    try:
                        vol       = session.SimpleAudioVolume
                        new_state = not vol.GetMute()
                        vol.SetMute(new_state, None)
                        return new_state
                    except Exception as e:
                        log.debug(f'toggle_mute failed for {app_name}: {e}')
            break
        return None

    def get_available_processes(self):
        names = []
        for s in self._sessions(force=True):
            if s.Process:
                try:
                    names.append(s.Process.name())
                except Exception as e:
                    log.debug(f'Could not read process name: {e}')
        return sorted(set(names))

    # ── master output volume ───────────────────────────────────────────────────

    def _master_endpoint(self):
        if not _PYCAW_AVAILABLE:
            return None
        try:
            device    = AudioUtilities.GetSpeakers()
            dev       = getattr(device, '_dev', device)
            interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            log.warning(f'Cannot get master endpoint: {e}')
            return None

    def adjust_master_volume(self, increase=True):
        vol = self._master_endpoint()
        if vol is None:
            return None
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_vol = min(1.0, current + self._STEP) if increase else max(0.0, current - self._STEP)
            vol.SetMasterVolumeLevelScalar(new_vol, None)
            return round(new_vol * 100)
        except Exception as e:
            log.warning(f'adjust_master_volume failed: {e}')
            return None

    def get_master_volume(self):
        vol = self._master_endpoint()
        if vol is None:
            return None
        try:
            return round(vol.GetMasterVolumeLevelScalar() * 100)
        except Exception as e:
            log.debug(f'get_master_volume failed: {e}')
            return None

    def toggle_master_mute(self):
        vol = self._master_endpoint()
        if vol is None:
            return None
        try:
            new_state = not vol.GetMute()
            vol.SetMute(new_state, None)
            return new_state
        except Exception as e:
            log.debug(f'toggle_master_mute failed: {e}')
            return None

    def get_master_mute(self):
        vol = self._master_endpoint()
        if vol is None:
            return False
        try:
            return bool(vol.GetMute())
        except Exception as e:
            log.debug(f'get_master_mute failed: {e}')
            return False

    # ── microphone / capture volume ────────────────────────────────────────────

    def _mic_endpoint(self):
        if not _PYCAW_AVAILABLE:
            return None
        try:
            # pycaw >= 0.4.3 exposes GetMicrophone(); >= 20230407 wraps result in AudioDevice
            device    = AudioUtilities.GetMicrophone()
            dev       = getattr(device, '_dev', device)
            interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except AttributeError:
            # Older pycaw — use COM directly
            return self._mic_endpoint_via_com()
        except Exception as e:
            log.debug(f'Cannot get mic endpoint: {e}')
            return None

    def _mic_endpoint_via_com(self):
        try:
            import comtypes
            CLSID = comtypes.GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
            IID   = comtypes.GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')

            class IMMDeviceEnumerator(comtypes.IUnknown):
                _iid_    = IID
                _methods_ = [
                    comtypes.STDMETHOD(comtypes.HRESULT, 'EnumAudioEndpoints'),
                    comtypes.STDMETHOD(comtypes.HRESULT, 'GetDefaultAudioEndpoint',
                        [comtypes.c_uint, comtypes.c_uint,
                         comtypes.POINTER(comtypes.IUnknown)]),
                ]

            enumerator = comtypes.CoCreateInstance(CLSID, IMMDeviceEnumerator,
                                                   comtypes.CLSCTX_INPROC_SERVER)
            device    = enumerator.GetDefaultAudioEndpoint(1, 0)   # eCapture, eConsole
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            log.warning(f'COM mic enumeration failed: {e}')
            return None

    def adjust_mic_volume(self, increase=True):
        vol = self._mic_endpoint()
        if vol is None:
            return None
        try:
            current = vol.GetMasterVolumeLevelScalar()
            new_vol = min(1.0, current + self._STEP) if increase else max(0.0, current - self._STEP)
            vol.SetMasterVolumeLevelScalar(new_vol, None)
            return round(new_vol * 100)
        except Exception as e:
            log.debug(f'adjust_mic_volume failed: {e}')
            return None

    def get_mic_volume(self):
        vol = self._mic_endpoint()
        if vol is None:
            return None
        try:
            return round(vol.GetMasterVolumeLevelScalar() * 100)
        except Exception as e:
            log.debug(f'get_mic_volume failed: {e}')
            return None

    def toggle_mic_mute(self):
        vol = self._mic_endpoint()
        if vol is None:
            return None
        try:
            new_state = not vol.GetMute()
            vol.SetMute(new_state, None)
            return new_state
        except Exception as e:
            log.debug(f'toggle_mic_mute failed: {e}')
            return None

    def get_mic_mute(self):
        vol = self._mic_endpoint()
        if vol is None:
            return False
        try:
            return bool(vol.GetMute())
        except Exception as e:
            log.debug(f'get_mic_mute failed: {e}')
            return False

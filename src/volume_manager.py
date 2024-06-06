from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

class VolumeManager:
    def __init__(self):
        self.devices = AudioUtilities.GetAllSessions()

    def adjust_volume(self, app_name, increase=True):
        for session in self.devices:
            if session.Process and session.Process.name() == app_name:
                volume = session.SimpleAudioVolume
                current_volume = volume.GetMasterVolume()
                new_volume = min(current_volume + 0.1, 1.0) if increase else max(current_volume - 0.1, 0.0)
                volume.SetMasterVolume(new_volume, None)
                return new_volume * 100  # Return percentage

    def get_available_processes(self):
        processes = []
        for session in self.devices:
            if session.Process:
                processes.append(session.Process.name())
        return processes

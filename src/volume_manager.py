from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

class VolumeManager:
    def adjust_volume(self, application_name, increase=True):
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name() == application_name:
                volume = session.SimpleAudioVolume
                current_volume = volume.GetMasterVolume()
                if increase:
                    new_volume = min(current_volume + 0.1, 1.0)
                else:
                    new_volume = max(current_volume - 0.1, 0.0)
                volume.SetMasterVolume(new_volume, None)
                return new_volume * 100  # Return volume as percentage
        return None

    def get_available_processes(self):
        sessions = AudioUtilities.GetAllSessions()
        processes = set()
        for session in sessions:
            if session.Process:
                processes.add(session.Process.name())
        return list(processes)

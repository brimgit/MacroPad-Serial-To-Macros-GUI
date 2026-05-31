import ctypes
import ctypes.wintypes
from PyQt5.QtCore import QThread, pyqtSignal

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


class ForegroundWatcher(QThread):
    """Background thread that emits the foreground process name whenever it changes."""
    app_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._last = ''

    def run(self):
        self._running = True
        user32 = ctypes.windll.user32
        while self._running:
            hwnd = user32.GetForegroundWindow()
            name = ''
            if hwnd and _PSUTIL:
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    name = psutil.Process(pid.value).name()
                except Exception:
                    name = ''
            if name != self._last:
                self._last = name
                self.app_changed.emit(name)
            self.msleep(500)

    def stop(self):
        self._running = False
        self.wait(1500)

import ctypes
import time
import threading
import logging

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

log = logging.getLogger(__name__)


class ForegroundWatcher:
    """Polls the foreground window every 500 ms and calls on_change(app_name) when it changes."""

    _POLL_S = 0.5

    def __init__(self, on_change):
        self._on_change = on_change
        self._current   = None
        self._running   = False
        self._thread    = None

    def start(self):
        if not _PSUTIL:
            log.warning('psutil unavailable — auto profile switching disabled')
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _foreground_app(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return None
            return psutil.Process(pid.value).name()
        except Exception:
            return None

    def _run(self):
        while self._running:
            app = self._foreground_app()
            if app and app != self._current:
                self._current = app
                try:
                    self._on_change(app)
                except Exception as e:
                    log.debug(f'ForegroundWatcher callback error: {e}')
            time.sleep(self._POLL_S)

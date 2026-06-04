import serial
import threading
import time
import logging
from serial.tools import list_ports as sp_list_ports
from volume_manager import VolumeManager

log = logging.getLogger(__name__)

_DEVICE_ID  = 'MACROPAD_OK'
_PING_CMD   = b'PING\n'


def list_ports():
    return [p.device for p in sp_list_ports.comports()]


def find_macropad_port(baud_rate=115200):
    """Scan all serial ports and return the one that identifies as our MacroPad."""
    for info in sp_list_ports.comports():
        port = info.device
        try:
            ser = serial.Serial()
            ser.port     = port
            ser.baudrate = baud_rate
            ser.dtr      = False   # don't reset a running device during scan
            ser.timeout  = 0.5
            ser.open()
            ser.reset_input_buffer()
            ser.write(_PING_CMD)
            ser.flush()
            deadline = time.monotonic() + 1.0
            found = False
            while time.monotonic() < deadline:
                line = ser.readline()
                if line and line.decode('utf-8', errors='replace').strip() == _DEVICE_ID:
                    found = True
                    break
            ser.close()
            if found:
                log.info(f'MacroPad auto-discovered on {port}')
                return port
        except Exception:
            pass
    return None


class SerialManager:
    _RECONNECT_DELAY = 3.0

    def __init__(self, data_callback, port='COM6', baud_rate=115200,
                 connected_callback=None):
        self.data_callback      = data_callback
        self.connected_callback = connected_callback
        self.port               = port
        self.baud_rate          = baud_rate
        self.serial_port        = None
        self.running            = False
        self.thread             = None
        self.volume_manager     = VolumeManager()
        self._connected         = False
        self._stop_event        = threading.Event()
        self.start()

    @property
    def is_connected(self):
        return self._connected

    def start(self):
        self.stop()
        self._stop_event.clear()
        self.running = True
        self.thread  = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=4)
            self.thread = None
        self._close_port()

    def _close_port(self):
        self._connected = False
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None

    def _verify_device(self):
        """Send PING and wait for MACROPAD_OK. Accounts for ESP32 boot time (~2.5s)."""
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(_PING_CMD)
            self.serial_port.flush()
            deadline = time.monotonic() + 4.0   # covers full startup sequence
            while time.monotonic() < deadline and self.running:
                line = self.serial_port.readline()
                if line and line.decode('utf-8', errors='replace').strip() == _DEVICE_ID:
                    return True
            return False
        except Exception:
            return False

    def _run(self):
        _logged_error = None
        _verified     = False   # only verify on the first connection this session
        while self.running:
            if not self._connected:
                try:
                    self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=1)

                    if not _verified:
                        if not self._verify_device():
                            log.warning(f'{self.port} did not identify as MacroPad — scanning all ports...')
                            self._close_port()
                            found = find_macropad_port(self.baud_rate)
                            if found:
                                self.port = found
                            else:
                                log.warning('MacroPad not found on any port')
                                self._stop_event.wait(self._RECONNECT_DELAY)
                            continue
                        _verified = True

                    self._connected = True
                    _logged_error   = None
                    log.info(f'MacroPad identified on {self.port} @ {self.baud_rate}')
                    if self.connected_callback:
                        self.connected_callback(True)
                except serial.SerialException as e:
                    err = str(e)
                    if err != _logged_error:
                        log.warning(f'Cannot open {self.port}: {e}')
                        _logged_error = err
                    self._stop_event.wait(self._RECONNECT_DELAY)
                    continue

            try:
                line = self.serial_port.readline()
                if line and self.running:
                    try:
                        decoded = line.decode('utf-8', errors='replace').strip()
                        if decoded:
                            self.data_callback(decoded)
                    except Exception as e:
                        log.debug(f'Error dispatching serial data: {e}')
            except serial.SerialException as e:
                log.warning(f'Serial read error: {e}')
                self._close_port()
                if self.connected_callback:
                    self.connected_callback(False)
                self._stop_event.wait(self._RECONNECT_DELAY)

    def update_settings(self, port, baud_rate):
        self.port      = port
        self.baud_rate = baud_rate
        self.start()

    def send_data(self, data):
        if self.serial_port and self.serial_port.is_open:
            try:
                if isinstance(data, str):
                    data = data.encode('utf-8')
                self.serial_port.write(data)
                self.serial_port.flush()
                log.debug(f'TX: {data.strip()}')
            except serial.SerialException as e:
                log.warning(f'Send error: {e}')
                self._close_port()

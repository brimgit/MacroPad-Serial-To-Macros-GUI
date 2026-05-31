import serial
import threading
import time
import logging
from serial.tools import list_ports as sp_list_ports
from volume_manager import VolumeManager

logging.basicConfig(level=logging.INFO)


def list_ports():
    return [p.device for p in sp_list_ports.comports()]


class SerialManager:
    _RECONNECT_DELAY = 3.0

    def __init__(self, data_callback, port='COM20', baud_rate=115200,
                 connected_callback=None):
        self.data_callback = data_callback
        self.connected_callback = connected_callback
        self.port = port
        self.baud_rate = baud_rate
        self.serial_port = None
        self.running = False
        self.thread = None
        self.volume_manager = VolumeManager()
        self._connected = False
        self._stop_event = threading.Event()
        self.start()

    @property
    def is_connected(self):
        return self._connected

    def start(self):
        self.stop()
        self._stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()  # wake up any sleeping wait() immediately
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

    def _run(self):
        while self.running:
            if not self._connected:
                try:
                    self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=1)
                    self._connected = True
                    logging.info(f'Connected to {self.port} @ {self.baud_rate}')
                    if self.connected_callback:
                        self.connected_callback(True)
                except serial.SerialException as e:
                    logging.warning(f'Cannot open {self.port}: {e}')
                    self._stop_event.wait(self._RECONNECT_DELAY)
                    continue

            try:
                line = self.serial_port.readline()
                if line and self.running:
                    try:
                        decoded = line.decode('utf-8', errors='replace').strip()
                        if decoded:
                            self.data_callback(decoded)
                    except Exception:
                        pass
            except serial.SerialException as e:
                logging.warning(f'Serial read error: {e}')
                self._close_port()
                if self.connected_callback:
                    self.connected_callback(False)
                self._stop_event.wait(self._RECONNECT_DELAY)

    def update_settings(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.start()

    def send_data(self, data):
        if self.serial_port and self.serial_port.is_open:
            try:
                if isinstance(data, str):
                    data = data.encode('utf-8')
                self.serial_port.write(data)
                self.serial_port.flush()
                logging.info(f'TX: {data.strip()}')
            except serial.SerialException as e:
                logging.warning(f'Send error: {e}')
                self._close_port()

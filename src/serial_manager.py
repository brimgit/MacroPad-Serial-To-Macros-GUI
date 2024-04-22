import serial
import threading
import logging

logging.basicConfig(level=logging.INFO)
class SerialManager:
    def __init__(self, data_callback, port='COM20', baud_rate=115200):
        self.data_callback = data_callback
        self.port = port
        self.baud_rate = baud_rate
        self.serial_port = None
        self.running = False
        self.thread = None
        self.start()  # Start the serial connection

    def update_settings(self, port, baud_rate):
        if self.serial_port:
            self.serial_port.close()
        self.port = port
        self.baud_rate = baud_rate
        self.start()

    def start(self):
        try:
            self.serial_port = serial.Serial(self.port, int(self.baud_rate), timeout=1)
            self.running = True
            self.read_from_port()
        except serial.SerialException as e:
            logging.error(f"Failed to open serial port {self.port} at {self.baud_rate}: {e}")

    def read_from_port(self):
        if not self.thread:
            self.thread = threading.Thread(target=self._read_from_port, daemon=True)
            self.thread.start()

    def _read_from_port(self):
        while self.running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.readline()
                if data:
                    self.data_callback(data)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.serial_port:
            self.serial_port.close()

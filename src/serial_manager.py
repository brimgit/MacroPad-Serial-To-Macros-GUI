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
        self.start()

    def start(self):
        self.stop()  # Ensure any existing connection and thread are stopped before starting new
        try:
            self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self._read_from_port, daemon=True)
            self.thread.start()
        except serial.SerialException as e:
            logging.error(f"Failed to open serial port {self.port} at {self.baud_rate}: {e}")

    def stop(self):
        if self.running:
            self.running = False
            if self.thread is not None:
                self.thread.join()
            if self.serial_port is not None:
                self.serial_port.close()

    def _read_from_port(self):
        while self.running:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.readline()
                    if data:
                        self.data_callback(data)
            except serial.SerialException as e:
                logging.error(f"Error reading from serial port: {e}")
                break  # Exit the loop if we encounter an error

    def update_settings(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.start()  # Restart the connection with new settings
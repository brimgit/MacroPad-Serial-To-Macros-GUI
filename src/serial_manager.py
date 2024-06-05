import serial
import threading
import logging
from serial.tools import list_ports as sp_list_ports

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

logging.basicConfig(level=logging.INFO)

def list_ports():
    ports = sp_list_ports.comports()
    return [port.device for port in ports]

def adjust_volume(application_name, increase=True):
    print(f"Adjusting volume for {application_name}, increase: {increase}")
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() == application_name:
            volume = session.SimpleAudioVolume
            current_volume = volume.GetMasterVolume()
            print(f"Current volume of {application_name}: {current_volume}")
            if increase:
                new_volume = min(current_volume + 0.1, 1.0)
            else:
                new_volume = max(current_volume - 0.1, 0.0)
            volume.SetMasterVolume(new_volume, None)
            print(f"New volume of {application_name}: {new_volume}")
            return new_volume * 100
    else:
        print(f"No active session found for {application_name}")
        return None

def get_volume_percentage(application_name):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() == application_name:
            volume = session.SimpleAudioVolume
            current_volume = volume.GetMasterVolume()
            return current_volume * 100
    return None

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
            self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=0.01)
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
                    print(f"Raw data read: {data}")  # Debug print to check raw data
                    if data:
                        self.data_callback(data)
            except serial.SerialException as e:
                logging.error(f"Error reading from serial port: {e}")
                break  # Exit the loop if we encounter an error

    def update_settings(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.start()  # Restart the connection with new settings

    def send_data(self, data):
        """Send data to the serial port."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data)
                logging.info(f"Sent data: {data}")
            except serial.SerialException as e:
                logging.error(f"Error sending data: {e}")
        else:
            logging.warning("Serial port is not open.")

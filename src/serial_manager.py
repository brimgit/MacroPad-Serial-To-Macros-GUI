import serial
import threading

class SerialManager:
    def __init__(self, data_callback):
        self.data_callback = data_callback
        self.serial_port = serial.Serial('COM20', 115200, timeout=1)  # Adjust the COM port and baud rate as necessary
        self.running = True  # Control flag
        
    def start(self):
        self.thread = threading.Thread(target=self.read_from_port, daemon=True)
        self.thread.start()
        
    def read_from_port(self):
        while self.running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.readline()
                if data:
                    self.data_callback(data)
            pass
    def stop(self):
        self.running = False  # Signal the thread to stop
        self.thread.join()  # Wait for the thread to finish
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QLineEdit, QComboBox)
from serial_manager import list_ports  # Import the list_ports function

class ArduinoUploader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.serial_manager = None

    def initUI(self):
        layout = QVBoxLayout()

        self.project_file_label = QLabel("No project file selected", self)
        layout.addWidget(self.project_file_label)

        self.select_file_button = QPushButton("Select .ino File", self)
        self.select_file_button.clicked.connect(self.select_file)
        layout.addWidget(self.select_file_button)

        self.arduino_path_label = QLabel("Arduino CLI Path:", self)
        layout.addWidget(self.arduino_path_label)

        self.arduino_path_input = QLineEdit(self)
        self.arduino_path_input.setText("C:\\Program Files\\Arduino CLI\\arduino-cli.exe")  # Default path
        layout.addWidget(self.arduino_path_input)

        self.action_label = QLabel("Action:", self)
        layout.addWidget(self.action_label)

        self.action_dropdown = QComboBox(self)
        self.action_dropdown.addItems(["upload", "verify"])
        layout.addWidget(self.action_dropdown)

        self.board_label = QLabel("Board:", self)
        layout.addWidget(self.board_label)

        self.board_dropdown = QComboBox(self)
        self.board_dropdown.addItems([
            "esp32:esp32:esp32", 
            "esp32:esp32:esp32wrover", 
            "esp32:esp32:esp32da"
        ])
        layout.addWidget(self.board_dropdown)

        self.port_label = QLabel("Port:", self)
        layout.addWidget(self.port_label)

        self.port_dropdown = QComboBox(self)
        self.update_ports()
        layout.addWidget(self.port_dropdown)

        self.refresh_ports_button = QPushButton("Refresh Ports", self)
        self.refresh_ports_button.clicked.connect(self.update_ports)
        layout.addWidget(self.refresh_ports_button)

        self.upload_button = QPushButton("Execute", self)
        self.upload_button.clicked.connect(self.execute_ino)
        layout.addWidget(self.upload_button)

        self.back_button = QPushButton("Back", self)
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.setWindowTitle("ESP32 Arduino Uploader")

    def select_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Arduino .ino file", "", "Arduino Files (*.ino)", options=options)
        if file_name:
            self.project_file_label.setText(file_name)
            self.project_file = file_name

    def update_ports(self):
        available_ports = list_ports()  # Use the imported list_ports function
        self.port_dropdown.clear()
        self.port_dropdown.addItems(available_ports)

    def execute_ino(self):
        project_file = self.project_file_label.text()
        if not project_file:
            QMessageBox.critical(self, "Error", "Please select a project file")
            return

        arduino_prog = self.arduino_path_input.text()
        if not arduino_prog:
            QMessageBox.critical(self, "Error", "Please provide the Arduino CLI path")
            return

        action = self.action_dropdown.currentText()
        board = self.board_dropdown.currentText()
        port = self.port_dropdown.currentText()

        available_ports = list_ports()
        if port not in available_ports:
            QMessageBox.critical(self, "Error", f"Selected port {port} does not exist.")
            return

        # Close the serial port before executing the command
        if self.serial_manager and self.serial_manager.running:
            self.serial_manager.stop()

        compile_command = f'"{arduino_prog}" compile --fqbn {board} "{project_file}"'
        upload_command = f'"{arduino_prog}" {action} --fqbn {board} --port {port} "{project_file}"'

        result = subprocess.run(compile_command, shell=True)
        if result.returncode != 0:
            QMessageBox.critical(self, "Error", "Compilation failed")
            return

        result = subprocess.run(upload_command, shell=True)
        if result.returncode != 0:
            QMessageBox.critical(self, "Error", f"Execution failed: {result.stderr}")
            return

        QMessageBox.information(self, "Success", f"{action.capitalize()} successful!")

        # Reopen the serial port after executing the command
        if self.serial_manager:
            self.serial_manager.start()

    def set_serial_manager(self, serial_manager):
        self.serial_manager = serial_manager

    def go_back(self):
        self.parent().setCurrentIndex(0)  # Go back to the main widget

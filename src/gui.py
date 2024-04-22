from PyQt5.QtWidgets import (QMainWindow, QPushButton, QVBoxLayout, QWidget,
                             QLabel, QLineEdit, QTextEdit, QListWidget, QHBoxLayout,
                             QMessageBox, QDialog, QFormLayout, QDialogButtonBox)
from PyQt5.QtCore import pyqtSignal, QObject
import pyautogui
import logging
from src.macro_manager import set_macro, save_macros, reload_macros, delete_macro
from src.serial_manager import SerialManager
class GuiUpdater(QObject):
    updateTextSignal = pyqtSignal(str)
    executeMacroSignal = pyqtSignal(str)

class SettingsDialog(QDialog):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Settings')

        # Layout and form
        layout = QFormLayout(self)

        # Serial port settings
        self.portInput = QLineEdit(self)
        self.portInput.setPlaceholderText('COM1')
        layout.addRow('Serial Port:', self.portInput)

        self.baudRateInput = QLineEdit(self)
        self.baudRateInput.setPlaceholderText('115200')
        layout.addRow('Baud Rate:', self.baudRateInput)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def getSettings(self):
        return self.portInput.text(), self.baudRateInput.text()

class MacroPadApp(QMainWindow):
    
    def __init__(self):
        super().__init__()
        # Initialize SerialManager with a default port and baud rate
        self.serial_manager = SerialManager(self.handle_received_data, 'COM1', 115200)
        self.decodedVar = ""
        self.guiUpdater = GuiUpdater()
        self.guiUpdater.updateTextSignal.connect(self.updateReceivedDataDisplay)
        self.guiUpdater.executeMacroSignal.connect(self.execute_macro)
        self.MacroPadApp = reload_macros()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('MacroPad Serial Interface')
        self.setGeometry(100, 100, 800, 600)
        main_layout = QVBoxLayout()

        self.statusLabel = QLabel("Ready", self)
        main_layout.addWidget(self.statusLabel)

        self.receivedDataDisplay = QTextEdit(self)
        self.receivedDataDisplay.setPlaceholderText("Received data will be shown here...")
        self.receivedDataDisplay.setReadOnly(True)
        main_layout.addWidget(self.receivedDataDisplay)

        self.macroList = QListWidget(self)
        self.update_macro_list()
        main_layout.addWidget(self.macroList)

        control_layout = QHBoxLayout()
        self.macroInput = QLineEdit(self)
        self.macroInput.setPlaceholderText("Enter a key or combo...")
        control_layout.addWidget(self.macroInput)

        self.setMacroButton = QPushButton("Set/Edit Macro", self)
        self.setMacroButton.clicked.connect(self.set_or_edit_macro)
        control_layout.addWidget(self.setMacroButton)

        self.refreshMacrosButton = QPushButton("Refresh Macros", self)
        self.refreshMacrosButton.clicked.connect(self.refresh_macros)
        control_layout.addWidget(self.refreshMacrosButton)

        self.saveMacrosButton = QPushButton("Save Macros", self)
        self.saveMacrosButton.clicked.connect(self.save_macros)
        control_layout.addWidget(self.saveMacrosButton)

        self.removeMacroButton = QPushButton("Remove Selected Macro", self)
        self.removeMacroButton.clicked.connect(self.remove_selected_macro)
        control_layout.addWidget(self.removeMacroButton)

        main_layout.addLayout(control_layout)
        centralWidget = QWidget(self)
        centralWidget.setLayout(main_layout)
        self.setCentralWidget(centralWidget)
        
        self.settingsButton = QPushButton("Settings", self)
        self.settingsButton.clicked.connect(self.open_settings)
        control_layout.addWidget(self.settingsButton)
    
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            port, baud_rate = dialog.getSettings()
            self.serial_manager.update_settings(port, baud_rate)
            self.statusLabel.setText(f"Serial port set to {port} at {baud_rate} baud")
               
    def set_or_edit_macro(self):
        command = self.decodedVar
        macro_action = self.macroInput.text()
        if not macro_action:
            QMessageBox.warning(self, "Invalid Macro", "Macro action cannot be empty.")
            return
        set_macro(command, macro_action)
        self.refresh_macros()
        self.statusLabel.setText(f"Macro set for {command}: {macro_action}")

    def refresh_macros(self):
        self.MacroPadApp = reload_macros()
        self.update_macro_list()
        self.statusLabel.setText("Macros refreshed successfully.")

    def save_macros(self):
        save_macros()
        self.statusLabel.setText("Macros saved successfully.")

    def remove_selected_macro(self):
        item = self.macroList.currentItem()
        if item:
            # Here we need to handle the text properly to capture everything before the action
            # Assuming the format is "command: action"
            command_text = item.text()
            command = command_text[:command_text.rfind(':')].strip()  # This strips after the last colon
            try:
                delete_macro(command)
                self.refresh_macros()
                self.statusLabel.setText(f"Removed macro for {command}")
            except KeyError as e:
                QMessageBox.warning(self, "Deletion Error", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Deletion Error", "Failed to delete macro: " + str(e))
        else:
            QMessageBox.warning(self, "Select Macro", "Please select a macro to remove.")
            
    def update_macro_list(self):
        self.macroList.clear()
        for command, action in self.MacroPadApp.items():
            self.macroList.addItem(f"{command}: {action}")  # Ensure consistent formatting

    def handle_received_data(self, data):
        try:
            decoded_data = data.decode('utf-8').strip()
            self.guiUpdater.updateTextSignal.emit(decoded_data)
            self.decodedVar = decoded_data
        except UnicodeDecodeError:
            QMessageBox.warning(self, "Decode Error", "Received non-UTF-8 data")

    def execute_macro(self, command):
        macro_action = self.MacroPadApp.get(command)
        if macro_action:
            pyautogui.write(macro_action)
            self.statusLabel.setText(f"Executed macro for {command}")
        else:
            self.statusLabel.setText("No macro assigned for this command")

    def updateReceivedDataDisplay(self, text):
        self.receivedDataDisplay.append(text)

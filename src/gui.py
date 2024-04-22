from PyQt5.QtWidgets import (QMainWindow, QPushButton, QVBoxLayout, QWidget,
                             QLabel, QLineEdit, QTextEdit, QListWidget, QHBoxLayout,
                             QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QComboBox)
from PyQt5.QtCore import pyqtSignal, QObject
import pyautogui, keyboard
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

        self.actionTypeSelect = QComboBox(self)
        self.actionTypeSelect.addItems(["Keyboard Key", "Media Control", "Function Key", "Modifier Key"])
        self.actionTypeSelect.currentIndexChanged.connect(self.updateActionOptions)
        control_layout.addWidget(self.actionTypeSelect)
        
        self.actionSelect = QComboBox(self)
        control_layout.addWidget(self.actionSelect)
        self.updateActionOptions(0)  # Initialize the action options

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            port, baud_rate = dialog.getSettings()
            self.serial_manager.update_settings(port, baud_rate)
            self.statusLabel.setText(f"Serial port set to {port} at {baud_rate} baud")
               
    def set_or_edit_macro(self):
        command = self.decodedVar
        action_type = self.actionTypeSelect.currentText()
        macro_action = self.actionSelect.currentText()  # Updated to get the action from the dropdown
        if not macro_action:
            QMessageBox.warning(self, "Invalid Macro", "Macro action cannot be empty.")
            return
        set_macro(command, action_type, macro_action)
        self.refresh_macros()
        self.statusLabel.setText(f"Macro set for {command}: {action_type} - {macro_action}")

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
            full_text = item.text()
            # It's important to extract the full key exactly as it's stored in the macros dictionary.
            # Assuming your list items are in the format "1: Pressed: Media Control - play/pause",
            # you would split by ':' and take the first two parts to reconstruct "1: Pressed".
            command_key = ':'.join(full_text.split(':')[:2]).strip()

            try:
                if command_key in self.MacroPadApp:
                    delete_macro(command_key)
                    self.refresh_macros()
                    self.statusLabel.setText(f"Removed macro for {command_key}")
                else:
                    QMessageBox.warning(self, "Error", f"No macro found for command '{command_key}'")
            except KeyError as e:
                QMessageBox.warning(self, "Deletion Error", str(e))
        else:
            QMessageBox.warning(self, "Select Macro", "Please select a macro to remove.")

    def updateActionOptions(self, index):
        self.actionSelect.clear()

        if index == 0:  # Keyboard Key
            # List more common keys if needed
            keyboard_keys = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 
                            'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                            'enter', 'esc', 'backspace', 'tab', 'space', 'minus', 
                            'equal', 'leftbrace', 'rightbrace', 'semicolon', 'quote', 
                            'tilde', 'comma', 'period', 'slash', 'backslash']
            self.actionSelect.addItems(keyboard_keys)
        elif index == 1:  # Media Control
            self.actionSelect.addItems(['play/pause', 'next track', 'previous track', 'volume up', 'volume down'])
        elif index == 2:  # Function Key
            function_keys = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12']
            self.actionSelect.addItems(function_keys)
        elif index == 3:  # Modifier Key
            self.actionSelect.addItems(['alt', 'ctrl', 'shift', 'win'])


                    
    def update_macro_list(self):
        self.macroList.clear()
        for command, details in self.MacroPadApp.items():
            list_item = f"{command}: {details['type']} - {details['action']}"
            self.macroList.addItem(list_item)



    def handle_received_data(self, data):
        try:
            decoded_data = data.decode('utf-8').strip()
            print(f"Received data: {decoded_data}")  # Debug print
            self.guiUpdater.updateTextSignal.emit(decoded_data)
            self.decodedVar = decoded_data
            self.execute_macro(decoded_data)
        except UnicodeDecodeError:
            print("Received non-UTF-8 data")
            
    def execute_macro(self, command):
        macro = self.MacroPadApp.get(command)
        if macro:
            action_type = macro["type"]
            macro_action = macro["action"]
            if action_type == "Keyboard Key":
                pyautogui.press(macro_action)
            elif action_type == "Media Control":
                # keyboard can simulate media keys, ensure you run your script with appropriate privileges
                if macro_action == "play/pause":
                    keyboard.press_and_release('play/pause')
                elif macro_action == "next track":
                    keyboard.press_and_release('next track')
                elif macro_action == "previous track":
                    keyboard.press_and_release('previous track')
                elif macro_action == "volume up":
                    keyboard.press_and_release('volume up')
                elif macro_action == "volume down":
                    keyboard.press_and_release('volume down')
                # Add more elif blocks for other media controls as needed.
            elif action_type == "Function Key":
                pyautogui.press(macro_action)
            elif action_type == "Modifier Key":
                pyautogui.keyDown(macro_action)
                pyautogui.keyUp(macro_action)
            self.statusLabel.setText(f"Executed {action_type} macro for {command}: {macro_action}")
        else:
            self.statusLabel.setText("No macro assigned for this command")


    def updateReceivedDataDisplay(self, text):
        self.receivedDataDisplay.append(text)

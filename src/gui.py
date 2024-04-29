import sys
import os
import json
import logging
import keyboard
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel,
                             QTextEdit, QListWidget, QPushButton, QMessageBox,
                             QDialog, QFormLayout, QDialogButtonBox, QComboBox,
                             QDockWidget, QLineEdit, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import pyqtSignal, QObject, Qt
from serial.tools import list_ports

from macro_manager import set_macro, save_macros, reload_macros, delete_macro
from serial_manager import SerialManager, adjust_volume
from utils import resource_path

# Check if the platform is Windows
is_windows = sys.platform.startswith('win')

# Create 'logs' directory if it does not exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Set up logging to file
logging.basicConfig(
    level=logging.ERROR,  # Log error and above levels
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='logs/logs.txt',  # Log file path
    filemode='a'  # Append mode
)

class GuiUpdater(QObject):
    updateTextSignal = pyqtSignal(str)
    executeMacroSignal = pyqtSignal(str)

from PyQt5.QtWidgets import QDialog, QFormLayout, QComboBox, QPushButton, QDialogButtonBox
from PyQt5.QtCore import Qt
from serial.tools import list_ports

class SettingsDialog(QDialog):
    def __init__(self, parent=None, default_port='COM20', default_baud='115200'):
        super().__init__(parent)
        self.setWindowTitle('Settings')
        self.layout = QFormLayout(self)
        self.layout.setSpacing(10)  # Add some space between form rows for better clarity

        # COM Port selection
        self.portInput = QComboBox(self)
        self.populate_ports(default_port)
        self.layout.addRow("Serial Port:", self.portInput)

        # Baud Rate input
        self.baudRateInput = QLineEdit(self)
        self.baudRateInput.setPlaceholderText('115200')
        self.baudRateInput.setText(default_baud)
        self.layout.addRow('Baud Rate:', self.baudRateInput)

        # Refresh button
        self.refreshButton = QPushButton("Refresh Ports", self)
        self.refreshButton.clicked.connect(self.populate_ports)
        self.refreshButton.setToolTip("Click to refresh the list of available COM ports.")
        self.layout.addRow(self.refreshButton)

        # Buttons for OK and Cancel
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)

    def populate_ports(self, default_port=None):
        self.portInput.clear()
        ports = list_ports.comports()
        port_list = [f"{port.device} - {port.description}" for port in ports]
        self.portInput.addItems(port_list)
        if default_port:
            default_index = next((i for i, item in enumerate(port_list) if item.startswith(default_port)), -1)
            if default_index != -1:
                self.portInput.setCurrentIndex(default_index)

    def getSettings(self):
        selected_text = self.portInput.currentText()
        port = selected_text.split(' - ')[0]  # Only retrieve the COM part
        baud_rate = self.baudRateInput.text()
        return port, baud_rate

def ensure_data_directory_exists():
    data_dir = resource_path('Data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

def save_settings(port, baud_rate):
    ensure_data_directory_exists()
    settings_path = resource_path('Data/settings_serial.json')
    settings = {'port': port, 'baud_rate': baud_rate}
    with open(settings_path, 'w') as f:
        json.dump(settings, f)

def load_settings():
    settings_path = resource_path('Data/settings_serial.json')
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        # Use list_ports.comports() to list available COM ports
        available_ports = [port.device for port in list_ports.comports()]
        if settings['port'] in available_ports:
            return settings['port'], settings['baud_rate']
        else:
            return None, None  # Port no longer available
    except FileNotFoundError:
        return None, None  # No settings file found
class MacroPadApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.serial_manager = None
        self.decodedVar = ""
        self.guiUpdater = GuiUpdater()
        self.guiUpdater.updateTextSignal.connect(self.updateReceivedDataDisplay)
        self.guiUpdater.executeMacroSignal.connect(self.execute_macro)

        self.encoder_app_map = {
            1: 'Discord.exe',  # Example: Encoder 1 controls Discord
            2: 'Spotify.exe', # Encoder 2 controls Spotify
            3: 'vlc.exe',     # Encoder 3 controls VLC Player
            4: 'firefox.exe'  # Encoder 4 controls Firefox
        }
        
        self.initUI()
        self.showSettingsDialog()
        self.load_macros_and_update_list()
         
    def initUI(self):
        self.setWindowTitle('MacroPad Serial Interface')
        self.setGeometry(100, 100, 800, 600)
        self.createSidebar()
        self.setWindowIcon(QIcon(resource_path('Assets/Images/icon.ico')))
        
        # System Tray Icon
        self.tray_icon = QSystemTrayIcon(QIcon(resource_path('Assets/Images/icon.png')), self)
        self.tray_icon.activated.connect(self.toggle_window)
        self.create_tray_menu()

        main_layout = QVBoxLayout()
        self.statusLabel = QLabel("Ready")
        main_layout.addWidget(self.statusLabel)

        self.receivedDataDisplay = QTextEdit()
        self.receivedDataDisplay.setReadOnly(True)
        main_layout.addWidget(self.receivedDataDisplay)

        self.macroList = QListWidget()
        main_layout.addWidget(self.macroList)

        self.actionTypeSelect = QComboBox()
        self.actionTypeSelect.addItems(["Keyboard Key", "Media Control", "Function Key", "Modifier Key"])
        self.actionTypeSelect.currentIndexChanged.connect(self.updateActionOptions)
        main_layout.addWidget(self.actionTypeSelect)

        self.actionSelect = QComboBox()
        main_layout.addWidget(self.actionSelect)

        self.setMacroButton = QPushButton("Set/Edit Macro")
        self.setMacroButton.clicked.connect(self.set_or_edit_macro)
        main_layout.addWidget(self.setMacroButton)

        self.removeMacroButton = QPushButton("Remove Selected Macro")
        self.removeMacroButton.clicked.connect(self.remove_selected_macro)
        main_layout.addWidget(self.removeMacroButton)

        centralWidget = QWidget()
        centralWidget.setLayout(main_layout)
        self.setCentralWidget(centralWidget)
           
    def showSettingsDialog(self):
        port, baud_rate = load_settings()
        if port is None or baud_rate is None:
            dialog = SettingsDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                port, baud_rate = dialog.getSettings()
                save_settings(port, baud_rate)
            else:
                sys.exit(0)  # Exit if no settings are selected

        self.serial_manager = SerialManager(self.handle_received_data, port, baud_rate)
    


    def createSidebar(self):
        self.sidebar = QDockWidget("", self)
        self.sidebar.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.sidebar.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.sidebar.setTitleBarWidget(QWidget())  # Remove the title bar

        sidebar_contents = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_contents)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        self.sidebar.setWidget(sidebar_contents)
        self.sidebar.setMinimumWidth(300)  # Adjust this value as needed

        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path('Assets/Images/logo.png'))
        logo_label.setPixmap(logo_pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        sidebar_layout.addWidget(logo_label)

        settings_button = QPushButton('Settings')
        settings_button.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(settings_button)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar)

    def load_stylesheet(self):
        try:
            with open(resource_path('Data/style.css'), 'r') as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                print("Stylesheet loaded successfully.")
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")

    def load_macros_and_update_list(self):
        try:
            self.MacroPadApp = reload_macros()
            self.update_macro_list()
            self.statusLabel.setText("Macros loaded and updated successfully.")
        except Exception as e:
            self.statusLabel.setText("Failed to load or update macros.")
            print(f"Error loading macros: {e}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            try:
                port, baud_rate = dialog.getSettings()
                self.serial_manager.update_settings(port, baud_rate)
                self.statusLabel.setText(f"Serial port set to {port} at {baud_rate} baud")
            except Exception as e:
                self.statusLabel.setText("Failed to update settings.")
                print(f"Settings update error: {e}")

    def set_or_edit_macro(self):
        command = self.decodedVar.strip()  # Strip any leading/trailing whitespace
        action_type = self.actionTypeSelect.currentText()
        macro_action = self.actionSelect.currentText()

        # Check if the command is empty
        if not command:
            QMessageBox.warning(self, "Invalid Command", "No command detected. Please receive a valid command before setting a macro.")
            return

        # Check if the macro action is empty
        if not macro_action:
            QMessageBox.warning(self, "Invalid Macro", "Macro action cannot be empty.")
            return

        # Set macro, save macros, and refresh the list
        set_macro(command, action_type, macro_action)
        save_macros()  # This will save the current state of the macros to the file
        self.refresh_macros()  # Refresh the macro list to reflect the new changes

        self.statusLabel.setText(f"Macro set for {command}: {action_type} - {macro_action}")

    def refresh_macros(self):
        self.MacroPadApp = reload_macros()
        self.update_macro_list()
        self.statusLabel.setText("Macros refreshed successfully.")

    def save_macros(self):
        try:
            save_macros()
            self.statusLabel.setText("Macros saved successfully.")
        except Exception as e:
            self.statusLabel.setText("Failed to save macros.")
            print(f"Error saving macros: {e}")

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

        if index == 0:  # Keyboard Key (Alphabets, Numbers, and Common Keys)
            keyboard_keys = [
                'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                'backspace', 'tab', 'enter', 'space',
                'esc', 'capslock', 'numlock', 'scrolllock', 'printscreen', 'menu'
            ]
            self.actionSelect.addItems(keyboard_keys)

        elif index == 1:  # Media Control Keys
            media_controls = [
                'play/pause', 'stop_media', 'previous_track', 'next_track', 'volume_mute',
                'volume_up', 'volume_down'
            ]
            self.actionSelect.addItems(media_controls)

        elif index == 2:  # Function Keys
            function_keys = [
                'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12','f13','f14','f15','f16','f17','f18','f19','f20','f21','f22','f23','f24'
            ]
            self.actionSelect.addItems(function_keys)

        elif index == 3:  # Modifier Keys
            modifier_keys = [
                'alt', 'ctrl', 'shift', 'win',
                'delete', 'pause', 'insert', 'home', 'end', 'pageup', 'pagedown'  # Added these system control keys
            ]
            self.actionSelect.addItems(modifier_keys)

    def load_macros_and_update_list(self):
        # Load macros from file
        self.MacroPadApp = reload_macros()
        self.update_macro_list()

    def update_macro_list(self):
        self.macroList.clear()
        for command, details in self.MacroPadApp.items():
            list_item = f"{command}: {details['type']} - {details['action']}"
            self.macroList.addItem(list_item)

    def handle_received_data(self, data):
        try:
            decoded_data = data.decode('utf-8').strip()
            print(f"Received data: {decoded_data}")  # Debug print to confirm data reception

            # Debugging data processing logic
            encoder_cmd = decoded_data.split(': ')
            if len(encoder_cmd) == 2 and encoder_cmd[0].startswith('Enc'):
                encoder_id = int(encoder_cmd[0][3:])  # Extract encoder number
                command = encoder_cmd[1].strip()  # Ensure command is stripped of whitespace
                app_name = self.encoder_app_map.get(encoder_id)  # Retrieve mapped application name

                if app_name:
                    print(f"Handling volume adjustment for {app_name} with command {command}")
                    if command == '+':
                        adjust_volume(app_name, increase=True)
                    elif command == '-':
                        adjust_volume(app_name, increase=False)
                else:
                    print(f"No application mapped to encoder {encoder_id}")

            else:
                # If not an encoder command, handle as a regular macro or display update
                print("Data received does not match encoder patterns.")
                self.guiUpdater.updateTextSignal.emit(decoded_data)
                self.decodedVar = decoded_data
                self.execute_macro(decoded_data)

        except UnicodeDecodeError:
            print("Received non-UTF-8 data")
        except Exception as e:
            print(f"Error processing received data: {e}")
                  
    def execute_macro(self, command):
        macro = self.MacroPadApp.get(command)
        if macro:
            action_type = macro["type"]
            macro_action = macro["action"]

            try:
                if action_type == "Keyboard Key":
                    keyboard.send(macro_action)  # Use send for simpler direct key press
                elif action_type == "Media Control":
                    # Using keyboard for media controls. Make sure to handle exceptions if keys are not available
                    keyboard.send(macro_action)
                elif action_type == "Function Key":
                    keyboard.send(macro_action)  # Function keys are handled similarly to normal keys
                elif action_type == "Modifier Key":
                    # Modifier keys include both traditional modifiers and other keys categorized here for macros
                    # Handling individual key presses; consider adding functionality for combinations if needed
                    keyboard.send(macro_action)

                self.statusLabel.setText(f"Executed {action_type} macro for {command}: {macro_action}")
            except Exception as e:
                self.statusLabel.setText(f"Failed to execute {action_type} macro: {str(e)}")
                print(f"Error executing macro for {command}: {str(e)}")  # Optionally log to a file or logging system
        else:
            self.statusLabel.setText("No macro assigned for this command")

    def updateReceivedDataDisplay(self, text):
        self.receivedDataDisplay.append(text)
            
    def create_tray_menu(self):
        # Create tray menu
        self.tray_menu = QMenu()
        show_action = QAction('Show', self)
        show_action.triggered.connect(self.show)
        self.tray_menu.addAction(show_action)
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange and self.isVisible():
            if self.windowState() & Qt.WindowMinimized:
                event.ignore()
                self.hide()
                self.tray_icon.show()

    def toggle_window(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isHidden():
                self.showNormal()
                self.activateWindow()
            else:
                self.hide()
                self.tray_icon.show()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Exit', 'Are you sure you want to exit?',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if hasattr(self, 'tray_icon'):  # Check if tray_icon is initialized
                self.tray_icon.hide()
            event.accept()
            QApplication.quit()
        else:
            event.ignore()
            
import json
import os
import logging

import pyautogui

macros = {}

logging.basicConfig(level=logging.INFO)

def set_macro(command, action_type, action):
    macros[command] = {"type": action_type, "action": action}

    
def save_macros():
    file_path = os.path.join(os.path.dirname(__file__), '../Data/macros.json')
    try:
        with open(file_path, 'w') as f:
            json.dump(macros, f, indent=4)  # Use indent for better readability
        logging.info("Macros saved successfully.")
    except IOError as e:
        logging.error(f"Failed to save macros: {e}")
        raise IOError("Failed to save macros due to an I/O error.")

def reload_macros():
    file_path = os.path.join(os.path.dirname(__file__), '../Data/macros.json')
    try:
        with open(file_path, 'r') as f:
            loaded_macros = json.load(f)
            macros.update(loaded_macros)
            logging.info("Macros reloaded successfully.")
            return loaded_macros
    except FileNotFoundError:
        logging.warning("Macros file not found, loading defaults.")
        return {}
    except json.JSONDecodeError:
        logging.error("Error decoding JSON, loading defaults.")
        raise Exception("Failed to decode macros; JSON file is corrupted.")
    
def delete_macro(command):
    if command in macros:
        del macros[command]
        save_macros()
    else:
        logging.warning(f"Attempted to delete a non-existent macro: {command}")
        raise KeyError(f"No macro found for command '{command}'.")


    
def get_macro(command):
    # Return the action associated with the command or None if it doesn't exist
    return macros.get(command, None)

def execute_macro(self, command):
    macro = self.MacroPadApp.get(command)
    if macro:
        if macro["type"] == "Keyboard Key":
            pyautogui.press(macro["action"])
        elif macro["type"] == "Media Control":
            # Example for media control
            if macro["action"] == "play/pause":
                pyautogui.press('playpause')
            elif macro["action"] == "volume up":
                pyautogui.press('volumeup')
        elif macro["type"] == "Function Key":
            pyautogui.press(macro["action"])
        elif macro["type"] == "Modifier Key":
            # For a single key press, like pressing and releasing Alt
            pyautogui.keyDown(macro["action"])
            pyautogui.keyUp(macro["action"])
        self.statusLabel.setText(f"Executed {macro['type']} macro for {command}: {macro['action']}")
    else:
        self.statusLabel.setText("No macro assigned for this command")

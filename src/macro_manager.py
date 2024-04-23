import json
import os
import logging
import keyboard  # Import the keyboard library

# Configuration for logging
logging.basicConfig(level=logging.INFO)

macros = {}  # Dictionary to store macro configurations

def set_macro(command, action_type, action):
    """ Store the macro configuration in a dictionary """
    macros[command] = {"type": action_type, "action": action}
    logging.info(f"Macro set for {command}: {action_type} - {action}")

def save_macros():
    """ Save the macros dictionary to a JSON file """
    file_path = os.path.join(os.path.dirname(__file__), '../Data/macros.json')
    try:
        with open(file_path, 'w') as f:
            json.dump(macros, f, indent=4)  # Use indent for better readability
        logging.info("Macros saved successfully.")
    except IOError as e:
        logging.error(f"Failed to save macros: {e}")
        raise IOError("Failed to save macros due to an I/O error.")

def reload_macros():
    """ Load macros from a JSON file and update the macros dictionary """
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
    """ Delete a macro from the macros dictionary and save the changes """
    if command in macros:
        del macros[command]
        save_macros()
    else:
        logging.warning(f"Attempted to delete a non-existent macro: {command}")
        raise KeyError(f"No macro found for command '{command}'.")

def execute_macro(command):
    """ Execute the macro action based on the stored configuration """
    macro = macros.get(command)
    if macro:
        if macro["type"] == "Keyboard Key":
            keyboard.send(macro["action"])  # keyboard.send combines press and release
        elif macro["type"] == "Media Control":
            keyboard.send(macro["action"])  # Use send for media controls too
        elif macro["type"] == "Function Key":
            keyboard.send(macro["action"])  # Function keys treated similarly
        elif macro["type"] == "Modifier Key":
            keyboard.press_and_release(macro["action"])  # Press and release for modifiers
        logging.info(f"Executed {macro['type']} macro for {command}: {macro['action']}")
    else:
        logging.warning("No macro assigned for this command")

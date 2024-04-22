import json
import os
import logging

macros = {}

logging.basicConfig(level=logging.INFO)

def set_macro(command, action):
    macros[command] = action

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
    logging.debug(f"Deleting macro for command: {command}")
    if command in macros:
        del macros[command]
        try:
            save_macros()  # Save changes immediately after modification
        except Exception as e:
            logging.error(f"Failed to delete macro: {e}")
            raise Exception("Failed to delete macro due to file access issues.")
    else:
        logging.warning(f"Attempted to delete a non-existent macro: {command}")
        raise KeyError(f"No macro found for command '{command}'.")

    
def get_macro(command):
    # Return the action associated with the command or None if it doesn't exist
    return macros.get(command, None)

from core.hotkey import start_hotkey_listener
from ui.selected_app import get_user_configuration


def main():
    get_user_configuration()
    
    start_hotkey_listener()
    

if  __name__ == "__main__":
    main()

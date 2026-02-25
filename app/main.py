from core.hotkey import start_hotkey_listener
from core.notification import send_toast

def main():
    # get_user_configuration()
    send_toast("AutoH", "System started")
    start_hotkey_listener()
    

if  __name__ == "__main__":
    main()

import os


def get_apps_from_start_menu():
    apps = []
    START_MENU_PATHS = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]

    for base in START_MENU_PATHS:
        if not os.path.isdir(base):
            continue

        for root, dirs, files in os.walk(base):
            for file in files:
                if file.lower().endswith(".lnk"):
                    apps.append(
                        {
                            "name": os.path.splitext(file)[0],
                            "path": os.path.join(root, file),
                            "source": "start_menu",
                        }
                    )

    return apps

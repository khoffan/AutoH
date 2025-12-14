import winreg


def get_apps_from_registry():
    apps = []

    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in reg_paths:
            try:
                with winreg.OpenKey(root, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                name, _ = winreg.QueryValueEx(subkey, "DisplayName")

                                exe = ""
                                try:
                                    exe, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                except:
                                    pass

                                if name:
                                    apps.append({
                                        "name": name,
                                        "exe": exe
                                    })
                        except:
                            pass
            except:
                pass

    return apps
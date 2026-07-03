import copy
import json
import os
import sys

from config.get_base_dir import get_base_dir


def get_config_path():
    return os.path.join(get_base_dir(), "config.json")


def load_config(default=None, exit_on_missing=True):
    config_path = get_config_path()

    if not os.path.exists(config_path):
        if not exit_on_missing or default is not None:
            fallback = {"modes": {}} if default is None else default
            return copy.deepcopy(fallback)

        print("config.json not found:", config_path)
        input("Press Enter to exit...")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def save_config(config_data):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(config_data, config_file, indent=4, ensure_ascii=False)


def save_modes(modes):
    save_config({"modes": modes})


def save_config_file(mode_name, hotkey, app_list, urls=""):
    data = load_config(default={"modes": {}}, exit_on_missing=False)
    app_mapping = {app["name"]: (app.get("path") or app.get("exe")) for app in app_list}

    mode_data = {
        "hotkey": hotkey,
        "apps": app_mapping,
    }
    if urls:
        mode_data["urls"] = urls

    data.setdefault("modes", {})[mode_name] = mode_data
    save_config(data)


def delete_mode(mode_name):
    data = load_config(default={"modes": {}}, exit_on_missing=False)
    data.setdefault("modes", {}).pop(mode_name, None)
    save_config(data)

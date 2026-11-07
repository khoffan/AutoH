import os
import sys

APP_NAME = "AutoH"


def get_base_dir():
    """Folder that contains the exe (frozen) or the project root (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_user_data_dir():
    """Per-user writable folder: %LOCALAPPDATA%\\AutoH."""
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, APP_NAME)


def _is_writable_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def get_data_dir(filename=None):
    """Pick where data files live, without requiring anything to exist first.

    1. Next to the exe, if `filename` already exists there (portable mode).
    2. %LOCALAPPDATA%\\AutoH, if writable.
    3. Next to the exe, if writable.
    4. %LOCALAPPDATA%\\AutoH as a last resort (callers must tolerate write errors).
    """
    base_dir = get_base_dir()
    user_dir = get_user_data_dir()

    if filename and os.path.isfile(os.path.join(base_dir, filename)):
        return base_dir
    if filename and os.path.isfile(os.path.join(user_dir, filename)):
        return user_dir
    if _is_writable_dir(user_dir):
        return user_dir
    if _is_writable_dir(base_dir):
        return base_dir
    return user_dir

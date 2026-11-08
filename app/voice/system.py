"""Windows system control for voice actions (v2.1): volume, lock, sleep, power, closing apps.

All side effects live in `SystemControl` so tests and the dry-run REPL can swap
in a fake. Only fixed Windows APIs are called; nothing here takes a command line,
path or process id from what the user said.
"""
from __future__ import annotations

import os
import subprocess

# Processes that must never be closed by voice, whatever the name match says.
PROTECTED_PROCESSES = {
    "explorer.exe", "dwm.exe", "csrss.exe", "winlogon.exe", "wininit.exe", "lsass.exe",
    "services.exe", "svchost.exe", "smss.exe", "system", "registry", "fontdrvhost.exe",
    "sihost.exe", "taskmgr.exe", "autoh.exe",
}


def _is_shared_folder(folder: str) -> bool:
    """Folders that hold many unrelated programs: match exact exe only there."""
    folder = os.path.normcase(os.path.abspath(folder))
    windir = os.path.normcase(os.environ.get("WINDIR", r"C:\Windows"))
    if folder == windir or folder.startswith(windir + os.sep):
        return True
    roots = {os.path.normcase(os.path.abspath(os.environ[var])) for var in (
        "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData", "LOCALAPPDATA",
        "APPDATA", "USERPROFILE", "PUBLIC") if os.environ.get(var)}
    if os.environ.get("LOCALAPPDATA"):
        roots.add(os.path.normcase(os.path.join(os.environ["LOCALAPPDATA"], "Programs")))
    return folder in roots or os.path.dirname(folder) == folder      # drive root


def _package_matcher(family: str):
    """exe path -> True if it belongs to package family 'Name_publisherid'."""
    if "_" not in family:
        return lambda _exe: False
    name, publisher = (part.lower() for part in family.rsplit("_", 1))

    def matches(exe: str) -> bool:
        parts = exe.lower().split(os.sep)
        if "windowsapps" not in parts:
            return False
        index = parts.index("windowsapps")
        if index + 1 >= len(parts):
            return False
        folder = parts[index + 1]
        return folder.startswith(name + "_") and folder.endswith("_" + publisher)
    return matches


def lnk_target(path: str) -> str:
    """Target of a .lnk shortcut ("" if it cannot be read). Other paths unchanged."""
    if not path.lower().endswith(".lnk"):
        return path
    try:
        import comtypes.client
        from comtypes.persist import IPersistFile
        from comtypes.shelllink import ShellLink

        link = comtypes.client.CreateObject(ShellLink)
        link.QueryInterface(IPersistFile).Load(path, 0)
        return link.GetPath(0) or ""
    except Exception:
        return ""


class SystemControl:
    """Real implementation. Every method may raise; handlers turn errors into messages."""

    # ---------------------------------------------------------------- volume
    @staticmethod
    def _endpoint():
        from pycaw.pycaw import AudioUtilities

        return AudioUtilities.GetSpeakers().EndpointVolume

    def get_volume(self) -> int:
        return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, level: int) -> None:
        endpoint = self._endpoint()
        endpoint.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
        if level > 0:
            endpoint.SetMute(0, None)          # "เสียง 30" while muted should be audible

    def set_mute(self, on: bool) -> None:
        self._endpoint().SetMute(1 if on else 0, None)

    # ---------------------------------------------------------------- session / power
    def lock(self) -> None:
        import ctypes

        if not ctypes.windll.user32.LockWorkStation():
            raise OSError("LockWorkStation failed")

    def sleep(self) -> None:
        import ctypes

        # SetSuspendState(hibernate=False, force=False, wakeup_events_disabled=False)
        if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
            raise OSError("SetSuspendState failed")

    def shutdown(self) -> None:
        # The app already showed its own cancellable countdown; Windows runs it now.
        subprocess.run(["shutdown", "/s", "/t", "0"], check=True, creationflags=_NO_WINDOW)

    def restart(self) -> None:
        subprocess.run(["shutdown", "/r", "/t", "0"], check=True, creationflags=_NO_WINDOW)

    # ---------------------------------------------------------------- apps
    def running_pids(self, path: str, name: str) -> set[int]:
        """PIDs of the app at `path` (shortcuts resolved), never protected processes.

        Stricter than launcher._app_pids (used only to focus a window): a process
        counts if it is the same exe, or lives under the app's own folder. Shared
        folders (C:\\Windows, Program Files root, ...) only allow the exact exe, so
        "ปิด Notepad" can never reach other System32 programs.
        """
        import psutil

        from system.store_apps import is_packaged_path, package_family

        if is_packaged_path(path):
            # Store app: its exe lives in WindowsApps\<Name>_<version>_<arch>_<res>_<publisher>\
            target, folder, allow_folder = "", "", False
            package = _package_matcher(package_family(path))
        else:
            target = os.path.normcase(os.path.abspath(lnk_target(path) or path))
            folder = os.path.dirname(target)
            allow_folder = target.endswith(".exe") and not _is_shared_folder(folder)
            package = None
        compact = name.lower().replace(" ", "")
        own = os.getpid()
        pids = set()
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                pid, pname = proc.info["pid"], (proc.info["name"] or "").lower()
                exe = os.path.normcase(proc.info["exe"] or "")
            except (psutil.Error, OSError):
                continue
            if pid == own or pname in PROTECTED_PROCESSES:
                continue
            if (exe and exe == target) \
                    or (allow_folder and exe.startswith(folder + os.sep)) \
                    or (package is not None and package(exe)) \
                    or (len(compact) >= 3 and pname.removesuffix(".exe") == compact):
                pids.add(pid)
        return pids

    def close_windows(self, pids: set[int]) -> int:
        """Ask the app's windows to close (WM_CLOSE), like clicking X. Returns windows asked.

        Never kills: the app can still ask to save, and tray apps may keep running.
        """
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        windows = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4) \
                    and user32.GetWindowTextLengthW(hwnd) > 0:      # 4 = GW_OWNER: skip popups
                windows.append(hwnd)
            return True

        user32.EnumWindows(callback, 0)
        for hwnd in windows:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)                    # WM_CLOSE
        return len(windows)


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_default: SystemControl | None = None


def default() -> SystemControl:
    global _default
    if _default is None:
        _default = SystemControl()
    return _default

"""App scanning: Start Menu filter fix and Store (packaged) apps."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from system import normalize  # noqa: E402
from system.store_apps import get_store_apps, is_packaged_path, package_family  # noqa: E402
from voice.system import _package_matcher  # noqa: E402

MENU = r"C:\Users\me\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"
COMMON = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"


def names(menu_apps, reg_apps=()):
    with mock.patch("builtins.print"):
        return {app["name"] for app in normalize.normalize_apps(list(reg_apps), menu_apps)}


def link(name, folder=MENU):
    return {"name": name, "path": os.path.join(folder, name + ".lnk"), "source": "start_menu"}


class StartMenuFilterTest(unittest.TestCase):
    def test_start_menu_location_alone_does_not_filter(self):
        kept = names([link("Discord"), link("LINE", MENU + r"\LINE"), link("Steam", COMMON + r"\Steam"),
                      link("Visual Studio Code", MENU + r"\Visual Studio Code")])
        self.assertEqual(kept, {"Discord", "LINE", "Steam", "Visual Studio Code"})

    def test_still_filtered(self):
        kept = names([
            link("Event Viewer", COMMON + r"\Administrative Tools"),
            link("Administrative Tools"),
            link("Windows PowerShell", MENU + r"\Windows PowerShell"),
            link("WinRAR help", COMMON + r"\WinRAR"),
            link("Visit MobaXterm Website", COMMON + r"\MobaXterm"),
            link("Uninstall Discord"),
        ])
        self.assertEqual(kept, set())

    def test_office_and_browsers_kept(self):
        self.assertEqual(names([link("Microsoft Edge", COMMON), link("Word", COMMON)]),
                         {"Microsoft Edge", "Word"})


class StoreAppsTest(unittest.TestCase):
    def test_parse_get_start_apps_output(self):
        output = ('[{"Name":"Notepad","AppID":"Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},'
                  '{"Name":"Google Chrome","AppID":"Chrome"},'
                  '{"Name":"WSL Settings","AppID":"{6D809377}\\\\WSL\\\\wslsettings.exe"}]')
        result = mock.Mock(stdout=output.encode("utf-8"))
        with mock.patch("subprocess.run", return_value=result):
            apps = get_store_apps()
        self.assertEqual(apps, [{"name": "Notepad", "source": "store",
                                 "path": "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"}])

    def test_powershell_failure_returns_empty(self):
        with mock.patch("subprocess.run", side_effect=OSError("no powershell")):
            self.assertEqual(get_store_apps(), [])

    def test_package_helpers(self):
        path = "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"
        self.assertTrue(is_packaged_path(path))
        self.assertFalse(is_packaged_path(r"C:\Windows\notepad.exe"))
        self.assertEqual(package_family(path), "Microsoft.WindowsNotepad_8wekyb3d8bbwe")

    def test_package_matcher(self):
        matches = _package_matcher("Microsoft.WindowsCalculator_8wekyb3d8bbwe")
        base = os.path.normcase(r"C:\Program Files\WindowsApps")
        self.assertTrue(matches(base + os.path.normcase(
            r"\Microsoft.WindowsCalculator_11.2502.2.0_x64__8wekyb3d8bbwe\CalculatorApp.exe")))
        self.assertFalse(matches(base + os.path.normcase(
            r"\Microsoft.WindowsNotepad_11.2.0_x64__8wekyb3d8bbwe\Notepad.exe")))
        self.assertFalse(matches(os.path.normcase(r"C:\Apps\Microsoft.WindowsCalculator_1_x64__8wekyb3d8bbwe\a.exe")))


if __name__ == "__main__":
    unittest.main()

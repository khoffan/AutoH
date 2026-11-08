"""v2.1 M1: system actions (close app, volume, mute, lock, sleep, shutdown, restart)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from voice import intents  # noqa: E402
from voice.actions import Action, ActionContext, Risk, tool_definitions  # noqa: E402
from voice.intents import parse_number  # noqa: E402
from voice.pipeline import execute, interpret_detail  # noqa: E402
from voice.validate import Rejected, resolve  # noqa: E402


class FakeSystem:
    def __init__(self, running=("Google Chrome",), volume=40):
        self.running = set(running)
        self.volume = volume
        self.calls = []

    def running_pids(self, path, name):
        return {123} if name in self.running else set()

    def close_windows(self, pids):
        self.calls.append(("close", sorted(pids)))
        return 2

    def get_volume(self):
        return self.volume

    def set_volume(self, level):
        self.calls.append(("volume", level))
        self.volume = level

    def set_mute(self, on):
        self.calls.append(("mute", on))

    def lock(self):
        self.calls.append(("lock",))

    def sleep(self):
        self.calls.append(("sleep",))

    def shutdown(self):
        self.calls.append(("shutdown",))

    def restart(self):
        self.calls.append(("restart",))


def make_ctx(**kwargs):
    system = FakeSystem(**kwargs)
    ctx = ActionContext(
        apps={"Google Chrome": r"C:\Apps\Chrome\chrome.exe", "LINE": r"C:\Apps\LINE\line.exe"},
        modes={}, aliases={"ไลน์": ("LINE", "app"), "โครม": ("Google Chrome", "app")},
        system=system,
    )
    return ctx, system


def yes(_question):
    return True


def no(_question):
    return False


class ParseNumberTests(unittest.TestCase):
    def test_numbers(self):
        cases = {"30": 30, "๗๐": 70, "สามสิบ": 30, "ยี่สิบห้า": 25, "สิบเอ็ด": 11, "สิบ": 10,
                 "ร้อย": 100, "ห้าสิบ เปอร์เซ็นต์": 50, "ศูนย์": 0}
        for text, expected in cases.items():
            self.assertEqual(parse_number(text), expected, text)

    def test_not_numbers(self):
        for text in ("", "สองสาม", "ดัง", "abc"):
            self.assertIsNone(parse_number(text), text)


class SystemIntentTests(unittest.TestCase):
    def check(self, text, name, args=None):
        actions = intents.parse(text)
        self.assertEqual(len(actions), 1, text)
        self.assertEqual(actions[0].name, name, text)
        if args is not None:
            self.assertEqual(actions[0].args, args, text)

    def test_volume(self):
        self.check("เสียง 30", "set_volume", {"level": 30})
        self.check("ตั้งเสียงเป็นห้าสิบ", "set_volume", {"level": 50})
        self.check("ปรับเสียง 20%", "set_volume", {"level": 20})
        self.check("volume 80", "set_volume", {"level": 80})
        self.check("เพิ่มเสียง", "set_volume", {"delta": 10})
        self.check("เพิ่มเสียงอีก 20", "set_volume", {"delta": 20})
        self.check("ลดเสียงหน่อย", "set_volume", {"delta": -10})
        self.check("เสียงเบาลง 5", "set_volume", {"delta": -5})

    def test_volume_out_of_range_not_understood(self):
        self.assertEqual(intents.parse("เสียง 150"), [])

    def test_mute(self):
        self.check("ปิดเสียง", "mute", {"on": True})
        self.check("mute", "mute", {"on": True})
        self.check("เปิดเสียง", "mute", {"on": False})

    def test_power_and_lock(self):
        self.check("ล็อกเครื่อง", "lock_screen", {})
        self.check("ล็อคหน้าจอ", "lock_screen", {})
        self.check("lock screen", "lock_screen", {})
        self.check("พักเครื่อง", "sleep", {})
        self.check("sleep", "sleep", {})
        self.check("ปิดเครื่อง", "shutdown", {})
        self.check("ปิดคอมให้หน่อย", "shutdown", {})
        self.check("shut down", "shutdown", {})
        self.check("รีสตาร์ทเครื่อง", "restart", {})
        self.check("restart", "restart", {})

    def test_close_app(self):
        self.check("ปิด chrome", "close_app", {"name": "chrome"})
        self.check("ปิดโปรแกรมไลน์", "close_app", {"name": "ไลน์"})
        self.check("close line", "close_app", {"name": "line"})

    def test_existing_commands_unchanged(self):
        self.check("เปิดไลน์", "open_app", {"name": "ไลน์"})
        self.check("ตั้งค่าเสียง", "open_settings", {"page": "เสียง"})
        self.check("เปิดเพลงเสียงสวรรค์", "play_music", {"query": "เสียงสวรรค์"})


class ResolveSystemTests(unittest.TestCase):
    def test_close_running_app_needs_confirm(self):
        ctx, _ = make_ctx()
        item = resolve(Action("close_app", {"name": "โครม"}), ctx)
        self.assertEqual(item.action.args["name"], "Google Chrome")
        self.assertTrue(item.needs_confirm)
        self.assertEqual(item.spec.risk, Risk.CONFIRM)

    def test_close_app_not_running(self):
        ctx, _ = make_ctx(running=())
        with self.assertRaises(Rejected) as caught:
            resolve(Action("close_app", {"name": "line"}), ctx)
        self.assertIn("ไม่ได้เปิดอยู่", str(caught.exception))

    def test_close_unknown_app_offers_no_picker(self):
        ctx, _ = make_ctx()
        with self.assertRaises(Rejected) as caught:
            resolve(Action("close_app", {"name": "zzqx"}), ctx)
        self.assertIsNone(caught.exception.term)

    def test_volume_args_are_checked(self):
        ctx, _ = make_ctx()
        bad = [{"level": 150}, {"level": -1}, {"level": "30"}, {"level": True}, {"level": 30, "delta": 5},
               {}, {"delta": 0}, {"volume": 30}]
        for args in bad:
            with self.assertRaises(Rejected, msg=args):
                resolve(Action("set_volume", args), ctx)

    def test_mute_needs_boolean(self):
        ctx, _ = make_ctx()
        with self.assertRaises(Rejected):
            resolve(Action("mute", {"on": "yes"}), ctx)

    def test_no_arg_actions_reject_args(self):
        ctx, _ = make_ctx()
        with self.assertRaises(Rejected):
            resolve(Action("shutdown", {"command": "shutdown /s /t 0"}), ctx)

    def test_disabled_action(self):
        ctx, _ = make_ctx()
        ctx.disabled = {"shutdown"}
        resolved, rejected = interpret_detail("ปิดเครื่อง", ctx)
        self.assertEqual(resolved, [])
        self.assertIn("ถูกปิดใช้", str(rejected[0]))

    def test_tool_definitions_have_typed_params(self):
        tools = {tool["name"]: tool for tool in tool_definitions()}
        for name in ("close_app", "set_volume", "mute", "lock_screen", "sleep", "shutdown", "restart"):
            self.assertIn(name, tools)
        self.assertEqual(tools["set_volume"]["input_schema"]["properties"]["level"]["type"], "integer")


class ExecuteSystemTests(unittest.TestCase):
    def run_text(self, text, ctx, confirm=yes, countdown=None):
        resolved, rejected = interpret_detail(text, ctx)
        self.assertEqual(rejected, [], text)
        return execute(resolved, ctx, confirm, countdown=countdown)

    def test_volume_safe_runs_without_confirm(self):
        ctx, system = make_ctx(volume=95)
        results = self.run_text("เพิ่มเสียง 20", ctx, confirm=no)
        self.assertEqual(system.calls, [("volume", 100)])          # clamped
        self.assertEqual(results[0][1], "volume 100%")

    def test_lock_runs(self):
        ctx, system = make_ctx()
        self.run_text("ล็อกเครื่อง", ctx, confirm=no)
        self.assertEqual(system.calls, [("lock",)])

    def test_close_app_asks_first(self):
        ctx, system = make_ctx()
        results = self.run_text("ปิด chrome", ctx, confirm=no)
        self.assertEqual(results[0][1], "cancelled")
        self.assertEqual(system.calls, [])
        self.run_text("ปิด chrome", ctx, confirm=yes)
        self.assertEqual(system.calls, [("close", [123])])

    def test_close_app_exited_meanwhile(self):
        ctx, system = make_ctx()
        resolved, _ = interpret_detail("ปิด chrome", ctx)
        system.running.clear()
        results = execute(resolved, ctx, yes)
        self.assertIn("ไม่ได้เปิดอยู่", results[0][1])
        self.assertEqual(system.calls, [])

    def test_sleep_asks_first(self):
        ctx, system = make_ctx()
        self.assertEqual(self.run_text("พักเครื่อง", ctx, confirm=no)[0][1], "cancelled")
        self.run_text("พักเครื่อง", ctx, confirm=yes)
        self.assertEqual(system.calls, [("sleep",)])

    def test_shutdown_needs_confirm_and_countdown(self):
        ctx, system = make_ctx()
        countdowns = []

        def go(label, seconds):
            countdowns.append((label, seconds))
            return True

        self.assertEqual(self.run_text("ปิดเครื่อง", ctx, confirm=no, countdown=go)[0][1], "cancelled")
        self.assertEqual(countdowns, [])                     # "no" never starts the countdown
        self.assertEqual(self.run_text("ปิดเครื่อง", ctx, confirm=yes, countdown=None)[0][1], "cancelled")
        self.assertEqual(self.run_text("ปิดเครื่อง", ctx, confirm=yes,
                                       countdown=lambda *_: False)[0][1], "cancelled")
        self.assertEqual(system.calls, [])
        self.run_text("ปิดเครื่อง", ctx, confirm=yes, countdown=go)
        self.assertEqual(system.calls, [("shutdown",)])
        self.assertEqual(countdowns, [("ปิดเครื่อง", 30)])

    def test_restart_is_critical(self):
        ctx, system = make_ctx()
        self.run_text("รีสตาร์ท", ctx, confirm=yes, countdown=lambda *_: False)
        self.assertEqual(system.calls, [])


class RunningPidsTests(unittest.TestCase):
    @staticmethod
    def pids_for(path, name, procs):
        from voice.system import SystemControl

        class Proc:
            def __init__(self, pid, pname, exe):
                self.info = {"pid": pid, "name": pname, "exe": exe}

        fake = [Proc(*p) for p in procs]
        with mock.patch("psutil.process_iter", return_value=fake):
            return SystemControl().running_pids(path, name)

    def test_app_folder_matches_but_protected_and_own_never(self):
        procs = [
            (1, "chrome.exe", r"C:\Apps\Chrome\chrome.exe"),
            (2, "helper.exe", r"C:\Apps\Chrome\sub\helper.exe"),       # same app folder
            (3, "explorer.exe", r"C:\Apps\Chrome\explorer.exe"),       # protected name
            (os.getpid(), "python.exe", r"C:\Apps\Chrome\python.exe"),  # AutoH itself
            (5, "other.exe", r"C:\Apps\Other\other.exe"),
        ]
        self.assertEqual(self.pids_for(r"C:\Apps\Chrome\chrome.exe", "Google Chrome", procs), {1, 2})

    def test_shared_windows_folder_matches_exact_exe_only(self):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        procs = [
            (1, "notepad.exe", windir + r"\System32\notepad.exe"),
            (2, "cmd.exe", windir + r"\System32\cmd.exe"),
            (3, "conhost.exe", windir + r"\System32\conhost.exe"),
        ]
        self.assertEqual(self.pids_for(windir + r"\System32\notepad.exe", "Notepad", procs), {1})

    def test_lnk_target_passes_other_paths_through(self):
        from voice.system import lnk_target

        self.assertEqual(lnk_target(r"C:\a\b.exe"), r"C:\a\b.exe")
        self.assertEqual(lnk_target(r"C:\missing\nothing.lnk"), "")


if __name__ == "__main__":
    unittest.main()

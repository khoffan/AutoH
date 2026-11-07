import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from config import database  # noqa: E402
from voice import intents  # noqa: E402
from voice.actions import Action, ActionContext, tool_definitions  # noqa: E402
from voice.matching import normalize  # noqa: E402
from voice.pipeline import execute, interpret  # noqa: E402
from voice.validate import Rejected, resolve  # noqa: E402


def make_ctx(**overrides):
    opened, urls, modes_run = [], [], []
    ctx = ActionContext(
        apps={
            "LINE": r"C:\Apps\LINE\line.exe",
            "Google Chrome": r"C:\Apps\Chrome\chrome.exe",
            "MongoDB Compass": r"C:\Apps\Compass\compass.exe",
            "Visual Studio Code": r"C:\Apps\Code\code.exe",
        },
        modes={"work": {"hotkey": "ctrl+alt+t", "apps": {}}},
        aliases=dict(database.DEFAULT_ALIASES),
        open_app=lambda path, name: opened.append(name),
        open_url=urls.append,
        run_mode=modes_run.append,
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx, opened, urls, modes_run


class NormalizeTest(unittest.TestCase):
    def test_keeps_thai_marks_and_strips_fillers(self):
        self.assertEqual(normalize("เปิดไลน์ให้หน่อยครับ."), "เปิดไลน์")
        self.assertEqual(normalize("  Open   Chrome, please! "), "open chrome")


class IntentTest(unittest.TestCase):
    CASES = [
        ("เปิดไลน์", "open_app", {"name": "ไลน์"}),
        ("เปิดโปรแกรม excel", "open_app", {"name": "excel"}),
        ("open chrome", "open_app", {"name": "chrome"}),
        ("เปิดเว็บยูทูบ", "open_url", {"site": "ยูทูบ"}),
        ("go to github", "open_url", {"site": "github"}),
        ("ค้นหาราคาทอง", "web_search", {"query": "ราคาทอง"}),
        ("search for python tutorial", "web_search", {"query": "python tutorial"}),
        ("เข้าโหมด work", "run_mode", {"name": "work"}),
        ("โหมดwork", "run_mode", {"name": "work"}),
        ("mode work", "run_mode", {"name": "work"}),
    ]

    def test_rules(self):
        for text, name, args in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(intents.parse(text), [Action(name, args)])

    def test_not_understood(self):
        for text in ("", "สวัสดี", "เปิด", "ครับ"):
            with self.subTest(text=text):
                self.assertEqual(intents.parse(text), [])


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.ctx, *_ = make_ctx()

    def check(self, text, name, key, value, confirm=False):
        resolved, errors = interpret(text, self.ctx)
        self.assertEqual(errors, [], text)
        self.assertEqual(resolved[0].action.name, name, text)
        self.assertEqual(resolved[0].action.args[key], value, text)
        self.assertEqual(resolved[0].needs_confirm, confirm, text)

    def test_apps(self):
        self.check("เปิดไลน์ครับ", "open_app", "name", "LINE")
        self.check("เปิด chrome", "open_app", "name", "Google Chrome")
        self.check("เปิดโครม", "open_app", "name", "Google Chrome")
        self.check("เปิด compass", "open_app", "name", "MongoDB Compass")
        self.check("เปิดวีเอสโค้ด", "open_app", "path", r"C:\Apps\Code\code.exe")

    def test_open_falls_through_to_site_and_mode(self):
        self.check("เปิดยูทูบ", "open_url", "url", "https://www.youtube.com")
        self.check("เปิด youtube", "open_url", "site", "youtube")
        self.check("เปิด work", "run_mode", "name", "work")

    def test_search_and_mode(self):
        self.check("ค้นหาราคาทอง", "web_search", "query", "ราคาทอง")
        self.check("เข้าโหมด work", "run_mode", "name", "work")

    def test_fuzzy_asks(self):
        self.check("เปิด crome", "open_app", "name", "Google Chrome", confirm=True)
        self.check("เปิด compas", "open_app", "name", "MongoDB Compass", confirm=True)

    def test_unknown(self):
        resolved, errors = interpret("เปิด photoshop", self.ctx)
        self.assertEqual(resolved, [])
        self.assertEqual(len(errors), 1)
        resolved, errors = interpret("สวัสดีครับ", self.ctx)
        self.assertEqual(resolved, [])
        self.assertIn("ไม่เข้าใจ", errors[0])


class ValidateGuardTest(unittest.TestCase):
    """Inputs an LLM (v2.1) might produce must be rejected."""

    def setUp(self):
        self.ctx, *_ = make_ctx()

    def test_rejects(self):
        bad = [
            Action("run_shell", {"cmd": "del C:\\"}),
            Action("open_app", {"name": "LINE", "path": r"C:\Windows\System32\cmd.exe"}),
            Action("open_app", {"name": r"C:\Windows\System32\cmd.exe"}),
            Action("open_url", {"site": "http://evil.example.com/payload.exe"}),
            Action("open_app", {"name": ""}),
            Action("open_app", {"name": 123}),
            Action("open_app", {}),
            Action("web_search", {"query": "x" * 500}),
            Action("open_app", "LINE"),
        ]
        for action in bad:
            with self.subTest(action=action):
                with self.assertRaises(Rejected):
                    resolve(action, self.ctx)

    def test_tool_definitions(self):
        names = {t["name"] for t in tool_definitions()}
        self.assertEqual(names, {"open_app", "open_url", "web_search", "run_mode"})


class ExecuteTest(unittest.TestCase):
    def test_runs_and_confirms(self):
        ctx, opened, urls, modes_run = make_ctx()
        asked = []

        resolved, _ = interpret("เปิดไลน์", ctx)
        execute(resolved, ctx, confirm=lambda q: asked.append(q) or False)
        self.assertEqual((opened, asked), (["LINE"], []))

        resolved, _ = interpret("เปิด crome", ctx)
        results = execute(resolved, ctx, confirm=lambda q: asked.append(q) or False)
        self.assertEqual(results[0][1], "cancelled")
        self.assertEqual(opened, ["LINE"])
        self.assertEqual(len(asked), 1)

        resolved, _ = interpret("ค้นหา ราคา ทอง", ctx)
        execute(resolved, ctx, confirm=lambda q: True)
        self.assertEqual(urls, ["https://www.google.com/search?q=%E0%B8%A3%E0%B8%B2%E0%B8%84%E0%B8%B2+%E0%B8%97%E0%B8%AD%E0%B8%87"])

    def test_handler_error_is_caught(self):
        ctx, *_ = make_ctx(run_mode=None)
        resolved, _ = interpret("โหมด work", ctx)
        results = execute(resolved, ctx, confirm=lambda q: True)
        self.assertTrue(results[0][1].startswith("error:"))


class SchemaUpgradeTest(unittest.TestCase):
    def test_v1_db_gets_v2_tables_and_aliases(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "autoh.db")
        with sqlite3.connect(path) as conn:  # minimal v1 database
            conn.executescript(
                "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);"
                "INSERT INTO meta VALUES ('schema_version', '1'), ('legacy_json_migrated', '1');"
            )
        conn.close()

        with mock.patch.object(database, "get_db_path", return_value=path), \
             mock.patch.object(database, "get_base_dir", return_value=tmp), \
             mock.patch.object(database, "get_user_data_dir", return_value=tmp), \
             mock.patch.object(database, "_initialized_paths", set()):
            with database.connect() as conn:
                version = conn.execute(
                    "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
                aliases = database.read_aliases(conn)
                database.set_setting(conn, "voice_hotkey", "ctrl+alt+v")
                database.write_app_index(conn, [("LINE", "C:/line.exe", "mode")])
            with database.connect() as conn:
                self.assertEqual(database.get_setting(conn, "voice_hotkey"), "ctrl+alt+v")
                self.assertEqual(database.read_app_index(conn), {"LINE": "C:/line.exe"})

        self.assertEqual(version, "2")
        self.assertEqual(aliases["ไลน์"], ("line", "app"))


if __name__ == "__main__":
    unittest.main()

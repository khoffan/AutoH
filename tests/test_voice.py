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
from voice.pipeline import (  # noqa: E402
    apply_pick, execute, history_record, interpret, interpret_detail, learn_alias, picker_options,
)
from voice.validate import Rejected, resolve, suggest  # noqa: E402


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
        open_path=urls.append,
        find_video=lambda query: None,   # no network in tests: search-page fallback
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

    def test_typhoon_transcripts(self):
        """Real Typhoon ASR outputs from the M1 benchmark: English names spelled in Thai."""
        self.ctx.apps.update({
            "Docker Desktop": "C:/docker.exe", "Canva": "C:/canva.exe",
            "Microsoft Edge": "C:/edge.exe", "WinRAR 7.13 (64-bit)": "C:/winrar.exe",
        })
        cases = [
            ("เปิดโครม", "open_app", "Google Chrome"),
            ("เปิด มงโกดีบี คอมพาส", "open_app", "MongoDB Compass"),
            ("เปิด ด็อกเกอร์ Distop", "open_app", "Docker Desktop"),
            ("เปิดแขนว่า", "open_app", "Canva"),
            ("เปิดไมโครซอฟเอด", "open_app", "Microsoft Edge"),
            ("เปิดวินรา", "open_app", "WinRAR 7.13 (64-bit)"),
            ("โอเพ่นโครม", "open_app", "Google Chrome"),
            ("เปิดยูทูป", "open_url", "youtube"),
            ("เปิดเว็บกิตทับ", "open_url", "github"),
            ("เข้าโหมดเวิร์ค", "run_mode", "work"),
            # Manual test 2026-11-08: Thai final consonants (ส = /t/) and "ให้" filler
            ("เปิดคลอสให้หน่อย", "open_url", "claude"),
            ("เปิดเว็บคลอสให้หน่อย", "open_url", "claude"),
            ("เปิดไลน์น่ะ", "open_app", "LINE"),
        ]
        for text, name, target in cases:
            with self.subTest(text=text):
                resolved, errors = interpret(text, self.ctx)
                self.assertEqual(errors, [])
                self.assertEqual(resolved[0].action.name, name)
                self.assertIn(target, (resolved[0].action.args.get("name"),
                                       resolved[0].action.args.get("site")))
        for text in ("คนหาร้านกาแฟใกล้ฉัน", "เสิร์ช ไพทอน"):
            with self.subTest(text=text):
                self.assertEqual(interpret(text, self.ctx)[0][0].action.name, "web_search")

    def test_phonetic_does_not_overmatch(self):
        for text in ("เปิดร้าย", "เปิด photoshop", "เปิดราคาทอง"):
            with self.subTest(text=text):
                self.assertEqual(interpret(text, self.ctx)[0], [])

    def test_unknown(self):
        resolved, errors = interpret("เปิด photoshop", self.ctx)
        self.assertEqual(resolved, [])
        self.assertEqual(len(errors), 1)
        resolved, errors = interpret("สวัสดีครับ", self.ctx)
        self.assertEqual(resolved, [])
        self.assertIn("ไม่เข้าใจ", errors[0])


class FuzzyVerbTest(unittest.TestCase):
    """Verbs as Typhoon/Whisper actually misheard them in the M1 benchmark."""

    def test_recovers_misheard_verbs(self):
        cases = [
            ("คนหาร้านกาแฟใกล้ฉัน", "web_search", {"query": "ร้านกาแฟใกล้ฉัน"}),
            ("ข้นหาสภาพอากาศ", "web_search", {"query": "สภาพอากาศ"}),
            ("หมดเวิร์ค", "run_mode", {"name": "เวิร์ค"}),
            ("เข้าหมดเวิร์ก", "run_mode", {"name": "เวิร์ก"}),
            ("เปิ้ดไลน์", "open_app", {"name": "ไลน์"}),
        ]
        for text, name, args in cases:
            with self.subTest(text=text):
                [action] = intents.parse(text)
                self.assertEqual((action.name, action.args), (name, args))
                self.assertLess(action.confidence, 1.0)

    def test_low_confidence_verb_asks(self):
        ctx, *_ = make_ctx()
        [item], _ = interpret("คุณหาราคาทอง", ctx)   # 0.84: plausible but not sure
        self.assertEqual(item.action.name, "web_search")
        self.assertTrue(item.needs_confirm)

    def test_ordinary_sentences_are_not_commands(self):
        for text in ("ขนมปังอร่อย", "สวัสดีครับ", "เงือกล้าย", "วันนี้อากาศดี"):
            with self.subTest(text=text):
                self.assertEqual(intents.parse(text), [])

    def test_exact_verbs_keep_full_confidence(self):
        self.assertEqual(intents.parse("ค้นหาราคาทอง")[0].confidence, 1.0)


class LearningTest(unittest.TestCase):
    def test_confirmed_guess_is_learned(self):
        ctx, opened, *_ = make_ctx()
        saved = []
        [item], _ = interpret("เปิด มงโกดีบี คอมพาส", ctx)
        self.assertTrue(item.needs_confirm)

        execute([item], ctx, confirm=lambda q: True, save_alias=lambda *a: saved.append(a))
        self.assertEqual(saved, [("มงโกดีบี คอมพาส", "MongoDB Compass", "app")])

        [again], _ = interpret("เปิด มงโกดีบี คอมพาส", ctx)
        self.assertFalse(again.needs_confirm)
        self.assertEqual(again.action.args["name"], "MongoDB Compass")

    def test_cancelled_or_verb_only_guess_is_not_learned(self):
        ctx, *_ = make_ctx()
        saved = []
        [item], _ = interpret("เปิด มงโกดีบี คอมพาส", ctx)
        execute([item], ctx, confirm=lambda q: False, save_alias=lambda *a: saved.append(a))
        [item], _ = interpret("เปิ้ดโครม", ctx)        # verb guessed, name certain
        execute([item], ctx, confirm=lambda q: True, save_alias=lambda *a: saved.append(a))
        self.assertEqual(saved, [])

    def test_pick_from_suggestions_then_learn(self):
        ctx, *_ = make_ctx()
        resolved, rejected = interpret_detail("เปิดร้าย", ctx)
        self.assertEqual(resolved, [])
        self.assertEqual(rejected[0].term, "ร้าย")

        options = suggest(rejected[0].term, ctx)
        self.assertTrue(options)                       # picker has something to show
        self.assertTrue(learn_alias("ร้าย", "app", "LINE", ctx))
        [item], _ = interpret("เปิดร้าย", ctx)
        self.assertEqual(item.action.args["name"], "LINE")
        self.assertFalse(item.needs_confirm)

    def test_rejects_useless_aliases(self):
        ctx, *_ = make_ctx()
        self.assertFalse(learn_alias("ก", "app", "LINE", ctx))
        self.assertFalse(learn_alias("line", "app", "LINE", ctx))
        self.assertFalse(learn_alias("xx", "web_search", "LINE", ctx))

    def test_history_record(self):
        ctx, *_ = make_ctx()
        resolved, _ = interpret("เปิดไลน์", ctx)
        results = execute(resolved, ctx, confirm=lambda q: True)
        source, actions, result = history_record(resolved, results)
        self.assertEqual((source, result), ("rule", "done"))
        self.assertNotIn("path", actions[0]["args"])
        self.assertEqual(history_record([], None), ("none", [], "rejected"))


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
            Action("open_folder", {"name": r"C:\Windows\System32"}),
            Action("open_folder", {"name": "Downloads", "path": r"C:\Windows"}),
            Action("open_settings", {"page": "ms-settings:anything"}),
            Action("open_settings", {"page": "network", "uri": "file:///C:/evil.exe"}),
        ]
        for action in bad:
            with self.subTest(action=action):
                with self.assertRaises(Rejected):
                    resolve(action, self.ctx)

    def test_tool_definitions(self):
        names = {t["name"] for t in tool_definitions()}
        self.assertEqual(names, {"open_app", "open_url", "web_search", "run_mode",
                                 "play_music", "open_folder", "open_settings",
                             # v2.1 system actions (tests/test_voice_system.py)
                             "close_app", "set_volume", "mute", "lock_screen", "sleep",
                             "shutdown", "restart"})


class MoreActionsTest(unittest.TestCase):
    """play_music (YouTube), open_folder (known folders), open_settings (whitelist)."""

    def setUp(self):
        self.ctx, self.opened, self.urls, _ = make_ctx()

    def run_text(self, text):
        resolved, errors = interpret(text, self.ctx)
        self.assertEqual(errors, [], text)
        execute(resolved, self.ctx, confirm=lambda q: True)
        return resolved[0]

    def test_music_goes_to_youtube_search(self):
        for text, query in [("เปิดเพลงซิลิฟูให้หน่อย", "ซิลิฟู"), ("เล่นเพลง lofi", "lofi"),
                            ("ฟังเพลงบอดี้สแลม", "บอดี้สแลม"), ("play shape of you", "shape of you")]:
            with self.subTest(text=text):
                item = self.run_text(text)
                self.assertEqual((item.action.name, item.action.args["query"]), ("play_music", query))
        self.assertTrue(all(u.startswith("https://www.youtube.com/results?search_query=") for u in self.urls))

    def test_music_plays_first_video_when_found(self):
        self.ctx.find_video = lambda query: "Wk2BPFVzvlQ"
        self.run_text("เปิดเพลงขี้หึงของซิลลี่ฟูล")
        self.assertEqual(self.urls[-1], "https://www.youtube.com/watch?v=Wk2BPFVzvlQ")

    def test_find_first_video_parsing(self):
        from voice import actions

        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def read(self, _limit):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        page = (b'..."adSlotRenderer":{"videoId":"AAAAAAAAAAA"}..."reelItemRenderer":{"videoId":"BBBBBBBBBBB"}'
                b'..."videoRenderer":{"videoId":"Wk2BPFVzvlQ","thumbnail":...')
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(page)):
            self.assertEqual(actions.find_first_video("x"), "Wk2BPFVzvlQ")   # skips ads/shorts
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"<html>changed</html>")):
            self.assertIsNone(actions.find_first_video("x"))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(actions.find_first_video("x"))

    def test_known_folders_only(self):
        item = self.run_text("เปิดโฟลเดอร์ดาวน์โหลด")
        self.assertEqual(item.action.args["name"], "Downloads")
        self.assertTrue(os.path.isabs(self.urls[-1]))
        self.assertEqual(self.run_text("open folder documents").action.args["name"], "Documents")
        self.assertEqual(interpret("เปิดโฟลเดอร์ระบบลับ", self.ctx)[0], [])

    def test_settings_whitelist(self):
        for text, uri in [("เปิดตั้งค่าไวไฟ", "ms-settings:network-wifi"),
                          ("ตั้งค่าบลูทูธ", "ms-settings:bluetooth"),
                          ("เปิดการตั้งค่าเสียง", "ms-settings:sound"),
                          ("เปิดตั้งค่า", "ms-settings:")]:
            with self.subTest(text=text):
                self.run_text(text)
                self.assertEqual(self.urls[-1], uri)

    def test_existing_commands_unchanged(self):
        self.assertEqual(self.run_text("เปิดไลน์").action.name, "open_app")
        self.assertEqual(self.run_text("เข้าโหมด work").action.name, "run_mode")
        self.assertEqual(self.run_text("ค้นหาเพลงใหม่").action.name, "web_search")

    def test_picker_fallbacks(self):
        options = picker_options("ซิลิฟู", self.ctx)
        self.assertEqual([o[0] for o in options[-2:]], ["web_search", "play_music"])

        resolved, rejected = apply_pick(("play_music", "ซิลิฟู"), "ซิลิฟู", "เปิดซิลิฟู", self.ctx)
        self.assertEqual((resolved[0].action.name, rejected), ("play_music", []))
        self.assertNotIn("ซิลิฟู", self.ctx.aliases)             # fallbacks are never learned

        resolved, _ = apply_pick(("web_search", "ซิลิฟู"), "ซิลิฟู", "เปิดซิลิฟู", self.ctx)
        self.assertEqual(resolved[0].action.name, "web_search")

        resolved, _ = apply_pick(("app", "LINE"), "ร้าย", "เปิดร้าย", self.ctx)
        self.assertEqual(resolved[0].action.args["name"], "LINE")
        self.assertIn("ร้าย", self.ctx.aliases)

        resolved, rejected = apply_pick(None, "ร้ายๆ", "เปิดร้ายๆ", self.ctx)
        self.assertEqual((resolved, rejected[0].term), ([], "ร้ายๆ"))


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
                database.write_alias(conn, "ร้าย", "LINE", "app")
                database.add_history(conn, "เปิดร้าย", "rule",
                                     [{"name": "open_app", "args": {"name": "LINE"}}], "done")
            with database.connect() as conn:
                self.assertEqual(database.get_setting(conn, "voice_hotkey"), "ctrl+alt+v")
                self.assertEqual(database.read_app_index(conn), {"LINE": "C:/line.exe"})
                self.assertEqual(database.read_aliases(conn)["ร้าย"], ("LINE", "app"))
                [(ts, heard, source, actions, result)] = database.read_history(conn)
                self.assertEqual((heard, result), ("เปิดร้าย", "done"))
                self.assertIn('"LINE"', actions)

        self.assertEqual(version, "2")
        self.assertEqual(aliases["ไลน์"], ("line", "app"))


if __name__ == "__main__":
    unittest.main()

"""Upgrading an existing v2.0 database: new default aliases and one-time app rescan."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from config import database  # noqa: E402
from voice import app_index  # noqa: E402

V20_DEFAULTS = [alias for alias in database.DEFAULT_ALIASES
                if alias not in database.DEFAULT_ALIASES_ADDED[2]]


class TempDBCase(unittest.TestCase):
    """Each test gets its own database file."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "autoh.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    @contextmanager
    def db(self):
        """A fresh connect(), as on the next app start (migrations run again)."""
        with mock.patch.object(database, "get_db_path", return_value=self.path), \
             mock.patch.object(database, "get_base_dir", return_value=self.tmp), \
             mock.patch.object(database, "get_user_data_dir", return_value=self.tmp), \
             mock.patch.object(database, "_initialized_paths", set()):
            with database.connect() as conn:
                yield conn
        conn.close()

    def make_v20_db(self, extra_aliases=()):
        """Database as v2.0 left it: schema 2, v2.0 default aliases, no alias release marker."""
        with self.db() as conn:
            conn.execute("DELETE FROM aliases")
            conn.execute("DELETE FROM meta WHERE key = 'default_aliases_version'")
            for alias in V20_DEFAULTS:
                database.write_alias(conn, alias, *database.DEFAULT_ALIASES[alias])
            for alias, target, kind in extra_aliases:
                database.write_alias(conn, alias, target, kind)

class UpgradeTest(TempDBCase):
    def test_fresh_db_has_all_defaults(self):
        with self.db() as conn:
            aliases = database.read_aliases(conn)
        for alias in database.DEFAULT_ALIASES:
            self.assertIn(alias, aliases)

    def test_v20_db_gets_new_defaults_once(self):
        self.make_v20_db()
        with self.db() as conn:
            self.assertEqual(database.read_aliases(conn)["เครื่องคิดเลข"], ("calculator", "app"))
            database.delete_alias(conn, "เครื่องคิดเลข")          # user removes it
        with self.db() as conn:                                     # next start
            self.assertNotIn("เครื่องคิดเลข", database.read_aliases(conn))

    def test_user_mapping_for_same_words_is_kept(self):
        self.make_v20_db(extra_aliases=[("โน้ตแพด", "Notepad++", "app")])
        with self.db() as conn:
            self.assertEqual(database.read_aliases(conn)["โน้ตแพด"], ("Notepad++", "app"))

    def test_old_app_index_is_rescanned_once(self):
        with self.db() as conn:
            database.write_app_index(conn, [("LINE", "C:/line.exe", "scan")])
            conn.execute("DELETE FROM settings WHERE key = 'app_index_version'")
        scans = []

        def fake_scan(modes=None):
            scans.append(1)
            return [("Notepad", "shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "store")]

        with mock.patch.object(database, "get_db_path", return_value=self.path), \
             mock.patch.object(app_index, "scan_apps", fake_scan):
            first = app_index.load()
            second = app_index.load()
        self.assertEqual(len(scans), 1)
        self.assertIn("Notepad", first)
        self.assertEqual(first, second)


class DisabledActionsTest(TempDBCase):
    """M2: system commands switched off in Voice Settings."""

    def test_default_none_disabled(self):
        with self.db() as conn:
            self.assertEqual(database.read_disabled_actions(conn), set())

    def test_write_read_round_trip(self):
        with self.db() as conn:
            database.write_disabled_actions(conn, ["shutdown", "restart", "shutdown"])
        with self.db() as conn:
            self.assertEqual(database.read_disabled_actions(conn), {"shutdown", "restart"})

    def test_corrupt_value_means_none_disabled(self):
        with self.db() as conn:
            database.set_setting(conn, "disabled_actions", "{not json")
            self.assertEqual(database.read_disabled_actions(conn), set())

    def test_export_and_import(self):
        with self.db() as conn:
            database.write_disabled_actions(conn, ["sleep"])
            exported = database.read_voice(conn)
        self.assertEqual(exported["settings"]["disabled_actions"], '["sleep"]')
        voice = database.normalize_voice(exported)
        self.assertEqual(voice["settings"]["disabled_actions"], '["sleep"]')
        # a hand-edited file with a real JSON list is accepted too
        voice = database.normalize_voice({"settings": {"disabled_actions": ["restart"]}})
        self.assertEqual(voice["settings"]["disabled_actions"], '["restart"]')

    def test_import_rejects_bad_value(self):
        for bad in ("shutdown", '{"a": 1}', "[1, 2]"):
            with self.assertRaises(ValueError, msg=bad):
                database.normalize_voice({"settings": {"disabled_actions": bad}})

    def test_reload_applies_to_commands(self):
        from voice.controller import VoiceAssistant
        from voice.pipeline import interpret_detail

        with self.db() as conn:
            database.write_disabled_actions(conn, ["shutdown"])
        ui = mock.Mock()
        assistant = VoiceAssistant(ui, transcriber=mock.Mock(), recorder=mock.Mock())
        with mock.patch.object(database, "get_db_path", return_value=self.path), \
             mock.patch.object(app_index, "load", return_value={}):
            assistant.reload({})
        self.assertEqual(assistant.ctx.disabled, {"shutdown"})
        resolved, [rejected] = interpret_detail("ปิดเครื่อง", assistant.ctx)
        self.assertEqual(resolved, [])
        self.assertIn('"ปิดเครื่อง" ถูกปิดใช้', str(rejected))


if __name__ == "__main__":
    unittest.main()

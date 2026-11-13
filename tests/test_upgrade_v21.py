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


class UpgradeTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

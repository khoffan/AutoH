"""M5: voice settings, alias management, JSON import/export of voice data (temp DB)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from config import database, load_config  # noqa: E402
from voice.controller import VoiceAssistant, validate_voice_hotkey  # noqa: E402


class TempDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        path = os.path.join(self.tmp, "autoh.db")
        self.patches = [
            mock.patch.object(database, "get_db_path", return_value=path),
            mock.patch.object(database, "get_base_dir", return_value=self.tmp),
            mock.patch.object(database, "get_user_data_dir", return_value=self.tmp),
            mock.patch.object(database, "_initialized_paths", set()),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()


class NormalizeVoiceTest(unittest.TestCase):
    def test_valid_and_missing(self):
        self.assertEqual(database.normalize_voice(None), {"aliases": {}, "settings": {}})
        voice = database.normalize_voice({
            "aliases": {" ร้าย ": {"target": "LINE", "kind": "app"}},
            "settings": {"voice_hotkey": "ctrl+alt+v", "voice_enabled": "0"},
        })
        self.assertEqual(voice["aliases"], {"ร้าย": ("LINE", "app")})
        self.assertEqual(voice["settings"]["voice_enabled"], "0")

    def test_rejects_bad_data(self):
        bad = [
            "not an object",
            {"aliases": {"x": "LINE"}},
            {"aliases": {"xx": {"target": "", "kind": "app"}}},
            {"aliases": {"xx": {"target": "LINE", "kind": "shell"}}},
            {"settings": {"api_key": "secret"}},          # only whitelisted settings travel
        ]
        for data in bad:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    database.normalize_voice(data)


class ImportExportTest(TempDB):
    def test_round_trip_includes_voice(self):
        self.assertTrue(load_config.save_modes({"work": {"hotkey": "ctrl+alt+t", "apps": {}}}))
        with database.connect() as conn:
            database.write_alias(conn, "ร้าย", "LINE", "app")
            database.set_setting(conn, "voice_hotkey", "ctrl+shift+space")
            database.set_setting(conn, "unrelated", "stays local")
        out = os.path.join(self.tmp, "export.json")
        load_config.export_config(out)

        data = json.load(open(out, encoding="utf-8"))
        self.assertIn("work", data["modes"])
        self.assertEqual(data["voice"]["aliases"]["ร้าย"], {"target": "LINE", "kind": "app"})
        self.assertEqual(data["voice"]["settings"], {"voice_hotkey": "ctrl+shift+space"})

        modes, voice = load_config.read_import_bundle(out)
        self.assertIn("work", modes)
        self.assertEqual(voice["aliases"]["ร้าย"], ("LINE", "app"))

    def test_old_files_without_voice_still_import(self):
        path = os.path.join(self.tmp, "old.json")
        json.dump({"modes": {"work": {"hotkey": "ctrl+alt+t", "apps": {}}}}, open(path, "w", encoding="utf-8"))
        modes, voice = load_config.read_import_bundle(path)
        self.assertIn("work", modes)
        self.assertEqual(voice, {"aliases": {}, "settings": {}})
        self.assertEqual(load_config.read_import_file(path), modes)

    def test_save_voice_merges(self):
        with database.connect() as conn:
            database.write_alias(conn, "เก่า", "LINE", "app")
        self.assertTrue(load_config.save_voice({"aliases": {"ใหม่": ("youtube", "site")},
                                                "settings": {"voice_enabled": "0"}}))
        with database.connect() as conn:
            aliases = database.read_aliases(conn)
            self.assertEqual(database.get_setting(conn, "voice_enabled"), "0")
        self.assertIn("เก่า", aliases)
        self.assertEqual(aliases["ใหม่"], ("youtube", "site"))

    def test_delete_alias(self):
        with database.connect() as conn:
            database.write_alias(conn, "bpber ให้", "Windows Media Player Legacy", "app")
            self.assertTrue(database.delete_alias(conn, "bpber ให้"))
            self.assertFalse(database.delete_alias(conn, "bpber ให้"))


class VoiceSettingsTest(TempDB):
    def test_enable_and_hotkey_persist(self):
        self.assertTrue(VoiceAssistant.enabled())
        self.assertEqual(VoiceAssistant.hotkey(), "ctrl+alt+v")
        self.assertTrue(VoiceAssistant.save_settings(False, "ctrl+shift+space"))
        self.assertFalse(VoiceAssistant.enabled())
        self.assertEqual(VoiceAssistant.hotkey(), "ctrl+shift+space")

    def test_validate_hotkey(self):
        taken = {"ctrl+alt+s", "ctrl+alt+q", "ctrl+alt+t"}
        self.assertIsNone(validate_voice_hotkey("ctrl+alt+v", taken))
        self.assertIsNone(validate_voice_hotkey("ctrl+shift+space", taken))
        for bad in ("", "v", "ctrl+alt", "ctrl+alt+q", "CTRL+ALT+T", "ctrl+notakey"):
            with self.subTest(hotkey=bad):
                self.assertIsNotNone(validate_voice_hotkey(bad, taken))


if __name__ == "__main__":
    unittest.main()

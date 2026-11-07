"""VoiceAssistant end to end with fakes: no mic, no model, no Tk, temp database."""
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from config import database  # noqa: E402
from voice import controller as ctrl  # noqa: E402
from voice.controller import VoiceAssistant, VoiceUI  # noqa: E402
from voice.transcriber import TranscriberUnavailable  # noqa: E402

APPS = {"LINE": r"C:\line.exe", "Google Chrome": r"C:\chrome.exe", "MongoDB Compass": r"C:\c.exe"}
MODES = {"work": {"hotkey": "ctrl+alt+t", "apps": {}}}


class FakeTranscriber:
    def __init__(self, text="", error=None):
        self.text, self.error = text, error

    def warm_up(self):
        pass

    def transcribe(self, audio):
        if self.error:
            raise TranscriberUnavailable(self.error)
        return self.text


class FakeRecorder:
    def __init__(self, seconds=1.0):
        self.is_recording, self.seconds = False, seconds

    def start(self):
        self.is_recording = True

    def stop(self):
        self.is_recording = False
        return np.zeros(int(self.seconds * 16000), np.float32)


class ControllerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "autoh.db")
        self.patches = [
            mock.patch.object(database, "get_db_path", return_value=path),
            mock.patch.object(database, "get_base_dir", return_value=tmp),
            mock.patch.object(database, "get_user_data_dir", return_value=tmp),
            mock.patch.object(database, "_initialized_paths", set()),
            mock.patch.object(ctrl.app_index, "load", return_value=dict(APPS)),
            mock.patch.object(ctrl, "write_log"),
        ]
        for p in self.patches:
            p.start()
        self.shown, self.confirms, self.picks, self.modes_run, self.opened = [], [], [], [], []
        self.confirm_answer, self.pick_answer = True, None

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def make(self, text="", error=None, seconds=1.0):
        ui = VoiceUI(
            ui_call=lambda func, *args: func(*args),      # run "UI thread" work inline
            show=lambda text, ms=None: self.shown.append(text),
            confirm=lambda q: self.confirms.append(q) or self.confirm_answer,
            pick=lambda heard, options: self.picks.append((heard, options)) or self.pick_answer,
            run_mode=self.modes_run.append,
        )
        va = VoiceAssistant(ui, transcriber=FakeTranscriber(text, error), recorder=FakeRecorder(seconds))
        va.reload(MODES)
        va.ctx.open_app = lambda path, name: self.opened.append(name)
        va.ctx.open_url = lambda url: self.opened.append(url)
        return va

    def speak(self, va):
        self.assertTrue(va.begin())
        va.end()
        # transcription thread -> ui_call inline; wait for it
        for t in list(__import__("threading").enumerate()):
            if t.daemon and t is not __import__("threading").current_thread():
                t.join(timeout=5)

    def history(self):
        with database.connect() as conn:
            return database.read_history(conn)

    def test_open_app_by_voice(self):
        va = self.make("เปิดไลน์")
        self.speak(va)
        self.assertEqual(self.opened, ["LINE"])
        self.assertFalse(va.busy)
        self.assertIn("✓", self.shown[-1])
        self.assertEqual(self.history()[0][4], "done")

    def test_uncertain_name_confirmed_is_learned_and_saved(self):
        va = self.make("เปิด มงโกดีบี คอมพาส")
        self.speak(va)
        self.assertEqual(len(self.confirms), 1)
        self.assertEqual(self.opened, ["MongoDB Compass"])
        with database.connect() as conn:
            self.assertEqual(database.read_aliases(conn)["มงโกดีบี คอมพาส"], ("MongoDB Compass", "app"))

    def test_unknown_name_pick_then_run(self):
        self.pick_answer = ("app", "LINE")
        va = self.make("เปิดร้าย")
        self.speak(va)
        self.assertEqual(self.picks[0][0], "ร้าย")
        self.assertEqual(self.opened, ["LINE"])
        with database.connect() as conn:
            self.assertEqual(database.read_aliases(conn)["ร้าย"], ("LINE", "app"))

    def test_unknown_name_pick_cancelled(self):
        va = self.make("เปิดร้าย")
        self.speak(va)
        self.assertEqual(self.opened, [])
        self.assertIn("✗", self.shown[-1])
        self.assertEqual(self.history()[0][4], "rejected")

    def test_run_mode_and_blocked_mode(self):
        va = self.make("เข้าโหมด work")
        self.speak(va)
        self.assertEqual(self.modes_run, ["work"])

        def blocked(name):
            raise RuntimeError("เปิด mode ไปแล้ว")
        va.ctx.run_mode = blocked
        self.speak(va)
        self.assertIn("เปิด mode ไปแล้ว", self.shown[-1])
        self.assertEqual(self.history()[0][4], "error")

    def test_cancelled_confirm_runs_nothing(self):
        self.confirm_answer = False
        va = self.make("เปิด crome")
        self.speak(va)
        self.assertEqual(self.opened, [])
        self.assertIn("ยกเลิก", self.shown[-1])

    def test_silence_and_short_press(self):
        va = self.make("")
        self.speak(va)
        self.assertIn("ไม่ได้ยิน", self.shown[-1])
        va = self.make("เปิดไลน์", seconds=0.1)
        va.begin()
        va.end()
        self.assertIn("สั้นเกินไป", self.shown[-1])
        self.assertEqual(self.opened, [])

    def test_model_missing_disables_voice(self):
        va = self.make(error="ไม่พบไฟล์ model เสียง")
        self.assertFalse(va.begin())
        self.assertIn("ไม่พบไฟล์ model", self.shown[-1])
        self.assertTrue(va.status.startswith("off"))

    def test_hotkey_setting(self):
        self.assertEqual(VoiceAssistant.hotkey(), "ctrl+alt+v")
        with database.connect() as conn:
            database.set_setting(conn, "voice_hotkey", "ctrl+shift+space")
        self.assertEqual(VoiceAssistant.hotkey(), "ctrl+shift+space")


if __name__ == "__main__":
    unittest.main()

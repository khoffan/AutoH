"""Glue between push-to-talk, speech-to-text and the command pipeline.

UI-agnostic: the Tk app passes callbacks. Threading:
- begin()/end() and handle_text() run on the UI thread.
- Transcription runs on a worker thread; the result comes back via `ui_call`.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Callable

from config import database
from core.logger import write_log
from voice import app_index
from voice.actions import ActionContext
from voice.pipeline import execute, history_record, interpret_detail, learn_alias
from voice.recorder import PushToTalkRecorder, RecorderError
from voice.transcriber import Transcriber, TranscriberUnavailable
from voice.validate import suggest

DEFAULT_HOTKEY = "ctrl+alt+v"
MIN_AUDIO_SECONDS = 0.3


@dataclass
class VoiceUI:
    ui_call: Callable[..., None]                         # run func(*args) on the UI thread
    show: Callable[[str, int | None], None]              # toast text, hide after ms (None = keep)
    confirm: Callable[[str], bool]                       # yes/no, False on timeout
    pick: Callable[[str, list], tuple[str, str] | None]  # (heard, options) -> (kind, name)
    run_mode: Callable[[str], None]                      # raises RuntimeError if blocked


class VoiceAssistant:
    def __init__(self, ui: VoiceUI, transcriber=None, recorder=None):
        self.ui = ui
        self.transcriber = transcriber or Transcriber()
        self.recorder = recorder or PushToTalkRecorder()
        self.ctx = ActionContext(apps={}, modes={}, aliases={})
        self.busy = False

    # ------------------------------------------------------------ setup

    @staticmethod
    def hotkey() -> str:
        try:
            with database.connect() as conn:
                return database.get_setting(conn, "voice_hotkey", DEFAULT_HOTKEY) or DEFAULT_HOTKEY
        except sqlite3.Error:
            return DEFAULT_HOTKEY

    def start(self) -> None:
        """Load the speech model in the background (~3s); reload() builds the context."""
        self.transcriber.warm_up()

    def reload(self, modes: dict) -> None:
        apps = dict(app_index.load(modes))
        for settings in modes.values():               # mode apps are always known
            apps.update({name: path for name, path in settings.get("apps", {}).items() if path})
        try:
            with database.connect() as conn:
                aliases = database.read_aliases(conn)
        except sqlite3.Error:
            aliases = dict(database.DEFAULT_ALIASES)
        self.ctx.apps, self.ctx.modes, self.ctx.aliases = apps, modes, aliases
        self.ctx.run_mode = self.ui.run_mode

    @property
    def status(self) -> str:
        if self.transcriber.error:
            return f"off ({self.transcriber.error})"
        return "ready"

    # ------------------------------------------------------------ push-to-talk

    def begin(self) -> bool:
        """Key down. Returns False if voice cannot start now."""
        if self.busy or self.recorder.is_recording:
            return False
        if self.transcriber.error:
            self.ui.show(f"สั่งด้วยเสียงไม่ได้: {self.transcriber.error}", 5000)
            return False
        try:
            self.recorder.start()
        except RecorderError as exc:
            self.ui.show(str(exc), 5000)
            write_log(f"Voice: {exc}", "WARN")
            return False
        self.ui.show("🎙 กำลังฟัง... ปล่อยปุ่มเมื่อพูดจบ", None)
        return True

    def end(self) -> None:
        """Key up: stop recording and transcribe in the background."""
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if len(audio) < MIN_AUDIO_SECONDS * 16000:
            self.ui.show("สั้นเกินไป กดค้างแล้วพูด", 2500)
            return
        self.busy = True
        self.ui.show("กำลังแปลงเสียง...", None)
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    def _transcribe(self, audio) -> None:
        try:
            text = self.transcriber.transcribe(audio)
        except TranscriberUnavailable as exc:
            self.ui.ui_call(self._finish, f"สั่งด้วยเสียงไม่ได้: {exc}")
            return
        except Exception as exc:
            write_log(f"Voice transcribe error: {exc}", "ERROR")
            self.ui.ui_call(self._finish, "แปลงเสียงไม่สำเร็จ")
            return
        self.ui.ui_call(self.handle_text, text)

    def _finish(self, message: str) -> None:
        self.busy = False
        self.ui.show(message, 4000)

    # ------------------------------------------------------------ commands

    def handle_text(self, text: str) -> None:
        """UI thread: text -> (pick) -> (confirm) -> run -> history."""
        try:
            if not text:
                self._finish("ไม่ได้ยินเสียงพูด")
                return
            self.ui.show(f"ได้ยิน: \"{text}\"", None)
            resolved, rejected = interpret_detail(text, self.ctx)

            for exc in rejected:   # unknown name: let the user pick, learn, retry once
                if exc.term:
                    choice = self.ui.pick(exc.term, suggest(exc.term, self.ctx))
                    if choice and learn_alias(exc.term, choice[0], choice[1], self.ctx, _save_alias):
                        resolved, rejected = interpret_detail(text, self.ctx)
                    break

            results = execute(resolved, self.ctx, self.ui.confirm, save_alias=_save_alias)
            self._record(text, resolved, results)
            self._finish(_summary(text, resolved, rejected, results))
        except Exception as exc:   # never leave the assistant stuck in busy
            write_log(f"Voice handle error: {exc}", "ERROR")
            self._finish("เกิดข้อผิดพลาด ดู log")

    def _record(self, text, resolved, results) -> None:
        source, actions, result = history_record(resolved, results)
        try:
            with database.connect() as conn:
                database.add_history(conn, text, source, actions, result)
        except sqlite3.Error as exc:
            print(f"Cannot save command history: {exc}")
        write_log(f"Voice heard=\"{text}\" -> {result} {[a['name'] for a in actions]}", "VOICE")


def _save_alias(alias: str, target: str, kind: str) -> None:
    try:
        with database.connect() as conn:
            database.write_alias(conn, alias, target, kind)
        write_log(f"Voice learned alias \"{alias}\" -> {target} ({kind})", "VOICE")
    except sqlite3.Error as exc:
        print(f"Cannot save alias: {exc}")


def _summary(text, resolved, rejected, results) -> str:
    if not resolved:
        return f"✗ {rejected[0]}" if rejected else f"✗ ไม่เข้าใจ \"{text}\""
    lines = []
    for item, outcome in results:
        if outcome == "cancelled":
            lines.append(f"– ยกเลิก: {item.label}")
        elif outcome.startswith("error"):
            lines.append(f"✗ {item.label}: {outcome[len('error: '):]}")
        else:
            lines.append(f"✓ {item.label}")
    return "\n".join(lines)

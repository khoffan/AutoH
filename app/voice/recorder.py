"""Push-to-talk microphone recorder: start() on key down, stop() on key up.

Audio stays in memory only; nothing is written to disk. Recording stops by
itself after MAX_SECONDS so a stuck key cannot keep the microphone open.
"""
from __future__ import annotations

import threading
import time

SAMPLE_RATE = 16000
MAX_SECONDS = 10


class RecorderError(Exception):
    """No microphone / permission denied. Message is user-facing."""


class PushToTalkRecorder:
    def __init__(self, stream_factory=None, max_seconds: float = MAX_SECONDS):
        """`stream_factory(callback)` returns a started-able input stream (injectable for tests)."""
        self._stream_factory = stream_factory or _sounddevice_stream
        self._max_seconds = max_seconds
        self._chunks: list = []
        self._stream = None
        self._started_at = 0.0
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            # Set before start(): the audio callback can fire immediately and would
            # otherwise see a stale start time and drop the first syllable.
            self._started_at = time.monotonic()
            try:
                stream = self._stream_factory(self._on_audio)
                stream.start()
            except Exception as exc:
                raise RecorderError(f"เปิดไมโครโฟนไม่ได้: {exc}") from exc
            self._stream = stream

    def _on_audio(self, indata, frames, time_info, status):
        if time.monotonic() - self._started_at <= self._max_seconds:
            self._chunks.append(indata.copy())

    def stop(self):
        """Stop and return float32 mono audio (numpy array, possibly empty)."""
        import numpy as np

        with self._lock:
            stream, self._stream = self._stream, None
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).reshape(-1).astype(np.float32)

    def elapsed(self) -> float:
        return time.monotonic() - self._started_at if self._stream is not None else 0.0


def _sounddevice_stream(callback):
    import sounddevice as sd

    return sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback)

"""Speech-to-text with Typhoon ASR Real-Time (ONNX, offline, CPU).

Model files are looked up like the database: next to the exe/project first
(portable), then %LOCALAPPDATA%\\AutoH\\models. int8 files are preferred when
present. Missing model = voice disabled; the rest of the app keeps working.
"""
from __future__ import annotations

import os
import threading

from config.get_base_dir import get_base_dir, get_user_data_dir

MODEL_NAME = "typhoon-asr-realtime"
SAMPLE_RATE = 16000
_ENCODER = "encoder-fastconformer-quran-ar{suffix}.onnx"
_DECODER = "decoder_joint-fastconformer-quran-ar{suffix}.onnx"
_VOCAB = "vocab.json"


class TranscriberUnavailable(Exception):
    """Model files or runtime missing. Message is user-facing."""


def find_model_files(dirs: list[str] | None = None) -> tuple[str, str, str] | None:
    """(encoder, decoder, vocab) paths, int8 preferred, or None."""
    if dirs is None:
        dirs = [os.path.join(root, "models", MODEL_NAME) for root in (get_base_dir(), get_user_data_dir())]
    for folder in dirs:
        vocab = os.path.join(folder, _VOCAB)
        if not os.path.isfile(vocab):
            continue
        for suffix in ("-int8", ""):
            encoder = os.path.join(folder, _ENCODER.format(suffix=suffix))
            decoder = os.path.join(folder, _DECODER.format(suffix=suffix))
            if os.path.isfile(encoder) and os.path.isfile(decoder):
                return encoder, decoder, vocab
    return None


class Transcriber:
    """Thread-safe, lazily loaded. Call warm_up() at startup to load in the background."""

    def __init__(self, files: tuple[str, str, str] | None = None):
        self._files = files
        self._model = None
        self._error: str | None = None
        self._lock = threading.Lock()

    @property
    def error(self) -> str | None:
        return self._error

    def _load(self):
        if self._model is not None:
            return self._model
        if self._error is not None:
            raise TranscriberUnavailable(self._error)
        files = self._files or find_model_files()
        if files is None:
            self._error = f"ไม่พบไฟล์ model เสียง (models/{MODEL_NAME})"
            raise TranscriberUnavailable(self._error)
        try:
            from pythaiasr.typhoon import FastConformerRNNT

            encoder, decoder, vocab = files
            self._model = FastConformerRNNT(
                encoder_path=encoder, decoder_path=decoder, vocab_path=vocab, device="cpu"
            )
        except Exception as exc:  # ImportError, onnxruntime errors, corrupt file
            self._error = f"โหลด model เสียงไม่ได้: {exc}"
            raise TranscriberUnavailable(self._error) from exc
        return self._model

    def warm_up(self) -> threading.Thread:
        def run():
            try:
                with self._lock:
                    self._load()
            except TranscriberUnavailable:
                pass
        thread = threading.Thread(target=run, name="transcriber-warmup", daemon=True)
        thread.start()
        return thread

    def transcribe(self, audio) -> str:
        """float32 mono 16 kHz numpy array -> text ("" for silence)."""
        if audio is None or len(audio) < SAMPLE_RATE * 0.2:
            return ""
        with self._lock:
            model = self._load()
            return (model.transcribe(audio) or "").strip()

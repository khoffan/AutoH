import os
import sys
import tempfile
import unittest
import wave

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "app"))

from voice.recorder import PushToTalkRecorder, RecorderError  # noqa: E402
from voice.transcriber import Transcriber, TranscriberUnavailable, find_model_files  # noqa: E402

BENCH_WAV = os.path.join(ROOT, "bench", "audio", "14.wav")   # "ค้นหาราคาทอง"


class FakeStream:
    def __init__(self, callback, chunks):
        self.callback, self.chunks, self.closed = callback, chunks, False

    def start(self):
        for chunk in self.chunks:
            self.callback(chunk.reshape(-1, 1), len(chunk), None, None)

    def stop(self):
        pass

    def close(self):
        self.closed = True


class RecorderTest(unittest.TestCase):
    def test_collects_audio_in_memory(self):
        chunks = [np.full(1600, 0.1, dtype=np.float32), np.full(1600, 0.2, dtype=np.float32)]
        streams = []
        rec = PushToTalkRecorder(lambda cb: streams.append(FakeStream(cb, chunks)) or streams[-1])
        rec.start()
        self.assertTrue(rec.is_recording)
        audio = rec.stop()
        self.assertFalse(rec.is_recording)
        self.assertEqual(audio.shape, (3200,))
        self.assertEqual(audio.dtype, np.float32)
        self.assertTrue(streams[0].closed)

    def test_stop_without_start_is_empty(self):
        self.assertEqual(len(PushToTalkRecorder(lambda cb: None).stop()), 0)

    def test_max_seconds_drops_late_audio(self):
        rec = PushToTalkRecorder(lambda cb: FakeStream(cb, [np.ones(10, np.float32)]), max_seconds=-1)
        rec.start()
        self.assertEqual(len(rec.stop()), 0)

    def test_no_microphone(self):
        def broken(cb):
            raise OSError("Error querying device -1")
        with self.assertRaises(RecorderError):
            PushToTalkRecorder(broken).start()


class TranscriberTest(unittest.TestCase):
    def test_missing_model_is_reported_not_crashing(self):
        empty = tempfile.mkdtemp()
        self.assertIsNone(find_model_files([empty]))
        t = Transcriber(files=None)
        t._files = None
        import voice.transcriber as mod
        original = mod.find_model_files
        mod.find_model_files = lambda dirs=None: None
        try:
            with self.assertRaises(TranscriberUnavailable):
                t.transcribe(np.zeros(16000, np.float32))
            self.assertIn("model", t.error)
            t.warm_up().join()   # must not raise either
        finally:
            mod.find_model_files = original

    def test_prefers_int8(self):
        folder = tempfile.mkdtemp()
        for name in ("vocab.json", "encoder-fastconformer-quran-ar.onnx",
                     "decoder_joint-fastconformer-quran-ar.onnx",
                     "encoder-fastconformer-quran-ar-int8.onnx",
                     "decoder_joint-fastconformer-quran-ar-int8.onnx"):
            open(os.path.join(folder, name), "w").close()
        encoder, decoder, _ = find_model_files([folder])
        self.assertTrue(encoder.endswith("-int8.onnx") and decoder.endswith("-int8.onnx"))

    def test_silence_is_empty_text(self):
        self.assertEqual(Transcriber(files=("x", "y", "z")).transcribe(np.zeros(100, np.float32)), "")

    @unittest.skipUnless(find_model_files() and os.path.isfile(BENCH_WAV),
                         "needs models/typhoon-asr-realtime and bench/audio recordings")
    def test_real_model_on_recording(self):
        with wave.open(BENCH_WAV, "rb") as f:
            audio = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
        t = Transcriber()
        t.warm_up().join()
        self.assertIsNone(t.error)
        self.assertIn("ราคา", t.transcribe(audio))


if __name__ == "__main__":
    unittest.main()

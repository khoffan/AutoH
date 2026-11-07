"""M1 spike: record test sentences, then benchmark Whisper models on them.

Measures what matters for AutoH: did the spoken sentence end up as the right
action? (not word error rate). See docs/plans/v2.0-voice-commands.md, M1.

    venv\\Scripts\\python.exe scripts\\stt_bench.py record              # read 20 sentences aloud
    venv\\Scripts\\python.exe scripts\\stt_bench.py bench               # base + small
    venv\\Scripts\\python.exe scripts\\stt_bench.py bench --models tiny,base,small,medium
    venv\\Scripts\\python.exe scripts\\stt_bench.py bench --no-prompt   # without app-name hint
    venv\\Scripts\\python.exe scripts\\stt_bench.py bench --models typhoon       # offline, models/typhoon-asr-realtime
    $env:TYPHOON_API_KEY="..."; venv\\Scripts\\python.exe scripts\\stt_bench.py bench --models typhoon-api

Whisper models download from Hugging Face on first use (base ~150 MB, small ~500 MB).
"typhoon" needs the ONNX files in models/typhoon-asr-realtime/ (see SOURCE.txt there).
Recordings are saved to bench/audio/ (git-ignored); delete them any time.
"""
import argparse
import os
import sys
import threading
import time
import wave

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "app"))
AUDIO_DIR = os.path.join(ROOT, "bench", "audio")
SAMPLE_RATE = 16000
MAX_SECONDS = 10

# (sentence to read, expected action, expected target or search substring)
SENTENCES = [
    ("เปิดไลน์", "open_app", "LINE"),
    ("เปิดโครม", "open_app", "Google Chrome"),
    ("เปิด MongoDB Compass", "open_app", "MongoDB Compass"),
    ("เปิดดิสคอร์ด", "open_app", "Discord"),
    ("เปิด Docker Desktop", "open_app", "Docker Desktop"),
    ("เปิดแคนวา", "open_app", "Canva"),
    ("เปิด Microsoft Edge", "open_app", "Microsoft Edge"),
    ("เปิด WinRAR", "open_app", "WinRAR 7.13 (64-bit)"),
    ("เปิดไลน์ให้หน่อยครับ", "open_app", "LINE"),
    ("open chrome", "open_app", "Google Chrome"),
    ("เปิดยูทูบ", "open_url", "youtube"),
    ("เปิดเว็บ GitHub", "open_url", "github"),
    ("เปิดจีเมล", "open_url", "gmail"),
    ("เปิดเฟซบุ๊ก", "open_url", "facebook"),
    ("ค้นหาราคาทอง", "web_search", "ราคาทอง"),
    ("ค้นหาสภาพอากาศวันนี้", "web_search", "สภาพอากาศ"),
    ("ค้นหาร้านกาแฟใกล้ฉัน", "web_search", "ร้านกาแฟ"),
    ("search python tutorial", "web_search", "python"),
    ("เข้าโหมด work", "run_mode", "work"),
    ("โหมด work", "run_mode", "work"),
]


def wav_path(i):
    return os.path.join(AUDIO_DIR, f"{i:02d}.wav")


# ---------------------------------------------------------------- record

def record_one() -> bytes:
    """Record from Enter to Enter (max MAX_SECONDS). Returns int16 mono PCM."""
    import sounddevice as sd

    chunks, stop = [], threading.Event()

    def callback(indata, frames, t, status):
        chunks.append(bytes(indata))

    input("   Enter = start ")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        print("   ● recording... Enter = stop")
        waiter = threading.Thread(target=lambda: (input(), stop.set()), daemon=True)
        waiter.start()
        stop.wait(MAX_SECONDS)
    return b"".join(chunks)


def cmd_record(only=None):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    print("Read each sentence naturally, as you would give a real command.\n")
    for i, (sentence, _, _) in enumerate(SENTENCES):
        if only is not None and i not in only:
            continue
        while True:
            print(f"[{i + 1:02d}/{len(SENTENCES)}]  {sentence}")
            pcm = record_one()
            seconds = len(pcm) / 2 / SAMPLE_RATE
            if seconds >= 0.3:
                break
            print("   too short, again")
        with wave.open(wav_path(i), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(pcm)
        print(f"   saved {seconds:.1f}s\n")
    print(f"Done. Files in {AUDIO_DIR}")


# ---------------------------------------------------------------- bench

def load_audio(path):
    """WAV (16 kHz int16 mono) -> float32 array. Avoids faster-whisper's PyAV decoder."""
    import numpy as np

    with wave.open(path, "rb") as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path}: expected 16 kHz mono 16-bit")
        pcm = f.readframes(f.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def build_context():
    from config.database import DEFAULT_ALIASES
    from voice.actions import ActionContext
    from voice.app_index import scan_apps

    apps = {name: path for name, path, _ in scan_apps()}
    return ActionContext(apps=apps, modes={"work": {}}, aliases=dict(DEFAULT_ALIASES))


def hint_prompt(ctx) -> str:
    """Names Whisper should spell correctly (plan: initial_prompt)."""
    names = list(ctx.apps) + list(ctx.sites) + list(ctx.modes)
    return "คำสั่ง: เปิด, ค้นหา, โหมด. " + ", ".join(names)


def check(text, ctx, expected_action, expected_target):
    from voice.matching import normalize
    from voice.pipeline import interpret

    resolved, errors = interpret(text, ctx)
    if not resolved:
        return False, errors[0] if errors else "no action"
    action = resolved[0].action
    if action.name != expected_action:
        return False, f"{action.name}({action.args})"
    if action.name == "web_search":
        ok = normalize(expected_target).replace(" ", "") in normalize(action.args["query"]).replace(" ", "")
    else:
        ok = expected_target in (action.args.get("name"), action.args.get("site"))
    label = resolved[0].label + (" [ask]" if resolved[0].needs_confirm else "")
    return ok, label


TYPHOON_URL = "https://api.opentyphoon.ai/v1/audio/transcriptions"


class TyphoonAPI:
    """Typhoon ASR hosted API (OpenAI-compatible). Key from TYPHOON_API_KEY; never stored."""

    def __init__(self, model="typhoon-asr-realtime"):
        self.key = os.environ.get("TYPHOON_API_KEY")
        if not self.key:
            sys.exit("Set TYPHOON_API_KEY first (free key from the Typhoon playground, see https://docs.opentyphoon.ai)")
        self.model = model

    def transcribe(self, path) -> str:
        import json
        import urllib.request
        import uuid

        boundary = uuid.uuid4().hex
        with open(path, "rb") as f:
            audio = f.read()
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self.model}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode() + audio + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(TYPHOON_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response).get("text", "")


TYPHOON_DIR = os.path.join(ROOT, "models", "typhoon-asr-realtime")


class TyphoonLocal:
    """Typhoon ASR Real-Time, offline via ONNX Runtime (pythaiasr's FastConformer RNN-T)."""

    def __init__(self, model_dir=TYPHOON_DIR):
        from pythaiasr.typhoon import FastConformerRNNT

        self.model = FastConformerRNNT(
            encoder_path=os.path.join(model_dir, "encoder-fastconformer-quran-ar.onnx"),
            decoder_path=os.path.join(model_dir, "decoder_joint-fastconformer-quran-ar.onnx"),
            vocab_path=os.path.join(model_dir, "vocab.json"),
            device="cpu",
        )

    def transcribe(self, path) -> str:
        return self.model.transcribe(load_audio(path))


def cmd_bench(models, use_prompt):
    files = [(i, s) for i, s in enumerate(SENTENCES) if os.path.isfile(wav_path(i))]
    if not files:
        sys.exit("No recordings. Run: scripts\\stt_bench.py record")

    print("Scanning apps...")
    ctx = build_context()
    prompt = hint_prompt(ctx) if use_prompt else None
    summary = []

    for model_name in models:
        print(f"\n=== {model_name}  (loading, first time downloads) ===")
        t0 = time.perf_counter()
        if model_name == "typhoon-api":
            model = TyphoonAPI()
        elif model_name == "typhoon":
            model = TyphoonLocal()
        else:
            from faster_whisper import WhisperModel

            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        load_s = time.perf_counter() - t0

        passed, times = 0, []
        for i, (sentence, exp_action, exp_target) in files:
            t0 = time.perf_counter()
            if isinstance(model, (TyphoonAPI, TyphoonLocal)):
                text = model.transcribe(wav_path(i)).strip()
            else:
                segments, _ = model.transcribe(
                    load_audio(wav_path(i)), language="th", beam_size=5, initial_prompt=prompt,
                    vad_filter=True, condition_on_previous_text=False,
                )
                text = "".join(seg.text for seg in segments).strip()
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            ok, detail = check(text, ctx, exp_action, exp_target)
            passed += ok
            print(f"{'OK ' if ok else 'BAD'} {elapsed:4.1f}s  {sentence:<24} heard={text!r:<32} -> {detail}")

        avg, worst = sum(times) / len(times), max(times)
        summary.append((model_name, passed, len(files), avg, worst, load_s))
        print(f"--- {model_name}: {passed}/{len(files)} correct, avg {avg:.1f}s, worst {worst:.1f}s, load {load_s:.1f}s")
        del model

    print("\nmodel        correct   avg    worst  load")
    for name, p, n, avg, worst, load in summary:
        print(f"{name:<12} {p:>2}/{n:<2}    {avg:4.1f}s  {worst:4.1f}s  {load:4.1f}s")
    print("\nTarget (plan DoD): >= 90% correct, <= 3s from key release to action.")


def main():
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--only", help="re-record these numbers, e.g. 3,7")
    bench = sub.add_parser("bench")
    bench.add_argument("--models", default="base,small",
                       help="comma list: tiny,base,small,medium,large-v3 or a CTranslate2 model path/repo")
    bench.add_argument("--no-prompt", action="store_true", help="disable app-name initial_prompt")
    opts = parser.parse_args()

    if opts.cmd == "record":
        only = {int(x) - 1 for x in opts.only.split(",")} if opts.only else None
        cmd_record(only)
    else:
        cmd_bench([m.strip() for m in opts.models.split(",") if m.strip()], not opts.no_prompt)


if __name__ == "__main__":
    main()

"""Manual test for voice commands: type a command, or speak with --mic.

    venv\\Scripts\\python.exe scripts\\voice_repl.py            # real actions, no DB
    venv\\Scripts\\python.exe scripts\\voice_repl.py --dry-run  # show only, open nothing
    venv\\Scripts\\python.exe scripts\\voice_repl.py --db       # use autoh.db (modes, aliases, app index)
    venv\\Scripts\\python.exe scripts\\voice_repl.py --mic --dry-run   # Enter = talk, Enter = stop

Without --db nothing is written to disk: apps are scanned live, aliases are the
defaults, and modes are empty. --db opens the real database, which migrates
config.json next to the project root on first run (renamed to config.json.bak).
"""
import argparse
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from voice.actions import ActionContext  # noqa: E402
from voice.pipeline import execute, interpret_detail, learn_alias  # noqa: E402
from voice.validate import suggest  # noqa: E402


def build_context(use_db: bool, dry_run: bool) -> ActionContext:
    if use_db:
        from config import database
        from config.load_config import load_config
        from voice import app_index

        modes = load_config()["modes"]
        apps = app_index.load(modes)
        with database.connect() as conn:
            aliases = database.read_aliases(conn)
    else:
        from config.database import DEFAULT_ALIASES
        from voice.app_index import scan_apps

        modes = {}
        apps = {name: path for name, path, _ in scan_apps()}
        aliases = dict(DEFAULT_ALIASES)

    ctx = ActionContext(apps=apps, modes=modes, aliases=aliases)
    ctx.run_mode = lambda name: print(f"   (run_mode '{name}' is wired in M4; not run here)")
    if dry_run:
        ctx.open_app = lambda path, name: print(f"   [dry-run] open app {name}: {path}")
        ctx.open_url = lambda url: print(f"   [dry-run] open url {url}")
    return ctx


def confirm(question: str) -> bool:
    return input(f"   ? {question} [y/N] ").strip().lower() in ("y", "yes", "ใช่")


def alias_saver(use_db: bool):
    """Learned aliases go to the DB with --db; otherwise they live for this session only."""
    if not use_db:
        return lambda alias, target, kind: print(f"   + จำ \"{alias}\" = {target} (session only)")
    from config import database

    def save(alias, target, kind):
        with database.connect() as conn:
            database.write_alias(conn, alias, target, kind)
        print(f"   + จำ \"{alias}\" = {target} (saved)")
    return save


def pick_and_learn(term: str, ctx: ActionContext, save) -> None:
    options = suggest(term, ctx)
    if not options:
        return
    print(f"   หมายถึงอันไหน? (Enter = ไม่ใช่ทั้งหมด)")
    for n, (kind, name, s) in enumerate(options, 1):
        print(f"     {n}. {name} [{kind}] {s:.2f}")
    choice = input("   เลือก: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        kind, name, _ = options[int(choice) - 1]
        learn_alias(term, kind, name, ctx, save)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", action="store_true", help="use the real autoh.db")
    parser.add_argument("--dry-run", action="store_true", help="do not open anything")
    parser.add_argument("--mic", action="store_true", help="speak instead of typing (Typhoon ASR)")
    opts = parser.parse_args()

    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")

    print("Scanning apps...")
    ctx = build_context(opts.db, opts.dry_run)
    save = alias_saver(opts.db)
    print(f"{len(ctx.apps)} apps, {len(ctx.modes)} modes, {len(ctx.aliases)} aliases.")
    if opts.mic:
        from voice.recorder import PushToTalkRecorder
        from voice.transcriber import Transcriber

        recorder, transcriber = PushToTalkRecorder(), Transcriber()
        transcriber.warm_up().join()
        if transcriber.error:
            sys.exit(transcriber.error)
        print("Enter = start talking, Enter again = stop. Or type a command. 'q' quits.\n")
    else:
        print("Type a command (e.g. เปิดไลน์, เปิดยูทูบ, ค้นหาราคาทอง). ':apps' lists apps, empty line quits.\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if opts.mic and text == "":
            recorder.start()
            input("   ● กำลังฟัง... (Enter = หยุด) ")
            audio = recorder.stop()
            started = time.perf_counter()
            text = transcriber.transcribe(audio)
            print(f"   ได้ยิน: \"{text}\" ({len(audio) / 16000:.1f}s เสียง, "
                  f"แปลง {time.perf_counter() - started:.2f}s)")
            if not text:
                continue
        if not text or text == "q":
            break
        if text == ":apps":
            print("\n".join(f"   {name}" for name in sorted(ctx.apps)))
            continue

        resolved, rejected = interpret_detail(text, ctx)
        for exc in rejected:
            print(f"   x {exc}")
            if exc.term:
                pick_and_learn(exc.term, ctx, save)
        for item in resolved:
            print(f"   -> {item.label} (score {item.score:.2f}"
                  f"{', ต้องยืนยัน' if item.needs_confirm else ''})")
        for item, result in execute(resolved, ctx, confirm, save_alias=save):
            print(f"   = {result}")


if __name__ == "__main__":
    main()

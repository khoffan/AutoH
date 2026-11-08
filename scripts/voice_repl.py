"""Manual test for voice commands: type a command, or speak with --mic.

    venv\\Scripts\\python.exe scripts\\voice_repl.py            # real actions, no DB
    venv\\Scripts\\python.exe scripts\\voice_repl.py --dry-run  # show only, open nothing
    venv\\Scripts\\python.exe scripts\\voice_repl.py --db       # use autoh.db (modes, aliases, app index)
    venv\\Scripts\\python.exe scripts\\voice_repl.py --mic --dry-run   # Enter = talk, Enter = stop

System commands (v2.1 M1): ปิด chrome, เสียง 30, เพิ่มเสียง, ปิดเสียง, ล็อกเครื่อง,
พักเครื่อง, ปิดเครื่อง, รีสตาร์ท. Sleep/shutdown/restart are only simulated unless
--real-power is given; close app, volume and lock are real unless --dry-run.
    --disable shutdown,restart   turn actions off, like the future Settings switch
    --countdown 5                shorter shutdown/restart countdown (default 30 s)

Without --db, modes are empty, aliases are the defaults and learned aliases are
kept for the session only. Real (non --dry-run) launches still write a log line,
which opens the real database. Only --dry-run touches nothing on disk. The real
database migrates config.json from the project root on first use (-> .bak).
"""
import argparse
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from voice.actions import ActionContext  # noqa: E402
from voice.pipeline import apply_pick, execute, interpret_detail, picker_options  # noqa: E402


class FakeSystem:
    """Prints instead of touching the system. `real` handles what is safe to really do."""

    def __init__(self, real=None, simulate=("sleep", "shutdown", "restart")):
        self.real = real
        self.simulate = set(simulate)
        self.volume = 50

    def __getattr__(self, name):
        if self.real is not None and name not in self.simulate:
            return getattr(self.real, name)
        return lambda *args: self._fake(name, *args)

    def _fake(self, name, *args):
        if name == "get_volume":
            return self.volume
        if name == "set_volume":
            self.volume = args[0]
        if name == "running_pids":            # dry-run: pretend every known app is open
            return {0}
        if name == "close_windows":
            print(f"   [dry-run] close windows of pids {sorted(args[0])}")
            return 1
        print(f"   [simulated] {name}{args if args else ''}")
        return None


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
        ctx.open_path = lambda target: print(f"   [dry-run] open {target}")
    return ctx


def countdown_prompt(seconds_override: int | None):
    """Console version of the app's countdown: any key cancels, otherwise it goes ahead."""
    import msvcrt

    def countdown(label: str, seconds: int) -> bool:
        seconds = seconds_override or seconds
        for left in range(seconds, 0, -1):
            print(f"\r   ⏳ {label} ใน {left} วินาที — กดปุ่มใดก็ได้เพื่อยกเลิก ", end="", flush=True)
            for _ in range(10):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                    print("\n   ยกเลิกแล้ว")
                    return False
                time.sleep(0.1)
        print()
        return True
    return countdown


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


def pick(term: str, ctx: ActionContext):
    """Same choices as the app's pick dialog. Returns (kind, name) or None."""
    options = picker_options(term, ctx)
    print("   หมายถึงอันไหน? (Enter = ไม่ใช่ทั้งหมด)")
    for n, (kind, name, s) in enumerate(options, 1):
        if kind == "web_search":
            print(f"     {n}. ค้นหา \"{name}\" ใน Google")
        elif kind == "play_music":
            print(f"     {n}. เล่น \"{name}\" บน YouTube")
        else:
            print(f"     {n}. {name} [{kind}] {s:.2f}")
    choice = input("   เลือก: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        kind, name, _ = options[int(choice) - 1]
        return kind, name
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", action="store_true", help="use the real autoh.db")
    parser.add_argument("--dry-run", action="store_true", help="do not open anything")
    parser.add_argument("--mic", action="store_true", help="speak instead of typing (Typhoon ASR)")
    parser.add_argument("--real-power", action="store_true",
                        help="really sleep / shut down / restart (default: simulated)")
    parser.add_argument("--disable", default="", help="comma-separated actions to turn off")
    parser.add_argument("--countdown", type=int, help="seconds for the shutdown/restart countdown")
    opts = parser.parse_args()

    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")

    print("Scanning apps...")
    ctx = build_context(opts.db, opts.dry_run)
    from voice.system import SystemControl

    if opts.dry_run:
        ctx.system = FakeSystem()
    elif not opts.real_power:
        ctx.system = FakeSystem(real=SystemControl())
    ctx.disabled = {name.strip() for name in opts.disable.split(",") if name.strip()}
    countdown = countdown_prompt(opts.countdown)
    save = alias_saver(opts.db)
    print(f"{len(ctx.apps)} apps, {len(ctx.modes)} modes, {len(ctx.aliases)} aliases.")
    power = "REAL" if opts.real_power and not opts.dry_run else "simulated"
    print(f"sleep/shutdown/restart: {power}"
          + (f", disabled: {', '.join(sorted(ctx.disabled))}" if ctx.disabled else ""))
    if opts.mic:
        from voice.recorder import PushToTalkRecorder
        from voice.transcriber import Transcriber

        recorder, transcriber = PushToTalkRecorder(), Transcriber()
        transcriber.warm_up().join()
        if transcriber.error:
            sys.exit(transcriber.error)
        print("Enter = start talking, Enter again = stop. Or type a command. 'q' quits.\n")
    else:
        print("Type a command (e.g. เปิดไลน์, ปิด chrome, เสียง 30, ล็อกเครื่อง). "
              "':apps' lists apps, empty line quits.\n")

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
                resolved, rejected = apply_pick(pick(exc.term, ctx), exc.term, text, ctx, save)
                break
        for item in resolved:
            print(f"   -> {item.label} (score {item.score:.2f}"
                  f"{', ต้องยืนยัน' if item.needs_confirm else ''})")
        for item, result in execute(resolved, ctx, confirm, save_alias=save, countdown=countdown):
            print(f"   = {result}")


if __name__ == "__main__":
    main()

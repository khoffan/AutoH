"""Build AutoH: tests -> PyInstaller (one-folder) -> copy model -> Inno Setup installer.

    venv\\Scripts\\python.exe scripts\\build.py                # everything
    venv\\Scripts\\python.exe scripts\\build.py --no-installer # exe folder only (dist\\AutoH)
    venv\\Scripts\\python.exe scripts\\build.py --skip-tests

Output: dist\\AutoH\\AutoH.exe and installer-output\\AutoH-Setup-<version>.exe
Needs: models\\typhoon-asr-realtime\\*-int8.onnx (scripts\\quantize_typhoon.py makes them)
       Inno Setup 6 (ISCC.exe) for the installer step.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST = os.path.join(ROOT, "dist", "AutoH")
MODEL_SRC = os.path.join(ROOT, "models", "typhoon-asr-realtime")
MODEL_DST = os.path.join(DIST, "models", "typhoon-asr-realtime")
MODEL_FILES = [  # int8 only: 138 MB instead of 483 MB, same accuracy (M1 bench)
    "encoder-fastconformer-quran-ar-int8.onnx",
    "decoder_joint-fastconformer-quran-ar-int8.onnx",
    "vocab.json",
    "SOURCE.txt",
]
ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
]


def step(title):
    print(f"\n=== {title} ===", flush=True)


def run(cmd, **kw):
    print("> " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def read_version():
    namespace = {}
    with open(os.path.join(ROOT, "app", "version.py"), encoding="utf-8") as f:
        exec(f.read(), namespace)
    return namespace["__version__"]


def check_model():
    missing = [f for f in MODEL_FILES if not os.path.isfile(os.path.join(MODEL_SRC, f))]
    if missing:
        sys.exit(f"Missing model files in {MODEL_SRC}: {missing}\n"
                 f"Download per models/typhoon-asr-realtime/SOURCE.txt, then run scripts\\quantize_typhoon.py")


def copy_extras():
    os.makedirs(MODEL_DST, exist_ok=True)
    for name in MODEL_FILES:
        shutil.copy2(os.path.join(MODEL_SRC, name), MODEL_DST)
    shutil.copy2(os.path.join(ROOT, "installer", "THIRD_PARTY_NOTICES.txt"), DIST)
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(DIST, "LICENSE.txt"))


def folder_size_mb(path):
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(path) for f in files)
    return total / 1e6


def find_iscc(explicit):
    for candidate in ([explicit] if explicit else []) + ISCC_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return shutil.which("ISCC")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--no-installer", action="store_true")
    parser.add_argument("--iscc", help="path to ISCC.exe if not in the default location")
    opts = parser.parse_args()
    started = time.perf_counter()
    version = read_version()
    print(f"AutoH {version}")

    check_model()

    if not opts.skip_tests:
        step("Tests")
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])

    step("PyInstaller (one-folder)")
    run([sys.executable, "-m", "PyInstaller", os.path.join("installer", "AutoH.spec"),
         "--noconfirm", "--clean", "--distpath", "dist", "--workpath", os.path.join("build", "pyinstaller")])

    step("Copy model and notices")
    copy_extras()
    print(f"{DIST}: {folder_size_mb(DIST):.0f} MB")

    if opts.no_installer:
        print(f"\nDone in {time.perf_counter() - started:.0f}s (no installer). Run: {DIST}\\AutoH.exe")
        return

    step("Inno Setup")
    iscc = find_iscc(opts.iscc)
    if not iscc:
        sys.exit("ISCC.exe not found. Install Inno Setup 6 or pass --iscc PATH.")
    run([iscc, f"/DMyAppVersion={version}", os.path.join("installer", "AutoH.iss")])
    setup = os.path.join(ROOT, "installer-output", f"AutoH-Setup-{version}.exe")
    print(f"\nDone in {time.perf_counter() - started:.0f}s")
    print(f"Installer: {setup} ({os.path.getsize(setup) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

"""Build a portable (onedir) MiniLimiter release for Windows.

Usage:
    python build_portable.py                 # build + zip as dist/MiniLimiter-portable.zip
    python build_portable.py --version v1.0.0
    python build_portable.py --icon-only     # only (re)generate MiniLimiter.ico

Requires: pip install -r requirements.txt -r requirements-build.txt
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "MiniLimiter"
PNG = ROOT / "logo netlimiter.png"
ICON = ROOT / "MiniLimiter.ico"
DIST = ROOT / "dist"


def make_icon() -> None:
    """Convert the supplied PNG logo into a multi-size Windows .ico."""
    if not PNG.exists():
        raise FileNotFoundError(f"Logo tidak ditemukan: {PNG}")
    from PIL import Image  # Pillow is already a runtime dependency

    img = Image.open(PNG).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ICON, format="ICO", sizes=sizes)
    print(f"[icon] generated {ICON.name} from {PNG.name}")


def check_inputs() -> None:
    required = [
        ROOT / "src" / "main.py",
        ROOT / "bin" / "WinDivert.dll",
        ROOT / "bin" / "WinDivert64.sys",
        PNG,
        ICON,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("File build hilang:\n  " + "\n  ".join(missing))


def build(version: str) -> Path:
    check_inputs()
    # PyInstaller's --add-* syntax is "source<os.pathsep>destination".
    bin_dll = ROOT / "bin" / "WinDivert.dll"
    bin_sys = ROOT / "bin" / "WinDivert64.sys"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", APP_NAME,
        "--icon", str(ICON),
        "--paths", str(ROOT),
        "--add-data", f"{PNG}{os.pathsep}.",
        "--add-data", f"{ICON}{os.pathsep}.",
        "--add-binary", f"{bin_dll}{os.pathsep}bin",
        "--add-binary", f"{bin_sys}{os.pathsep}bin",
        "--collect-all", "customtkinter",
        "--collect-all", "pystray",
        "--hidden-import", "PIL.Image",
        str(ROOT / "src" / "main.py"),
    ]
    print("[build] " + " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    app_dir = DIST / APP_NAME
    exe = app_dir / f"{APP_NAME}.exe"
    if not exe.exists():
        raise FileNotFoundError(f"EXE tidak dihasilkan: {exe}")

    # Ship an empty config folder so the first-run state has an obvious home.
    (app_dir / "config").mkdir(parents=True, exist_ok=True)
    # Never package local state/logs left over from a test run.
    for stale in (app_dir / "MiniLimiter.log", app_dir / "config" / "rules.json"):
        if stale.exists():
            stale.unlink()

    zip_path = DIST / f"{APP_NAME}-{version}-portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(f"{APP_NAME}/config/.keep", "")
        for path in sorted(app_dir.rglob("*")):
            if path.is_file() and path.name not in {"MiniLimiter.log", "rules.json"}:
                zf.write(path, path.relative_to(DIST).as_posix())
    print(f"[build] EXE : {exe}")
    print(f"[build] ZIP : {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="portable", help="Version tag used in the ZIP filename")
    parser.add_argument("--icon-only", action="store_true", help="Only regenerate MiniLimiter.ico")
    args = parser.parse_args()

    make_icon()
    if args.icon_only:
        return
    build(args.version)


if __name__ == "__main__":
    main()

"""Portable path helpers.

Two kinds of paths are used by the app:

* **State paths** (``config/rules.json``, log file) must live next to the
  executable in a frozen (PyInstaller) build so the release is truly portable.
  Use :func:`app_base` for these.
* **Resource paths** (logo, WinDivert DLL/driver) are bundled *inside* the
  PyInstaller archive/extraction folder.  Use :func:`resource_path` for these.

In source mode (``python src/main.py``) both helpers simply point at the
project root, so development behaviour is unchanged.
"""

import sys
from pathlib import Path

__all__ = ["is_frozen", "app_base", "resource_path"]


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return bool(getattr(sys, "frozen", False))


def app_base() -> Path:
    """Writable base folder: directory of the .exe (frozen) or project root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """Read-only bundled resource: ``sys._MEIPASS`` (frozen) or project root."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(meipass) if meipass else app_base()
    else:
        base = app_base()
    return base.joinpath(*parts)

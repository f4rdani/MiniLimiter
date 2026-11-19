"""Elevation helper for Windows UAC."""

import ctypes
import logging
import os
import sys

from src.utils.paths import app_base, is_frozen

logger = logging.getLogger("MiniLimiter.Elevation")

# Internal flags are consumed by main.py and must not be forwarded on elevation.
_INTERNAL_FLAGS = {"--elevate", "--no-elevate"}
ERROR_CANCELLED = 1223  # user clicked "No" on the UAC prompt


def is_admin() -> bool:
    """Check if the current process is running with Administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _forwarded_args() -> str:
    return " ".join(f'"{arg}"' for arg in sys.argv[1:] if arg not in _INTERNAL_FLAGS)


def elevate_and_restart() -> None:
    """Relaunch the app with Administrator privileges via Windows UAC.

    Source mode: relaunch ``python.exe <script> [args]`` (old behaviour).
    Frozen mode: relaunch the ``.exe`` itself — ``sys.executable`` is the
    portable EXE, not the Python interpreter.
    """
    if is_admin():
        return

    args = _forwarded_args()
    if is_frozen():
        executable = sys.executable
        params = args
        work_dir = str(app_base())
    else:
        script = os.path.abspath(sys.argv[0])
        executable = sys.executable
        params = f'"{script}" {args}'.strip()
        work_dir = None

    # SW_SHOW = 5
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        work_dir,
        5,
    )
    if ret > 32 and ret != ERROR_CANCELLED:
        # Successfully requested elevation, exit current non-elevated process
        sys.exit(0)
    if ret in (0, ERROR_CANCELLED):
        # UAC declined: let the caller continue in monitoring/read-only mode.
        logger.info("UAC elevation declined; continuing in monitoring mode.")
        return
    raise PermissionError(f"Failed to elevate process. ShellExecute returned error code: {ret}")

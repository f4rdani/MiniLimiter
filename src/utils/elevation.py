"""Elevation helper for Windows UAC."""

import ctypes
import os
import sys


def is_admin() -> bool:
    """Check if the current process is running with Administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def elevate_and_restart() -> None:
    """Relaunches the current python script with elevated (Administrator) privileges via Windows UAC."""
    if is_admin():
        return

    # Prepare command line
    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    executable = sys.executable

    # SW_SHOW = 5
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        f'"{script}" {params}',
        None,
        5,
    )
    if ret > 32:
        # Successfully requested elevation, exit current non-elevated process
        sys.exit(0)
    else:
        raise PermissionError(f"Failed to elevate process. ShellExecute returned error code: {ret}")

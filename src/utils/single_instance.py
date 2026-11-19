"""Single-instance guard for MiniLimiter.

A named Windows mutex makes sure only one copy of the app can intercept
traffic at a time. Running two copies would fight over the WinDivert handle
and produce duplicate tray icons / confusing rules. If a second copy is
launched, we simply focus the already-running window and exit.

The mutex is session-local (``Local\\...``), so different Windows sessions
can still each run their own copy.
"""

import atexit
import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger("MiniLimiter.SingleInstance")

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

MUTEX_NAME = r"Local\MiniLimiter_SingleInstance_v1"

_handle = None

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def acquire() -> bool:
    """Return True if this is the first instance, False if one already runs."""
    global _handle
    if _handle is not None:
        return False

    kernel32 = ctypes.windll.kernel32
    try:
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            # Fail open: never block the app because the mutex API is unavailable.
            logger.warning("Could not create single-instance mutex; continuing.")
            return True
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _handle = handle
        atexit.register(release)
        return True
    except Exception as e:
        logger.warning(f"Single-instance check unavailable: {e}")
        return True


def release() -> None:
    """Release the mutex (called automatically at exit)."""
    global _handle
    if _handle is None:
        return
    handle, _handle = _handle, None
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def focus_existing() -> bool:
    """Bring the already-running MiniLimiter window to the foreground."""
    user32 = ctypes.windll.user32
    try:
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]

        found = False

        @_WNDENUMPROC
        def _on_window(hwnd, _lparam):
            nonlocal found
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.startswith("MiniLimiter"):
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                found = True
                return False  # stop enumerating
            return True

        user32.EnumWindows(_on_window, 0)
        return found
    except Exception as e:
        logger.debug(f"Could not focus existing window: {e}")
        return False

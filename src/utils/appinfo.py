"""Application file-version helper (Product / Version / Company ala NetLimiter).

Uses Win32 GetFileVersionInfo via ctypes. Falls back to exe basename when
unavailable (Store apps, system processes, access denied).
"""

import ctypes
import os
import socket
from ctypes import wintypes
from functools import lru_cache


@lru_cache(maxsize=1)
def get_computer_name() -> str:
    """Nama PC dinamis (DESKTOP-20, dst). Fallback berlapis, tidak pernah kosong."""
    try:
        name = socket.gethostname().strip()
        if name:
            return name
    except Exception:
        pass
    try:
        name = (os.environ.get("COMPUTERNAME") or "").strip()
        if name:
            return name
    except Exception:
        pass
    return "This computer"


def _query_value(lang_codepage: str, key: str, buf, handle) -> str:
    try:
        version = ctypes.windll.version
        sub = f"\\StringFileInfo\\{lang_codepage}\\{key}"
        ptr = ctypes.c_void_p()
        size = wintypes.UINT()
        if version.VerQueryValueW(buf, sub, ctypes.byref(ptr), ctypes.byref(size)) and ptr:
            return ctypes.wstring_at(ptr.value)
    except Exception:
        pass
    return ""


@lru_cache(maxsize=512)
def get_file_info(exe_path: str) -> dict:
    """Returns {name, product, version, company}. All strings, never raises."""
    base = os.path.basename(exe_path) if exe_path else ""
    info = {"name": base, "product": "", "version": "", "company": ""}
    if not exe_path or not os.path.exists(exe_path):
        return info
    try:
        version = ctypes.windll.version
        size = version.GetFileVersionInfoSizeW(exe_path, None)
        if not size:
            return info
        buf = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(exe_path, 0, size, buf):
            return info
        # Translation table
        ptr = ctypes.c_void_p()
        tsize = wintypes.UINT()
        lang = "040904B0"
        if version.VerQueryValueW(buf, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(tsize)):
            if tsize.value >= 4:
                arr = ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD * 2)).contents
                lang = f"{arr[0]:04x}{arr[1]:04x}"
        info["product"] = _query_value(lang, "ProductName", buf, None) or base
        info["version"] = _query_value(lang, "FileVersion", buf, None)
        info["company"] = _query_value(lang, "CompanyName", buf, None)
        # Fallback name
        if not info["product"]:
            info["product"] = base
    except Exception:
        pass
    return info

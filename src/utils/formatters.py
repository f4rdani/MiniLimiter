"""Formatters and parsers for network units following NetLimiter convention."""

import re
from typing import Tuple


def format_rate(bytes_per_sec: float, unit_mode: str = "autoByte", decimal_places: int = 2) -> str:
    """Formats bytes per second into human-readable string.
    
    Args:
        bytes_per_sec: Rate in bytes per second.
        unit_mode: 'autoByte', 'KB/s', 'MB/s', 'autoBit', 'Kb/s', 'Mb/s' (bit modes x8, base-1000 seperti Task Manager).
        decimal_places: Number of decimal places for fractional values.
    """
    if bytes_per_sec < 0 or bytes_per_sec != bytes_per_sec:  # handles negative and NaN
        bytes_per_sec = 0.0

    mode = unit_mode.lower().strip()
    raw = unit_mode.strip()

    # Bit modes (b kecil = bit, seperti Task Manager): cek case-sensitive dulu
    # karena lower() membuat "MB/s" dan "Mb/s" terlihat sama.
    if raw in ("Mb/s", "Mbps", "Mbit/s", "mbit/s", "MBps_bit"):
        return f"{(bytes_per_sec*8.0)/1_000_000.0:.{decimal_places}f} Mbps".replace(".", ",")
    if raw in ("Kb/s", "Kbps", "Kbit/s", "kbit/s"):
        return f"{(bytes_per_sec*8.0)/1000.0:.{decimal_places}f} Kbps".replace(".", ",")
    if mode in ("autobit", "auto-bit", "auto bit"):
        bits = bytes_per_sec * 8.0
        if bits < 1000:
            return f"{int(bits)} bps"
        elif bits < 1_000_000:
            return f"{bits/1000.0:.{decimal_places}f} Kbps".replace(".", ",")
        elif bits < 1_000_000_000:
            return f"{bits/1_000_000.0:.{decimal_places}f} Mbps".replace(".", ",")
        else:
            return f"{bits/1_000_000_000.0:.{decimal_places}f} Gbps".replace(".", ",")

    if mode == "kb/s":
        kb = bytes_per_sec / 1024.0
        return f"{kb:.{decimal_places}f} KB/s".replace(".", ",")
    elif mode == "mb/s":
        mb = bytes_per_sec / (1024.0 * 1024.0)
        return f"{mb:.{decimal_places}f} MB/s".replace(".", ",")

    # Default: autoByte
    if bytes_per_sec < 1024:
        return f"{int(bytes_per_sec)} B/s"
    elif bytes_per_sec < 1024 * 1024:
        kb = bytes_per_sec / 1024.0
        return f"{kb:.{decimal_places}f} KB/s".replace(".", ",")
    elif bytes_per_sec < 1024 * 1024 * 1024:
        mb = bytes_per_sec / (1024.0 * 1024.0)
        return f"{mb:.{decimal_places}f} MB/s".replace(".", ",")
    else:
        gb = bytes_per_sec / (1024.0 * 1024.0 * 1024.0)
        return f"{gb:.{decimal_places}f} GB/s".replace(".", ",")


def format_bytes(total_bytes: int, decimal_places: int = 2) -> str:
    """Formats total transferred bytes into human-readable format (B, KB, MB, GB)."""
    if total_bytes < 0:
        total_bytes = 0

    if total_bytes < 1024:
        return f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        kb = total_bytes / 1024.0
        return f"{kb:.{decimal_places}f} KB".replace(".", ",")
    elif total_bytes < 1024 * 1024 * 1024:
        mb = total_bytes / (1024.0 * 1024.0)
        return f"{mb:.{decimal_places}f} MB".replace(".", ",")
    else:
        gb = total_bytes / (1024.0 * 1024.0 * 1024.0)
        return f"{gb:.{decimal_places}f} GB".replace(".", ",")


def parse_rate_string(rate_str: str) -> int:
    """Parses user input string like '2 MB/s', '500 KB/s', '2M', '500k', or '2' into bytes per second.
    Default unit if none specified is MB/s.
    """
    clean_str = rate_str.strip().replace(",", ".").upper()
    match = re.match(r"^([\d.]+)\s*([KMGTP]?B?/S|[KMGTP]B?)?$", clean_str)
    if not match:
        raise ValueError(f"Invalid rate format: '{rate_str}'")

    number = float(match.group(1))
    unit = match.group(2) or "MB"

    if "G" in unit:
        multiplier = 1024 * 1024 * 1024
    elif "M" in unit:
        multiplier = 1024 * 1024
    elif "K" in unit:
        multiplier = 1024
    else:
        multiplier = 1

    return int(number * multiplier)

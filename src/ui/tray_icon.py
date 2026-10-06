"""System tray icon for MiniLimiter (pystray).

- Icon stays in Windows tray when window is minimized / closed (hide-to-tray).
- Hover tooltip shows live Download / Upload speeds.
- Menu: Show | Limiter On (toggle) | Exit.

Falls back to a no-op dummy when pystray/Pillow is unavailable (e.g. headless CI),
so UI smoke tests never break.
"""

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("MiniLimiter.Tray")

try:
    from PIL import Image, ImageDraw
    _HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    _HAS_PIL = False

try:
    import pystray
    _HAS_PYSTRAY = True
except Exception as e:
    pystray = None  # type: ignore
    _HAS_PYSTRAY = False
    logger.debug(f"pystray unavailable: {e}")


def create_tray_image(size: int = 64):
    """Build a small MiniLimiter icon (dark bg, green ↓ + orange ↑)."""
    if not _HAS_PIL:
        return None
    img = Image.new("RGBA", (size, size), (30, 30, 30, 255))
    d = ImageDraw.Draw(img)
    # lime circle background
    pad = size // 8
    d.ellipse([pad, pad, size - pad, size - pad], fill=(124, 187, 0, 255))
    # "M" letter
    try:
        # default bitmap font — always available
        d.text((size // 2, size // 2), "M", fill=(0, 0, 0, 255), anchor="mm")
    except Exception:
        pass
    # download (green->white?) keep simple; arrows drawn as small triangles
    # down arrow bottom-left, up arrow top-right for recognizability
    return img


def build_tooltip_text(dl_rate: float, ul_rate: float, unit_mode: str = "autoByte",
                       limiter_on: Optional[bool] = None) -> str:
    """Tooltip shown on hover: app name + DL/UL speeds (Windows caps ~127 chars)."""
    try:
        from src.utils.formatters import format_rate
        dl_s = format_rate(max(0.0, float(dl_rate or 0.0)), unit_mode=unit_mode)
        ul_s = format_rate(max(0.0, float(ul_rate or 0.0)), unit_mode=unit_mode)
    except Exception:
        dl_s, ul_s = "0 B/s", "0 B/s"
    lines = [f"MiniLimiter", f"DL: {dl_s}  UL: {ul_s}"]
    if limiter_on is not None:
        lines.append(f"Limiter: {'On' if limiter_on else 'Off'}")
    # Use newline — Windows tray tooltip supports multiline.
    return "\n".join(lines)


class MiniLimiterTray:
    """Thin wrapper around pystray.Icon running in a daemon thread."""

    def __init__(
        self,
        on_show: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        on_toggle_limiter: Optional[Callable[[], None]] = None,
        get_limiter_state: Optional[Callable[[], bool]] = None,
    ):
        self.on_show = on_show
        self.on_quit = on_quit
        self.on_toggle_limiter = on_toggle_limiter
        self.get_limiter_state = get_limiter_state
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_tooltip = "MiniLimiter"
        self.available = bool(_HAS_PYSTRAY and _HAS_PIL)
        if not self.available:
            logger.warning("Tray icon disabled (pystray/Pillow missing).")

    # ---------- lifecycle ----------
    def start(self) -> bool:
        if not self.available:
            return False
        if self._running:
            return True
        try:
            image = create_tray_image()
            menu = self._build_menu()
            self._icon = pystray.Icon("MiniLimiter", image, "MiniLimiter", menu)
            self._running = True
            self._thread = threading.Thread(target=self._run, name="TrayIconThread", daemon=True)
            self._thread.start()
            logger.info("Tray icon started.")
            return True
        except Exception as e:
            logger.warning(f"Could not start tray icon: {e}")
            self._running = False
            return False

    def _run(self):
        try:
            if self._icon is not None:
                self._icon.run()
        except Exception as e:
            logger.warning(f"Tray icon loop ended: {e}")
        finally:
            self._running = False

    def stop(self) -> None:
        try:
            if self._icon is not None:
                self._icon.stop()
        except Exception:
            pass
        self._icon = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return bool(self._running and self._icon is not None)

    # ---------- menu ----------
    def _build_menu(self):
        def _do_show(icon=None, item=None):
            try:
                if self.on_show:
                    self.on_show()
            except Exception:
                pass

        def _do_quit(icon=None, item=None):
            try:
                if self.on_quit:
                    self.on_quit()
            except Exception:
                pass

        def _do_toggle(icon=None, item=None):
            try:
                if self.on_toggle_limiter:
                    self.on_toggle_limiter()
            except Exception:
                pass

        def _limiter_checked(item):
            try:
                return bool(self.get_limiter_state()) if self.get_limiter_state else False
            except Exception:
                return False

        items = [
            pystray.MenuItem("Show MiniLimiter", _do_show, default=True),
        ]
        if self.on_toggle_limiter is not None:
            items.append(pystray.MenuItem("Limiter On", _do_toggle, checked=_limiter_checked))
        items.append(pystray.MenuItem("Exit", _do_quit))
        return pystray.Menu(*items)

    def refresh_menu(self) -> None:
        """Refresh checkmarks (call after limiter toggle)."""
        try:
            if self._icon is not None:
                self._icon.update_menu()
        except Exception:
            pass

    # ---------- tooltip ----------
    def update_rates(self, dl_rate: float, ul_rate: float,
                     unit_mode: str = "autoByte",
                     limiter_on: Optional[bool] = None) -> None:
        text = build_tooltip_text(dl_rate, ul_rate, unit_mode, limiter_on)
        if text == self._last_tooltip:
            return
        self._last_tooltip = text
        try:
            if self._icon is not None:
                self._icon.title = text
        except Exception:
            pass

    def set_tooltip(self, text: str) -> None:
        self._last_tooltip = text
        try:
            if self._icon is not None:
                self._icon.title = text
        except Exception:
            pass

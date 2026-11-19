"""Main entry point for MiniLimiter."""

import logging
import os
import sys
from pathlib import Path

# Ensure project root (or the PyInstaller bundle root) is in sys.path.
if getattr(sys, "frozen", False):
    # In a frozen build __file__ may point at src/main.py inside _MEIPASS;
    # the bootloader already adds _MEIPASS, but add it explicitly to be safe.
    _ROOT = Path(getattr(sys, "_MEIPASS", None) or Path(sys.executable).resolve().parent)
else:
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core.rules_manager import RulesManager
from src.core.shaper import TrafficShaper
from src.core.tracker import NetworkTracker
from src.ui.main_window import MainWindow
from src.utils import single_instance
from src.utils.elevation import elevate_and_restart, is_admin
from src.utils.paths import app_base, is_frozen


def _setup_logging() -> None:
    """Console in source mode, log file next to the EXE in windowed builds."""
    handlers = []
    if is_frozen():
        try:
            handlers.append(logging.FileHandler(app_base() / "MiniLimiter.log", encoding="utf-8"))
        except Exception:
            handlers.append(logging.NullHandler())
    else:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        handlers=handlers,
    )


_setup_logging()
logger = logging.getLogger("MiniLimiter")


def main():
    logger.info("Initializing MiniLimiter...")

    # Portable builds request UAC automatically on double-click (no .bat needed).
    # '--no-elevate' is kept for diagnostics; source mode still needs '--elevate'.
    auto_elevate = is_frozen() and "--no-elevate" not in sys.argv
    if not is_admin() and (auto_elevate or "--elevate" in sys.argv):
        logger.info("Requesting UAC Administrator elevation...")
        try:
            elevate_and_restart()
            return
        except Exception as e:
            logger.warning(f"Could not automatically elevate: {e}")

    # Only one copy may own the WinDivert engine. A second launch focuses the
    # existing window instead of creating duplicate engines/tray icons.
    if not single_instance.acquire():
        logger.info("MiniLimiter is already running; focusing the existing window.")
        single_instance.focus_existing()
        return

    # State lives beside the EXE in portable builds (source mode: project root).
    config_dir = app_base() / "config"
    rules_file = config_dir / "rules.json"

    # Core components (tick 0.5s agar realtime, history 120 = 60 detik)
    rules_mgr = RulesManager(rules_file)
    tracker = NetworkTracker(scan_interval=0.5, history_length=120)
    shaper = TrafficShaper(tracker, rules_mgr)

    # Start network tracker background monitor
    tracker.start()

    # If running as Administrator, attempt to start the WinDivert traffic shaper
    if is_admin():
        try:
            shaper.start()
            logger.info("WinDivert Traffic Shaper started successfully with Admin rights.")
        except Exception as e:
            logger.error(f"Failed to start WinDivert shaper: {e}")
    else:
        logger.warning("Running without Administrator rights. Running in Monitoring/Read-Only mode.")

    # Initialize GUI
    app = MainWindow(tracker, rules_mgr, shaper)

    def on_closing():
        # Tombol X = simpan ke tray (engine tetap jalan).
        # Keluar beneran hanya via menu tray "Exit" (MainWindow.shutdown).
        try:
            has_tray = getattr(app, "_tray", None) is not None
            really_quit = bool(getattr(app, "_really_quit", False))
            shutting = bool(getattr(app, "_shutting_down", False))
        except Exception:
            has_tray, really_quit, shutting = False, True, False
        if has_tray and not really_quit and not shutting:
            logger.info("Hiding MiniLimiter to tray (engine keeps running)...")
            try:
                app.hide_to_tray()
            except Exception as e:
                logger.debug(f"hide_to_tray failed, shutting down: {e}")
                app.shutdown()
            return
        logger.info("Shutting down MiniLimiter cleanly...")
        try:
            app.shutdown()
        except Exception:
            try:
                if getattr(app, "_refresh_after", None):
                    app.after_cancel(app._refresh_after)
            except Exception:
                pass
            try:
                shaper.stop()
            except Exception as e:
                logger.debug(f"Error stopping shaper: {e}")
            try:
                tracker.stop()
            except Exception as e:
                logger.debug(f"Error stopping tracker: {e}")
            try:
                app.destroy()
            except Exception:
                pass
        single_instance.release()
        logger.info("Shutdown complete.")

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()

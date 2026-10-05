"""Main entry point for MiniLimiter."""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.rules_manager import RulesManager
from src.core.shaper import TrafficShaper
from src.core.tracker import NetworkTracker
from src.ui.main_window import MainWindow
from src.utils.elevation import elevate_and_restart, is_admin

# Setup clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("MiniLimiter")


def main():
    logger.info("Initializing MiniLimiter...")

    # Optional auto-elevation flag: if user launches with '--elevate' or batch runner
    if "--elevate" in sys.argv and not is_admin():
        logger.info("Requesting UAC Administrator elevation...")
        try:
            elevate_and_restart()
            return
        except Exception as e:
            logger.warning(f"Could not automatically elevate: {e}")

    # Paths
    config_dir = PROJECT_ROOT / "config"
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
        logger.info("Shutting down MiniLimiter cleanly...")
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

        app.destroy()
        logger.info("Shutdown complete.")

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()

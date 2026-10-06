"""UI regression tests: startup MainWindow must not raise; no dead widgets.

- No-dead-controls: tidak ada command=lambda: None / tombol pajangan.
- Import: all UI modules importable.
- Live smoke (needs display): builds MainWindow, switches tabs, drives callbacks.
  Skipped automatically when Tk has no display (headless CI).
"""

import pathlib
import unittest


class TestNoDeadControls(unittest.TestCase):
    DEAD_PATTERNS = ["lambda: None", "lambda t=t: None"]

    def test_no_dead_buttons(self):
        """Semua tombol harus terhubung ke aksi nyata."""
        for name in ("main_window.py", "activity_tab.py", "info_view.py",
                     "traffic_chart.py", "rule_list_tab.py", "network_list_tab.py",
                     "application_list_tab.py", "blocker_tab.py"):
            src = pathlib.Path("src/ui") / name
            text = src.read_text(encoding="utf-8")
            for pat in self.DEAD_PATTERNS:
                self.assertNotIn(pat, text, f"{name} mengandung kontrol mati: {pat}")

    def test_no_removed_modules_referenced(self):
        root = pathlib.Path("src")
        all_src = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
        for dead in ("filter_list_tab", "extra_tabs", "PrioritiesTab", "QuotasTab",
                     "FilterListTab", "Priorities On", "Default with Chart",
                     "Connection history", "Edit HotKey", "Filter info"):
            self.assertNotIn(dead, all_src, f"referensi mati masih ada: {dead}")

    def test_ui_imports(self):
        import src.ui.main_window  # noqa
        import src.ui.activity_tab  # noqa
        import src.ui.info_view  # noqa
        import src.ui.traffic_chart  # noqa
        import src.ui.rule_list_tab  # noqa
        import src.ui.network_list_tab  # noqa
        import src.ui.blocker_tab  # noqa
        import src.ui.application_list_tab  # noqa


class TestMainWindowSmoke(unittest.TestCase):
    def test_build_and_drive(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from src.core.models import Rule
        from src.core.rules_manager import RulesManager
        from src.core.shaper import TrafficShaper
        from src.core.tracker import NetworkTracker
        from src.ui.main_window import MainWindow, TABS

        with TemporaryDirectory() as tmp:
            rules = RulesManager(Path(tmp) / "rules.json")
            tracker = NetworkTracker(scan_interval=0.2, history_length=10)
            shaper = TrafficShaper(tracker, rules)
            tracker.start()
            try:
                app = MainWindow(tracker, rules, shaper)
                app.update()
                for t in TABS:  # every tab must build without TclError
                    app._switch_tab(t)
                    app.update()
                tracker.record_traffic(44000, 1400, True, "8.8.8.8")
                tracker._calculate_rates()
                app._switch_tab("Activity")
                app._periodic_refresh()
                app.update()
                apps = tracker.get_all_apps()
                if apps:
                    app._on_app_selected(apps[0].name)
                    app.update()
                app.selected_app_name = "smoke_test.exe"
                app._on_rule_changed(Rule(app_name="smoke_test.exe", limit_in=2097152, enabled=True))
                app.update()
                app._switch_tab("Rules")
                app.update()
                # Filter gabungan Limit/Blocker (pengganti tab Blocker terpisah)
                app.rule_list_tab.set_filter("Blocker")
                app.update()
                app.rule_list_tab.set_filter("Limit")
                app.update()
                app.rule_list_tab.set_filter("All")
                app.update()
                # Nama lama tetap didukung (backward-compat)
                app._switch_tab("Rule List")
                app.update()
                app._switch_tab("Blocker")
                app.update()
                self.assertEqual(app.current_tab, "Rules")
                app._on_toggle_rule("smoke_test.exe")
                app.update()
                app._switch_tab("Network List")
                app.update()
                if app.network_list_tab._adapters:
                    app._on_network_selected(app.network_list_tab._adapters[0])
                    app.update()
                app._on_delete_rule("smoke_test.exe")
                app.update()
                # Layout: status bar ramping 22px, chart nempel bawah (bukan melayang)
                app.state("zoomed")
                app.update()
                self.assertLessEqual(app.bottom.winfo_height(), 30)
                self.assertGreater(app.split.winfo_height(), 400)
                bottom_y = app.bottom.winfo_rooty()
                chart_bottom = app.traffic_chart.winfo_rooty() + app.traffic_chart.winfo_height()
                self.assertLessEqual(abs(chart_bottom - bottom_y), 60)
            finally:
                try:
                    tracker.stop()
                except Exception:
                    pass
                try:
                    app.destroy()
                except Exception:
                    pass

    def test_activity_sort_and_filter(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from src.core.rules_manager import RulesManager
        from src.core.shaper import TrafficShaper
        from src.core.tracker import NetworkTracker
        from src.ui.main_window import MainWindow

        with TemporaryDirectory() as tmp:
            rules = RulesManager(Path(tmp) / "rules.json")
            tracker = NetworkTracker(scan_interval=0.2, history_length=10)
            shaper = TrafficShaper(tracker, rules)
            tracker.start()
            try:
                app = MainWindow(tracker, rules, shaper)
                app.update()
                tab = app.activity_tab
                for col in ("dl", "ul", "name", "rule"):
                    tab._on_sort(col)
                    tab.update_rows(tracker.get_all_apps(), {}, unit_mode="autoByte")
                    app.update()
                self.assertEqual(tab._sort_col, "rule")
                for mode in ("All", "Online", "Offline", "Hidden", "Limited"):
                    tab._set_filter(mode)
                    tab.update_rows(tracker.get_all_apps(), {}, unit_mode="autoByte")
                    app.update()
                self.assertGreaterEqual(len(tab.tree.get_children()), 5)  # grup + apps
            finally:
                try:
                    tracker.stop()
                except Exception:
                    pass
                try:
                    app.destroy()
                except Exception:
                    pass

    def test_resize_and_reset_view(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from src.core.rules_manager import RulesManager
        from src.core.shaper import TrafficShaper
        from src.core.tracker import NetworkTracker
        from src.ui.main_window import MainWindow

        with TemporaryDirectory() as tmp:
            rules = RulesManager(Path(tmp) / "rules.json")
            tracker = NetworkTracker(scan_interval=0.2, history_length=10)
            shaper = TrafficShaper(tracker, rules)
            tracker.start()
            try:
                app = MainWindow(tracker, rules, shaper)
                app.update()
                # divider bisa di-drag
                app.split.sashpos(0, 700)
                app.update()
                self.assertEqual(app.split.sashpos(0), 700)
                app.right_split.sashpos(0, 400)
                app.update()
                # kolom bisa digeser (drag) ...
                tree = app.activity_tab.tree
                before = tree.column("dl", "width")
                tree.column("dl", width=before + 120)
                app.update()
                self.assertNotEqual(tree.column("dl", "width"), before)
                # ... lalu reset mengembalikan state tampilan
                app.activity_tab._set_filter("Online")
                app._reset_view()
                app.update()
                self.assertEqual(app.activity_tab.filter_mode, "All")
                self.assertEqual(app.activity_tab._sort_col, "dl")
                self.assertTrue(app.activity_tab._sort_desc)
                self.assertEqual(app.search_entry.get(), "")
                # sash kembali ke default (lebar - 470)
                self.assertEqual(app.split.sashpos(0), max(400, app.split.winfo_width() - 470))
            finally:
                try:
                    tracker.stop()
                except Exception:
                    pass
                try:
                    app.destroy()
                except Exception:
                    pass

    def test_chart_axis_follows_units(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        try:
            import time
            import customtkinter as ctk
            from src.ui.traffic_chart import TrafficChart
            host = ctk.CTk()
            host.geometry("800x600")
            host.deiconify()
            try:
                chart = TrafficChart(host)
                chart.pack(fill="both", expand=True)
                host.update()
                now = time.perf_counter()
                hist = [(now - 4 + i, 2 * 1024 * 1024, 512 * 1024) for i in range(5)]
                chart.update_data(hist, unit_mode="Mb/s")
                host.update()
                texts = [chart.canvas.itemcget(i, "text") for i in chart.canvas.find_all()
                         if chart.canvas.type(i) == "text"]
                self.assertIn("Mbps", " ".join(texts))
                chart.update_data(hist, unit_mode="autoByte")
                host.update()
                texts = [chart.canvas.itemcget(i, "text") for i in chart.canvas.find_all()
                         if chart.canvas.type(i) == "text"]
                self.assertIn("MB", " ".join(texts))
            finally:
                try:
                    host.destroy()
                except Exception:
                    pass
        finally:
            pass

    def test_master_toggles_keep_monitoring(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from src.core.rules_manager import RulesManager
        from src.core.shaper import TrafficShaper
        from src.core.tracker import NetworkTracker
        from src.ui.main_window import MainWindow

        with TemporaryDirectory() as tmp:
            rules = RulesManager(Path(tmp) / "rules.json")
            tracker = NetworkTracker(scan_interval=0.2, history_length=10)
            shaper = TrafficShaper(tracker, rules)
            tracker.start()
            try:
                app = MainWindow(tracker, rules, shaper)
                app.update()
                # Limiter Off TIDAK boleh mematikan engine (monitoring jalan terus)
                app.var_limiter.set(False)
                app._on_master_limiter()
                self.assertFalse(rules.master_limiter_enabled)
                app.var_limiter.set(True)
                app._on_master_limiter()
                self.assertTrue(rules.master_limiter_enabled)
                # Blocker toggle tersimpan
                app.var_blocker.set(False)
                app._on_master_blocker()
                self.assertFalse(rules.master_blocker_enabled)
                # Device stats menyimpan total (popup tidak dibuka di test)
                app._on_app_selected("__device__")
                app.update()
                app.info_view.update_device_totals(12345, 678)
                self.assertEqual(app.info_view._device_totals, (12345, 678))
            finally:
                try:
                    tracker.stop()
                except Exception:
                    pass
                try:
                    app.destroy()
                except Exception:
                    pass

    def test_rules_tab_merged_filter(self):
        """Tab Rules gabungan: All/Limit/Blocker memfilter baris dengan benar."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            self.skipTest(f"no display: {e}")
            return
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from src.core.models import Rule
        from src.core.rules_manager import RulesManager
        from src.core.shaper import TrafficShaper
        from src.core.tracker import NetworkTracker
        from src.ui.main_window import MainWindow, TABS

        # Tab Blocker terpisah sudah dihapus dari TABS.
        self.assertNotIn("Blocker", TABS)
        self.assertIn("Rules", TABS)

        with TemporaryDirectory() as tmp:
            rules = RulesManager(Path(tmp) / "rules.json")
            tracker = NetworkTracker(scan_interval=0.2, history_length=10)
            shaper = TrafficShaper(tracker, rules)
            tracker.start()
            try:
                app = MainWindow(tracker, rules, shaper)
                app.update()
                app._on_rule_changed(Rule(app_name="chrome.exe", limit_in=2097152, enabled=True))
                app._on_rule_changed(Rule(app_name="evil.exe", block_in=True, block_out=True, enabled=True))
                app._switch_tab("Rules")
                app.update()

                tab = app.rule_list_tab
                tab.set_filter("All")
                n_all = len(tab.tree.get_children())
                tab.set_filter("Limit")
                n_limit = len(tab.tree.get_children())
                tab.set_filter("Blocker")
                n_blocker = len(tab.tree.get_children())
                # 1 baris limit + 2 baris blocker = 3 baris All
                self.assertEqual(n_all, 3)
                self.assertEqual(n_limit, 1)
                self.assertEqual(n_blocker, 2)
                tab.set_filter("All")
                app._reset_view()
                self.assertEqual(tab.filter_mode, "All")
            finally:
                try:
                    tracker.stop()
                except Exception:
                    pass
                try:
                    app.destroy()
                except Exception:
                    pass

    def test_blocker_works_when_limiter_off(self):
        """Regresi: blocker per-app tidak boleh ikut mati saat Limiter Off."""
        import pathlib
        src = pathlib.Path("src/core/shaper.py").read_text(encoding="utf-8")
        # Lookup rule harus memakai (limiter_on or blocker_on), bukan limiter saja.
        self.assertIn("limiter_on or blocker_on", src)


if __name__ == "__main__":
    unittest.main()

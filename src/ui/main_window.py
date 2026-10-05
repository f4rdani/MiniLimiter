"""Main window (NetLimiter-inspired).

Hanya berisi kontrol yang benar-benar berfungsi — tanpa menu/pilihan pajangan.
- Toolbar: Units | Blocker On | Limiter On | Search
- Tabs: Activity | Rule List | Application List | Network List | Blocker
- Left content per tab + bottom link-bar per tab
- Right: Info View (top) + Traffic chart (bottom)
"""

import logging
import tkinter as tk
from typing import Optional
import customtkinter as ctk

from src.core.models import ProcessInfo, Rule
from src.core.rules_manager import RulesManager
from src.core.shaper import TrafficShaper
from src.core.tracker import NetworkTracker
from src.ui.activity_tab import ActivityTab
from src.ui.application_list_tab import ApplicationListTab
from src.ui.blocker_tab import BlockerTab
from src.ui.info_view import InfoView
from src.ui.network_list_tab import NetworkListTab
from src.ui.rule_list_tab import RuleListTab
from src.ui.theme import (BG_APP, BG_PANEL, FONT_FAMILY, TAB_ACTIVE_BG, TAB_ACTIVE_TEXT,
                          TAB_BG, TAB_TEXT, TEXT_LINK, TEXT_MAIN, TEXT_MUTED,
                          apply_dark_ttk)
from src.ui.traffic_chart import TrafficChart
from src.utils.appinfo import get_file_info
from src.utils.elevation import elevate_and_restart, is_admin
from src.utils.formatters import format_rate

logger = logging.getLogger("MiniLimiter.UI")

TABS = ["Activity", "Rule List", "Application List", "Network List", "Blocker"]


class MainWindow(ctk.CTk):
    def __init__(self, tracker: NetworkTracker, rules_mgr: RulesManager, shaper: TrafficShaper):
        super().__init__()
        self.tracker = tracker
        self.rules_mgr = rules_mgr
        self.shaper = shaper
        self.is_elevated = is_admin()
        self.selected_app_name: Optional[str] = None
        self.current_tab = "Activity"

        ctk.set_appearance_mode("dark")
        apply_dark_ttk()
        suffix = "(Administrator)" if self.is_elevated else "(Monitoring Mode)"
        self.title(f"MiniLimiter {suffix}")
        self.geometry("1280x760")
        self.minsize(1024, 620)
        self.configure(fg_color=BG_APP)

        self._build_toolbar()
        self._build_tabbar()
        # PENTING: bottombar dipack DULU (side=bottom) sebelum split yang expand,
        # kalau tidak status bar terjepit 0px dan chart tidak nempel bawah.
        self._build_bottombar()
        self._build_split()
        self._refresh_after = self.after(500, self._periodic_refresh)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        try:
            if getattr(self, "_refresh_after", None):
                self.after_cancel(self._refresh_after)
        except Exception:
            pass
        self.destroy()

    # ---------------- toolbar ----------------
    def _build_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=36, corner_radius=0)
        self.toolbar.pack(fill="x", side="top")
        ctk.CTkLabel(self.toolbar, text="Units", font=(FONT_FAMILY, 11), text_color=TEXT_MUTED).pack(side="left", padx=(8, 2))
        self.unit_combo = ctk.CTkComboBox(self.toolbar, values=["autoByte", "KB/s", "MB/s", "autoBit", "Mb/s"],
                                          width=90, height=24, font=(FONT_FAMILY, 11), corner_radius=3,
                                          command=lambda _c: self._periodic_refresh())
        self.unit_combo.set("autoByte")
        self.unit_combo.pack(side="left", padx=2)

        self.var_blocker = tk.BooleanVar(value=self.rules_mgr.master_blocker_enabled)
        self.var_limiter = tk.BooleanVar(value=self.rules_mgr.master_limiter_enabled)
        for txt, var, cmd in (("Blocker On", self.var_blocker, self._on_master_blocker),
                              ("Limiter On", self.var_limiter, self._on_master_limiter)):
            cb = ctk.CTkCheckBox(self.toolbar, text=txt, variable=var, font=(FONT_FAMILY, 11),
                                 width=20, command=cmd)
            if var.get():
                cb.select()
            cb.pack(side="left", padx=8)

        if not self.is_elevated:
            ctk.CTkButton(self.toolbar, text="Restart as Admin", width=120, height=24, font=(FONT_FAMILY, 11, "bold"),
                          fg_color="#b35400", command=elevate_and_restart).pack(side="left", padx=4)

        # search kanan + ikon kaca
        swrap = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        swrap.pack(side="right", padx=6)
        self.search_entry = ctk.CTkEntry(swrap, placeholder_text="Search", width=180, height=24, font=(FONT_FAMILY, 11))
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", self._on_search)

    # ---------------- tab bar ----------------
    def _build_tabbar(self):
        self.tabbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=28, corner_radius=0)
        self.tabbar.pack(fill="x")
        self.tab_btns = {}
        for t in TABS:
            b = ctk.CTkButton(self.tabbar, text=t, height=24, font=(FONT_FAMILY, 11),
                              fg_color=TAB_BG, text_color=TAB_TEXT, corner_radius=0, anchor="center",
                              command=lambda n=t: self._switch_tab(n))
            b.pack(side="left", padx=0)
            self.tab_btns[t] = b
        self._paint_tabs()
        # garis kuning di bawah tab aktif (seperti ref)
        self.tab_underline = ctk.CTkFrame(self, fg_color=TAB_ACTIVE_BG, height=2, corner_radius=0)
        self.tab_underline.pack(fill="x")

    def _paint_tabs(self):
        for t, b in self.tab_btns.items():
            if t == self.current_tab:
                b.configure(fg_color=TAB_ACTIVE_BG, text_color=TAB_ACTIVE_TEXT, font=(FONT_FAMILY, 11, "bold"))
            else:
                b.configure(fg_color=TAB_BG, text_color=TAB_TEXT, font=(FONT_FAMILY, 11))

    # ---------------- split ----------------
    def _build_split(self):
        from tkinter import ttk
        # PanedWindow agar divider kiri/kanan bisa di-drag (resize panel).
        self.split = ttk.PanedWindow(self, orient="horizontal", style="Dark.TPanedwindow")
        self.split.pack(fill="both", expand=True, padx=0, pady=0)

        self.left = ctk.CTkFrame(self.split, fg_color=BG_APP, corner_radius=0)
        self.left.pack_propagate(False)
        self.split.add(self.left, weight=3)
        try:
            self.split.pane(self.left, minsize=400)
        except Exception:
            pass

        self.activity_tab = ActivityTab(self.left, on_app_selected=self._on_app_selected,
                                          on_refresh_requested=self.tracker.refresh_now)
        self.activity_tab.pack(fill="both", expand=True)

        self.rule_list_tab = RuleListTab(self.left, on_delete_rule=self._on_delete_rule,
                                         on_toggle_rule=self._on_toggle_rule,
                                         on_rule_selected=self._on_rule_selected)
        self.app_list_tab = ApplicationListTab(self.left, on_app_selected=self._on_app_selected)
        self.network_list_tab = NetworkListTab(self.left, on_network_selected=self._on_network_selected)
        self.blocker_tab = BlockerTab(self.left, on_rule_selected=self._on_rule_selected)
        self._tab_widgets = {"Activity": self.activity_tab, "Rule List": self.rule_list_tab,
                             "Application List": self.app_list_tab,
                             "Network List": self.network_list_tab, "Blocker": self.blocker_tab}

        self.right = ctk.CTkFrame(self.split, fg_color=BG_PANEL, corner_radius=0, width=460)
        self.right.pack_propagate(False)
        self.split.add(self.right, weight=0)
        try:
            self.split.pane(self.right, minsize=300)
        except Exception:
            pass

        # Panel kanan vertikal: Info (atas, expand) + Chart (bawah, bisa di-drag).
        from tkinter import ttk as _ttk
        self.right_split = _ttk.PanedWindow(self.right, orient="vertical", style="Dark.TPanedwindow")
        self.right_split.pack(fill="both", expand=True)
        self.info_view = InfoView(self.right_split, on_rule_changed=self._on_rule_changed,
                                  on_rule_removed=self._on_delete_rule,
                                  on_global_changed=self._on_global_changed,
                                  on_toggle_rule=self._on_toggle_rule)
        self.right_split.add(self.info_view, weight=3)
        try:
            self.right_split.pane(self.info_view, minsize=200)
        except Exception:
            pass
        # Chart tinggi awal 220, bisa dibesar/kecilkan via divider.
        self.traffic_chart = TrafficChart(self.right_split, height=220)
        self.right_split.add(self.traffic_chart, weight=1)
        try:
            self.right_split.pane(self.traffic_chart, minsize=140)
        except Exception:
            pass

    def _build_bottombar(self):
        self.bottom = ctk.CTkFrame(self, fg_color=BG_PANEL, height=22, corner_radius=0)
        self.bottom.pack(fill="x", side="bottom")
        self.bottom.pack_propagate(False)
        # height eksplisit + propagate off: frame kosong default 200x200 yg
        # mendorong status bar jadi raksasa (bug area kosong bawah).
        self.bottom_left = ctk.CTkFrame(self.bottom, fg_color="transparent", height=22)
        self.bottom_left.pack(side="left", padx=4)
        self.bottom_left.pack_propagate(False)
        self.lbl_filtered = ctk.CTkLabel(self.bottom, text="➤ Filtered view", font=(FONT_FAMILY, 11),
                                         text_color=TEXT_LINK)
        self.btn_reset_view = ctk.CTkButton(self.bottom, text="Reset view", font=(FONT_FAMILY, 11),
                                            fg_color="transparent", text_color=TEXT_LINK,
                                            hover_color="#333333", height=18, command=self._reset_view)
        self.btn_reset_view.pack(side="right", padx=8)
        self._refresh_bottombar()

    def _reset_view(self) -> None:
        """Kembalikan layout ke default: filter/sort/kolom/sash/chart."""
        try:
            self.search_entry.delete(0, "end")
        except Exception:
            pass
        try:
            self.activity_tab.reset_view()
        except Exception:
            pass
        for tab in (self.rule_list_tab, self.blocker_tab, self.app_list_tab, self.network_list_tab):
            try:
                tab.reset_columns()
            except Exception:
                pass
        try:
            self.update_idletasks()
            self.split.sashpos(0, max(400, self.split.winfo_width() - 470))
            self.right_split.sashpos(0, max(200, self.right.winfo_height() - 230))
        except Exception:
            pass
        self._refresh_bottombar()
        self._periodic_refresh()

    def _link(self, parent, text, cmd):
        ctk.CTkButton(parent, text=text, font=(FONT_FAMILY, 11), fg_color="transparent",
                      text_color=TEXT_LINK, hover=False, height=18, command=cmd).pack(side="left", padx=4)

    def _refresh_bottombar(self):
        for w in self.bottom_left.winfo_children():
            w.destroy()
        t = self.current_tab
        if t == "Activity":
            pass
        elif t == "Rule List":
            self._link(self.bottom_left, "Add rule", self._add_rule_dialog)
            self._link(self.bottom_left, "Delete rule", self._delete_selected_rule)
        elif t == "Blocker":
            self._link(self.bottom_left, "Delete rule", self._delete_selected_blocker)
        else:
            pass  # Application/Network List: tidak ada aksi bar — hanya Filtered view
        if getattr(self, "activity_tab", None) is not None and (
                self.activity_tab.filter_mode != "All" or self.activity_tab.search_query.strip()):
            self.lbl_filtered.pack(side="right", padx=8)
        else:
            self.lbl_filtered.pack_forget()

    # ---------------- tab switch ----------------
    def _switch_tab(self, name):
        self.current_tab = name
        for n, w in self._tab_widgets.items():
            w.pack_forget()
        self._tab_widgets[name].pack(fill="both", expand=True)
        self._paint_tabs()
        self._refresh_bottombar()
        if name == "Rule List":
            self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
        elif name == "Network List":
            self.network_list_tab.refresh_adapters()
        elif name == "Application List":
            self.app_list_tab.update_apps(self.tracker.get_all_apps())
        elif name == "Blocker":
            self.blocker_tab.update_blockers(self.rules_mgr.get_all_rules())
        self._periodic_refresh()

    # ---------------- selection ----------------
    def _on_search(self, _e=None):
        self.activity_tab.search_query = self.search_entry.get()
        self._refresh_bottombar()

    def _on_app_selected(self, app_name):
        # "__device__" = baris "-" (perangkat ini) -> editor global limit
        if app_name == "__device__":
            self.selected_app_name = "__device__"
            g = self.rules_mgr.get_global_limit()
            apps = self.tracker.get_all_apps()
            total_dl = sum(a.total_dl for a in apps)
            total_ul = sum(a.total_ul for a in apps)
            self.info_view.set_device(g, total_dl, total_ul)
            try:
                from src.utils.appinfo import get_computer_name
                host = get_computer_name()
            except Exception:
                host = "This computer"
            self.traffic_chart.set_target(f"{host} (-)", g.get("limit_in"), total_dl, total_ul)
            return
        self.selected_app_name = app_name
        info = self.tracker.get_app(app_name) or ProcessInfo(name=app_name)
        rule = self.rules_mgr.get_rule_any(app_name)
        try:
            fi = get_file_info(info.exe_path) if info.exe_path else {}
        except Exception:
            fi = {}
        self.info_view.set_app(info, rule, fi)
        lim = rule.limit_in if (rule and rule.enabled) else None
        self.traffic_chart.set_target(app_name, lim, info.total_dl, info.total_ul)

    def _on_rule_selected(self, row):
        self.info_view.set_rule(row)
        rule = row.get("rule")
        if rule is not None:
            self.selected_app_name = rule.app_name
            info = self.tracker.get_app(rule.app_name) or ProcessInfo(name=rule.app_name)
            self.traffic_chart.set_target(rule.app_name, rule.limit_in, info.total_dl, info.total_ul)
        else:
            self.traffic_chart.set_target(row.get("for", ""), None, 0, 0)

    def _on_network_selected(self, nic):
        self.info_view.set_network(nic)
        self.traffic_chart.set_target(nic.get("name", ""), None, 0, 0)

    # ---------------- rules ----------------
    def _on_global_changed(self, limit_in, limit_out, block_in, block_out):
        self.rules_mgr.set_global_limit(limit_in, limit_out, block_in, block_out)
        if self.is_elevated and not self.shaper.is_running and self.rules_mgr.master_limiter_enabled:
            try:
                self.shaper.start()
            except Exception as e:
                logger.error(f"shaper start: {e}")
        self._periodic_refresh()

    def _on_rule_changed(self, rule: Rule):
        self.rules_mgr.set_rule(rule)
        if self.is_elevated and not self.shaper.is_running and self.rules_mgr.master_limiter_enabled:
            try:
                self.shaper.start()
            except Exception as e:
                logger.error(f"shaper start: {e}")
        self._periodic_refresh()

    def _on_delete_rule(self, app_name):
        self.rules_mgr.remove_rule(app_name)
        self._periodic_refresh()

    def _on_toggle_rule(self, app_name, enabled=None):
        r = self.rules_mgr.get_rule_any(app_name)
        if r:
            r.enabled = (not r.enabled) if enabled is None else bool(enabled)
            self.rules_mgr.set_rule(r)
            self._periodic_refresh()

    def _delete_selected_rule(self):
        row = self.rule_list_tab.get_selected()
        if row.get("for") and row.get("kind") != "ignore":
            self._on_delete_rule(row["for"])
        else:
            self._hint_select("rule")

    def _delete_selected_blocker(self):
        row = self.blocker_tab.get_selected()
        if row.get("for") and row.get("rule") is not None:
            self._on_delete_rule(row["for"])
        else:
            self._hint_select("blocker")

    @staticmethod
    def _hint_select(what: str) -> None:
        try:
            from tkinter import messagebox
            messagebox.showinfo("MiniLimiter", f"Select {what} in the table first, then click again.")
        except Exception:
            pass

    def _add_rule_dialog(self):
        # Tambah limit 2 MB/s untuk app terpilih (cepat, seperti Add rule di ref)
        if self.selected_app_name == "__device__":
            self._on_global_changed(2 * 1024 * 1024, None, False, False)
        elif self.selected_app_name:
            self._on_rule_changed(Rule(app_name=self.selected_app_name, limit_in=2 * 1024 * 1024, enabled=True))
        else:
            self._hint_select("an application in the Activity tab")

    def _on_master_limiter(self):
        # Gerbang enforcement saja — monitoring tetap jalan (seperti NetLimiter).
        enabled = bool(self.var_limiter.get())
        self.rules_mgr.master_limiter_enabled = enabled
        self.rules_mgr.save()
        if enabled and self.is_elevated and not self.shaper.is_running:
            try:
                self.shaper.start()
            except Exception as e:
                logger.error(f"Error enabling shaper: {e}")

    def _on_master_blocker(self):
        self.rules_mgr.master_blocker_enabled = bool(self.var_blocker.get())
        self.rules_mgr.save()

    # ---------------- refresh ----------------
    def _periodic_refresh(self):
        try:
            # Snapshot atomik: apps + grup dari tick yang SAMA (anti race).
            apps, groups, group_totals = self.tracker.snapshot()
            all_rules = {r.app_name: r for r in self.rules_mgr.get_all_rules()}
            try:
                unit = self.unit_combo.get()
            except Exception:
                unit = "autoByte"
            if self.current_tab == "Activity":
                try:
                    self.activity_tab.set_group_rates(*groups)
                except Exception:
                    pass
                g = self.rules_mgr.get_global_limit()
                self.activity_tab.update_rows(apps, all_rules, unit_mode=unit,
                                              global_limit_in=g.get("limit_in"),
                                              group_totals=group_totals)
            elif self.current_tab == "Application List":
                try:
                    self.app_list_tab.update_apps(apps)
                except Exception:
                    pass
            elif self.current_tab == "Rule List":
                try:
                    self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
                except Exception:
                    pass
            elif self.current_tab == "Blocker":
                try:
                    self.blocker_tab.update_blockers(self.rules_mgr.get_all_rules())
                except Exception:
                    pass
            hist = self.tracker.get_history(self.selected_app_name)
            try:
                self.traffic_chart.update_data(hist, unit_mode=unit)
            except Exception:
                pass
            if self.selected_app_name == "__device__":
                g = self.rules_mgr.get_global_limit()
                total_dl_bytes = sum(a.total_dl for a in apps)
                total_ul_bytes = sum(a.total_ul for a in apps)
                try:
                    self.info_view.update_device_totals(total_dl_bytes, total_ul_bytes)
                except Exception:
                    pass
                try:
                    from src.utils.appinfo import get_computer_name
                    host = get_computer_name()
                except Exception:
                    host = "This computer"
                self.traffic_chart.set_target(f"{host} (-)", g.get("limit_in"), total_dl_bytes, total_ul_bytes)
            elif self.selected_app_name:
                info = self.tracker.get_app(self.selected_app_name)
                rule = all_rules.get(self.selected_app_name)
                lim = rule.limit_in if (rule and rule.enabled) else None
                if info:
                    self.traffic_chart.set_target(self.selected_app_name, lim, info.total_dl, info.total_ul)
            else:
                total_dl_bytes = sum(a.total_dl for a in apps)
                total_ul_bytes = sum(a.total_ul for a in apps)
                self.traffic_chart.set_target("Total Traffic", None, total_dl_bytes, total_ul_bytes)
        except Exception:
            pass
        finally:
            try:
                self._refresh_after = self.after(500, self._periodic_refresh)
            except Exception:
                pass

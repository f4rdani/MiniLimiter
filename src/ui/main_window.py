"""Main window (NetLimiter-inspired).

Hanya berisi kontrol yang benar-benar berfungsi — tanpa menu/pilihan pajangan.
- Toolbar: Units | Blocker On | Limiter On | Search
- Tabs: Activity | Rules (Limit+Blocker + filter) | Application List | Network List
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
from src.ui.info_view import InfoView
from src.ui.network_list_tab import NetworkListTab
from src.ui.rule_list_tab import RuleListTab
from src.ui.theme import (BG_APP, BG_PANEL, FONT_FAMILY, TAB_ACTIVE_BG, TAB_ACTIVE_TEXT,
                          TAB_BG, TAB_TEXT, TEXT_LINK, TEXT_MAIN, TEXT_MUTED,
                          apply_dark_ttk)
from src.ui.tray_icon import MiniLimiterTray
from src.ui.traffic_chart import TrafficChart
from src.utils.appinfo import get_file_info
from src.utils.elevation import elevate_and_restart, is_admin
from src.utils.formatters import format_rate

logger = logging.getLogger("MiniLimiter.UI")

TABS = ["Activity", "Rules", "Application List", "Network List"]
# Nama lama (sebelum gabung) -> nama baru, agar callback/test lama tetap jalan.
_LEGACY_TAB_ALIASES = {"Rule List": "Rules", "Blocker": "Rules"}


class MainWindow(ctk.CTk):
    def __init__(self, tracker: NetworkTracker, rules_mgr: RulesManager, shaper: TrafficShaper):
        super().__init__()
        self.tracker = tracker
        self.rules_mgr = rules_mgr
        self.shaper = shaper
        self.is_elevated = is_admin()
        self.selected_app_name: Optional[str] = None
        self.current_tab = "Activity"
        # --- tray state (hide-to-tray, bukan exit) ---
        self._tray = None
        self._is_hidden_to_tray = False
        self._really_quit = False
        self._shutting_down = False

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
        self._init_tray()
        self._refresh_after = self.after(500, self._periodic_refresh)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Minimize (_) -> sembunyi ke tray (bukan ke taskbar).
        self.bind("<Unmap>", self._on_minimize_to_tray)

    # ---------------- tray (hide-to-tray + hover DL/UL) ----------------
    def _init_tray(self):
        """Buat ikon tray. Hover = tooltip DL/UL live, menu = Show/Limiter/Exit."""
        try:
            self._tray = MiniLimiterTray(
                on_show=self._show_from_tray,
                on_quit=self._quit_from_tray,
                on_toggle_limiter=self._toggle_limiter_from_tray,
                get_limiter_state=lambda: bool(self.rules_mgr.master_limiter_enabled),
            )
            started = self._tray.start()
            if not started:
                self._tray = None
        except Exception as e:
            logger.warning(f"Tray init failed: {e}")
            self._tray = None

    def _ensure_tray(self) -> bool:
        if self._tray is not None:
            return True
        try:
            self._init_tray()
        except Exception:
            pass
        return self._tray is not None

    def hide_to_tray(self):
        """Sembunyikan window ke tray (engine tetap jalan)."""
        if self._shutting_down or self._really_quit:
            return
        if not self._ensure_tray():
            # Tanpa tray (headless/CI): fallback minimize biasa.
            try:
                self.iconify()
            except Exception:
                pass
            return
        try:
            self.withdraw()
        except Exception:
            pass
        self._is_hidden_to_tray = True
        try:
            self._update_tray_tooltip()
        except Exception:
            pass

    def _on_minimize_to_tray(self, _event=None):
        # Hanya saat user klik minimize (iconic) & belum disembunyikan.
        if self._shutting_down or self._really_quit or self._is_hidden_to_tray:
            return
        try:
            if self.state() == "iconic" and self._tray is not None:
                # Tunda sedikit agar state stabil, lalu withdraw ke tray.
                self.after(50, self._hide_if_still_iconic)
        except Exception:
            pass

    def _hide_if_still_iconic(self):
        try:
            if self.state() == "iconic" and not self._is_hidden_to_tray:
                self.hide_to_tray()
        except Exception:
            pass

    def _do_show_window(self):
        try:
            self.deiconify()
        except Exception:
            pass
        try:
            self.state("normal")
        except Exception:
            pass
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self._is_hidden_to_tray = False

    def _show_from_tray(self):
        """Callback dari thread tray -> jadwalkan ke thread Tk."""
        try:
            self.after(0, self._do_show_window)
        except Exception:
            pass

    def _toggle_limiter_from_tray(self):
        try:
            self.after(0, self._do_toggle_limiter_from_tray)
        except Exception:
            pass

    def _do_toggle_limiter_from_tray(self):
        try:
            new_val = not bool(self.rules_mgr.master_limiter_enabled)
            self.var_limiter.set(new_val)
            self._on_master_limiter()
            if self._tray is not None:
                self._tray.refresh_menu()
                self._update_tray_tooltip()
        except Exception:
            pass

    def _quit_from_tray(self):
        try:
            self.after(0, self.shutdown)
        except Exception:
            pass

    def _update_tray_tooltip(self):
        if self._tray is None:
            return
        try:
            dl, ul = self.tracker.get_total_rates()
        except Exception:
            dl, ul = 0.0, 0.0
        try:
            unit = self.unit_combo.get()
        except Exception:
            unit = "autoByte"
        try:
            limiter_on = bool(self.rules_mgr.master_limiter_enabled)
        except Exception:
            limiter_on = None
        try:
            self._tray.update_rates(dl, ul, unit_mode=unit, limiter_on=limiter_on)
        except Exception:
            pass

    def shutdown(self):
        """Keluar beneran: stop tray + backend lalu destroy (dipakai X+Exit)."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._really_quit = True
        try:
            if getattr(self, "_refresh_after", None):
                self.after_cancel(self._refresh_after)
        except Exception:
            pass
        try:
            if self._tray is not None:
                self._tray.stop()
        except Exception:
            pass
        try:
            self.shaper.stop()
        except Exception:
            pass
        try:
            self.tracker.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def destroy(self):
        # Pastikan ikon tray tidak tertinggal saat window dihancurkan (mis. test).
        try:
            self._shutting_down = True
        except Exception:
            pass
        try:
            if getattr(self, "_refresh_after", None):
                self.after_cancel(self._refresh_after)
        except Exception:
            pass
        try:
            if getattr(self, "_tray", None) is not None:
                self._tray.stop()
        except Exception:
            pass
        super().destroy()

    def _on_close(self):
        # Tombol X = simpan ke tray (engine tetap jalan), bukan exit.
        if self._really_quit or self._shutting_down or self._tray is None:
            self.shutdown()
        else:
            self.hide_to_tray()

    # ---------------- toolbar ----------------
    def _build_toolbar(self):
        from src.ui.theme import (BTN_BG, BTN_HOVER, INPUT_BG, INPUT_BORDER,
                                  INPUT_FOCUS, PRIMARY_BG, PRIMARY_HOVER,
                                  RADIUS_MD, RADIUS_PILL, SURFACE_2)
        self.toolbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=40, corner_radius=0)
        self.toolbar.pack(fill="x", side="top")
        ctk.CTkLabel(self.toolbar, text="Units", font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(10, 4), pady=8)
        self.unit_combo = ctk.CTkComboBox(
            self.toolbar, values=["autoByte", "KB/s", "MB/s", "autoBit", "Mb/s"],
            width=104, height=28, font=(FONT_FAMILY, 11), corner_radius=RADIUS_MD,
            fg_color=INPUT_BG, border_color=INPUT_BORDER, border_width=1,
            button_color=SURFACE_2, button_hover_color=BTN_HOVER,
            dropdown_fg_color=SURFACE_2, dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            command=lambda _c: self._periodic_refresh())
        self.unit_combo.set("autoByte")
        self.unit_combo.pack(side="left", padx=2, pady=6)

        self.var_blocker = tk.BooleanVar(value=self.rules_mgr.master_blocker_enabled)
        self.var_limiter = tk.BooleanVar(value=self.rules_mgr.master_limiter_enabled)
        for txt, var, cmd in (("Blocker On", self.var_blocker, self._on_master_blocker),
                              ("Limiter On", self.var_limiter, self._on_master_limiter)):
            cb = ctk.CTkCheckBox(self.toolbar, text=txt, variable=var, font=(FONT_FAMILY, 11),
                                 fg_color=PRIMARY_BG, hover_color=PRIMARY_HOVER,
                                 border_color=INPUT_BORDER, checkmark_color="#ffffff",
                                 text_color=TEXT_MAIN, command=cmd)
            if var.get():
                cb.select()
            cb.pack(side="left", padx=10, pady=8)

        if not self.is_elevated:
            ctk.CTkButton(self.toolbar, text="↗ Restart as Admin", width=140, height=28,
                          font=(FONT_FAMILY, 11, "bold"), corner_radius=RADIUS_MD,
                          fg_color="#b35400", hover_color="#c96a10",
                          command=elevate_and_restart).pack(side="left", padx=4, pady=6)

        # search kanan: satu entry pill kokoh + tombol clear (×) + tombol tray
        swrap = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        swrap.pack(side="right", padx=8, pady=6)
        ctk.CTkButton(swrap, text="Hide to Tray", width=104, height=28, font=(FONT_FAMILY, 11),
                      corner_radius=RADIUS_PILL, border_width=1, border_color=INPUT_BORDER,
                      fg_color=BTN_BG, hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                      command=self.hide_to_tray).pack(side="left", padx=(0, 8))
        search_box = ctk.CTkFrame(swrap, fg_color="transparent")
        search_box.pack(side="left")
        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text="○  Search apps…",
            width=200, height=28, font=(FONT_FAMILY, 11),
            corner_radius=RADIUS_PILL, fg_color=INPUT_BG,
            border_color=INPUT_BORDER, border_width=1,
            text_color=TEXT_MAIN, placeholder_text_color="#8a8a8a")
        self.search_entry.pack(side="left")
        self.btn_clear_search = ctk.CTkButton(
            search_box, text="×", width=28, height=28, font=(FONT_FAMILY, 13, "bold"),
            corner_radius=RADIUS_PILL, fg_color="transparent", hover_color=BTN_HOVER,
            text_color=TEXT_MUTED, command=self._clear_search)
        # disembunyikan sampai ada teks (diatur di _on_search)
        self.search_entry.bind("<KeyRelease>", self._on_search)
        self.search_entry.bind("<FocusIn>", lambda _e: self.search_entry.configure(border_color=INPUT_FOCUS))
        self.search_entry.bind("<FocusOut>", lambda _e: self.search_entry.configure(border_color=INPUT_BORDER))
        # garis bawah toolbar agar terasa seperti header aplikasi modern
        self.toolbar_border = ctk.CTkFrame(self, fg_color="#333333", height=1, corner_radius=0)
        self.toolbar_border.pack(fill="x", side="top")

    # ---------------- tab bar ----------------
    def _build_tabbar(self):
        from src.ui.theme import RADIUS_MD
        self.tabbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=34, corner_radius=0)
        self.tabbar.pack(fill="x", padx=8, pady=(6, 0))
        self.tab_btns = {}
        for t in TABS:
            b = ctk.CTkButton(self.tabbar, text=t, height=28, font=(FONT_FAMILY, 11),
                              fg_color=TAB_BG, text_color=TAB_TEXT, corner_radius=RADIUS_MD, anchor="center",
                              hover_color="#3d3d3d",
                              command=lambda n=t: self._switch_tab(n))
            b.pack(side="left", padx=3)
            self.tab_btns[t] = b
        self._paint_tabs()
        # garis kuning di bawah tab aktif (seperti ref)
        self.tab_underline = ctk.CTkFrame(self, fg_color=TAB_ACTIVE_BG, height=2, corner_radius=0)
        self.tab_underline.pack(fill="x", padx=0, pady=(4, 0))

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
        # Compat: kode/test lama yang mengakses app.blocker_tab / "Blocker" tetap jalan
        # (menunjuk ke tab Rules yang sama, bukan widget terpisah).
        self.blocker_tab = self.rule_list_tab
        self._tab_widgets = {"Activity": self.activity_tab, "Rules": self.rule_list_tab,
                             "Application List": self.app_list_tab,
                             "Network List": self.network_list_tab}
        # Alias nama lama -> widget baru.
        self._tab_widgets["Rule List"] = self.rule_list_tab
        self._tab_widgets["Blocker"] = self.rule_list_tab

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
        self.bottom_left.pack(side="left", padx=6)
        self.bottom_left.pack_propagate(False)
        self.lbl_filtered = ctk.CTkLabel(self.bottom, text="● Filtered view", font=(FONT_FAMILY, 10),
                                         text_color=TEXT_LINK)
        self.btn_reset_view = ctk.CTkButton(self.bottom, text="↺ Reset view", font=(FONT_FAMILY, 10, "bold"),
                                            fg_color="transparent", text_color=TEXT_LINK,
                                            border_width=1, border_color="#3d3d3d", corner_radius=11,
                                            hover_color="#333333", height=18, width=100,
                                            command=self._reset_view)
        self.btn_reset_view.pack(side="right", padx=8, pady=2)
        self._refresh_bottombar()

    def _reset_view(self) -> None:
        """Kembalikan layout ke default: filter/sort/kolom/sash/chart."""
        try:
            self.search_entry.delete(0, "end")
        except Exception:
            pass
        self._sync_clear_button()
        try:
            self.activity_tab.reset_view()
        except Exception:
            pass
        for tab in (self.rule_list_tab, self.app_list_tab, self.network_list_tab):
            try:
                tab.reset_columns()
            except Exception:
                pass
        try:
            self.rule_list_tab.set_filter("All")
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
        prefix = "+ " if text.lower().startswith("add") else ("— " if text.lower().startswith("delete") else "")
        ctk.CTkButton(parent, text=f"{prefix}{text}", font=(FONT_FAMILY, 10, "bold"),
                      fg_color="#2f2f2f", hover_color="#3d3d3d", text_color=TEXT_MAIN,
                      border_width=1, border_color="#3d3d3d", corner_radius=11,
                      height=18, command=cmd).pack(side="left", padx=3)

    def _refresh_bottombar(self):
        for w in self.bottom_left.winfo_children():
            w.destroy()
        t = _LEGACY_TAB_ALIASES.get(self.current_tab, self.current_tab)
        if t == "Activity":
            pass
        elif t == "Rules":
            self._link(self.bottom_left, "Add rule", self._add_rule_dialog)
            self._link(self.bottom_left, "Delete rule", self._delete_selected_rule)
        else:
            pass  # Application/Network List: tidak ada aksi bar — hanya Filtered view
        if getattr(self, "activity_tab", None) is not None and (
                self.activity_tab.filter_mode != "All" or self.activity_tab.search_query.strip()):
            self.lbl_filtered.pack(side="right", padx=8)
        else:
            self.lbl_filtered.pack_forget()

    # ---------------- tab switch ----------------
    def _switch_tab(self, name):
        # Terima nama lama ("Rule List"/"Blocker") demi backward-compat.
        name = _LEGACY_TAB_ALIASES.get(name, name)
        self.current_tab = name
        for n, w in self._tab_widgets.items():
            try:
                w.pack_forget()
            except Exception:
                pass
        self._tab_widgets[name].pack(fill="both", expand=True)
        self._paint_tabs()
        self._refresh_bottombar()
        if name == "Rules":
            self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
        elif name == "Network List":
            self.network_list_tab.refresh_adapters()
        elif name == "Application List":
            self.app_list_tab.update_apps(self.tracker.get_all_apps())
        self._periodic_refresh()

    # ---------------- selection ----------------
    def _on_search(self, _e=None):
        self.activity_tab.search_query = self.search_entry.get()
        self._sync_clear_button()
        self._refresh_bottombar()

    def _sync_clear_button(self) -> None:
        """Tampilkan tombol × hanya saat ada teks di search."""
        try:
            has_text = bool(self.search_entry.get().strip())
        except Exception:
            has_text = False
        try:
            if has_text:
                self.btn_clear_search.pack(side="left", padx=(4, 0))
            else:
                self.btn_clear_search.pack_forget()
        except Exception:
            pass

    def _clear_search(self) -> None:
        try:
            self.search_entry.delete(0, "end")
        except Exception:
            pass
        self._on_search()

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
    def _ensure_shaper_for_rules(self) -> None:
        """Start WinDivert engine bila ada limit/blocker aktif (limit ATAU blocker).

        Sebelumnya hanya cek master_limiter_enabled, sehingga blocker saja
        tidak pernah menghidupkan engine (blocker terlihat 'tidak berfungsi').
        """
        try:
            if not self.is_elevated or self.shaper.is_running:
                return
            if not (self.rules_mgr.master_limiter_enabled or self.rules_mgr.master_blocker_enabled):
                return
            if not self.rules_mgr.has_any_limiting():
                return
            self.shaper.start()
        except Exception as e:
            logger.error(f"shaper start: {e}")

    def _on_global_changed(self, limit_in, limit_out, block_in, block_out):
        self.rules_mgr.set_global_limit(limit_in, limit_out, block_in, block_out)
        self._ensure_shaper_for_rules()
        self._periodic_refresh()

    def _on_rule_changed(self, rule: Rule):
        self.rules_mgr.set_rule(rule)
        self._ensure_shaper_for_rules()
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

    # Compat: dulu ada tab Blocker terpisah dengan aksi hapus sendiri.
    def _delete_selected_blocker(self):
        return self._delete_selected_rule()

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
        if enabled:
            self._ensure_shaper_for_rules()
        try:
            if self._tray is not None:
                self._tray.refresh_menu()
                self._update_tray_tooltip()
        except Exception:
            pass

    def _on_master_blocker(self):
        self.rules_mgr.master_blocker_enabled = bool(self.var_blocker.get())
        self.rules_mgr.save()
        if bool(self.var_blocker.get()):
            self._ensure_shaper_for_rules()

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
            elif self.current_tab in ("Rules", "Rule List", "Blocker"):
                try:
                    self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
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
            # Hover tray icon = kecepatan DL & UL total (live).
            try:
                self._update_tray_tooltip()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                # Jangan jadwalkan refresh baru saat sedang shutdown/destroy.
                if not getattr(self, "_shutting_down", False) and self.winfo_exists():
                    self._refresh_after = self.after(500, self._periodic_refresh)
            except Exception:
                pass

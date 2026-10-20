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
from src.ui.theme import (ACCENT, BG_APP, BG_CARD, BG_CARD_ALT, BG_PANEL,
                          BORDER_COLOR, BORDER_STRONG, BTN_BG, BTN_HOVER,
                          DOT_AMBER, DOT_GRAY, DOT_GREEN, FONT_FAMILY,
                          PRIMARY_BG, TAB_ACTIVE_BG, TAB_ACTIVE_TEXT, TAB_BG,
                          TAB_HOVER, TAB_TEXT, TEXT_DISABLED, TEXT_GREEN,
                          TEXT_LINK, TEXT_MAIN, TEXT_MUTED, TEXT_SUBTLE,
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
    _UNIT_MODES = {
        "Auto (B/s)": "autoByte",
        "KB/s": "KB/s",
        "MB/s": "MB/s",
        "Auto (bit/s)": "autoBit",
        "Mbps": "Mb/s",
    }

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
        self._narrow = None
        self.bind("<Configure>", self._on_window_resize)

    # ---------------- responsive layout ----------------
    def _on_window_resize(self, event):
        """Toolbar adjusts itself so nothing important is pushed off-screen."""
        if event.widget is not self:
            return
        narrow = event.width < 1240
        if narrow == self._narrow:
            return
        self._narrow = narrow
        try:
            if narrow:
                self._brand_txt.pack_forget()
                self.unit_combo.configure(width=106)
                self.search_entry.configure(width=160)
            else:
                self._brand_txt.pack(side="left", padx=(9, 0))
                self.unit_combo.configure(width=118)
                self.search_entry.configure(width=224)
            if getattr(self, "_admin_btn", None) is not None:
                if narrow:
                    self._admin_btn.configure(text="↗  Admin", width=118)
                else:
                    self._admin_btn.configure(text="↗  Restart as Admin", width=166)
        except Exception:
            pass
        self._fit_right_panel()

    def _panel_width(self) -> int:
        """Right inspector width: a bit slimmer on small screens."""
        try:
            narrow = self.split.winfo_width() < 1200
        except Exception:
            narrow = False
        return 420 if narrow else 470

    def _fit_right_panel(self) -> None:
        """Keep the inspector panel from squeezing the tables on narrow windows."""
        try:
            width = self._panel_width()
            self.update_idletasks()
            self.right.configure(width=width)
            self.split.sashpos(0, max(400, self.split.winfo_width() - width))
        except Exception:
            pass

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
            unit = self._unit_mode()
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

    def _unit_mode(self) -> str:
        """Return the formatter mode for the human-readable units dropdown."""
        try:
            value = self.unit_combo.get()
        except Exception:
            return "autoByte"
        return self._UNIT_MODES.get(value, value or "autoByte")

    # ---------------- toolbar ----------------
    def _build_toolbar(self):
        from src.ui.theme import (BG_CARD_ALT, BTN_BG, BTN_HOVER, INPUT_BG, INPUT_BORDER,
                                  INPUT_FOCUS, PRIMARY_BG, PRIMARY_HOVER,
                                  RADIUS_PILL, SURFACE_2, SURFACE_3)
        self.toolbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=66, corner_radius=0)
        self.toolbar.pack(fill="x", side="top")
        self.toolbar.pack_propagate(False)

        bar = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        bar.pack(fill="both", expand=True, padx=14, pady=8)

        # -- brand ---------------------------------------------------------
        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(side="left")
        logo = ctk.CTkFrame(brand, width=36, height=36, corner_radius=10,
                            fg_color=TAB_ACTIVE_BG)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="M", font=(FONT_FAMILY, 16, "bold"),
                     text_color="#101318").place(relx=0.5, rely=0.5, anchor="center")
        brand_txt = ctk.CTkFrame(brand, fg_color="transparent")
        brand_txt.pack(side="left", padx=(9, 0))
        self._brand_txt = brand_txt
        ctk.CTkLabel(brand_txt, text="MiniLimiter", height=18,
                     font=(FONT_FAMILY, 14, "bold"),
                     text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(brand_txt, text="Network control", height=16,
                     font=(FONT_FAMILY, 11),
                     text_color=TEXT_SUBTLE).pack(anchor="w")
        self._toolbar_sep(bar)

        # -- units ---------------------------------------------------------
        units = ctk.CTkFrame(bar, fg_color="transparent")
        units.pack(side="left")
        ctk.CTkLabel(units, text="UNITS", height=14, font=(FONT_FAMILY, 10, "bold"),
                     text_color=TEXT_SUBTLE).pack(anchor="w")
        self.unit_combo = ctk.CTkComboBox(
            units, values=list(self._UNIT_MODES),
            width=118, height=32, font=(FONT_FAMILY, 11), corner_radius=7,
            fg_color=INPUT_BG, border_color=INPUT_BORDER, border_width=1,
            button_color=SURFACE_2, button_hover_color=BTN_HOVER,
            dropdown_fg_color=SURFACE_2, dropdown_text_color=TEXT_MAIN,
            dropdown_hover_color=BTN_HOVER,
            text_color=TEXT_MAIN,
            command=lambda _c: self._periodic_refresh())
        self.unit_combo.set("Auto (B/s)")
        self.unit_combo.pack(anchor="w", pady=(1, 0))
        self._toolbar_sep(bar, pad=14)

        # -- master switches ----------------------------------------------
        self.var_blocker = tk.BooleanVar(value=self.rules_mgr.master_blocker_enabled)
        self.var_limiter = tk.BooleanVar(value=self.rules_mgr.master_limiter_enabled)
        self._master_dots = {}
        self._master_states = {}
        self._master_wraps = {}
        self._master_switches = {}
        for key, txt, var, cmd in (
                ("limiter", "Limiter", self.var_limiter, self._on_master_limiter),
                ("blocker", "Blocker", self.var_blocker, self._on_master_blocker)):
            wrap = ctk.CTkFrame(bar, fg_color=BG_CARD, corner_radius=9,
                                border_width=1, border_color=BORDER_COLOR)
            wrap.pack(side="left", padx=(0, 6), pady=2)
            self._master_wraps[key] = wrap
            inner = ctk.CTkFrame(wrap, fg_color="transparent")
            inner.pack(padx=10, pady=4)
            dot = ctk.CTkFrame(inner, width=8, height=8, corner_radius=4,
                               fg_color=DOT_GRAY)
            dot.pack(side="left", padx=(0, 7))
            self._master_dots[key] = dot
            ctk.CTkLabel(inner, text=txt, height=22, font=(FONT_FAMILY, 11, "bold"),
                         text_color=TEXT_MAIN).pack(side="left")
            state = ctk.CTkLabel(inner, text="Off", width=26, height=22,
                                 font=(FONT_FAMILY, 10, "bold"), text_color=TEXT_SUBTLE)
            state.pack(side="right", padx=(7, 0))
            self._master_states[key] = state
            sw = ctk.CTkSwitch(
                inner, text="", width=38, height=20, switch_width=34, switch_height=18,
                corner_radius=9, variable=var,
                fg_color=SURFACE_3, progress_color=(
                    PRIMARY_BG if key == "limiter" else "#c65454"),
                button_color="#f3f6fb", button_hover_color="#ffffff",
                command=cmd)
            sw.pack(side="left", padx=(9, 4))
            self._master_switches[key] = sw
            if var.get():
                sw.select()

        # -- admin state ---------------------------------------------------
        self._admin_btn = None
        if not self.is_elevated:
            self._admin_btn = ctk.CTkButton(
                bar, text="↗  Restart as Admin", width=166, height=34,
                font=(FONT_FAMILY, 11, "bold"), corner_radius=8,
                fg_color="#4a371b", hover_color="#5c4522",
                text_color="#ffc56b", border_width=1, border_color="#7c5a20",
                command=elevate_and_restart)
            self._admin_btn.pack(side="left", padx=(4, 0), pady=1)
        else:
            admin = ctk.CTkFrame(bar, fg_color="#183323", corner_radius=8,
                                 border_width=1, border_color="#356a45")
            admin.pack(side="left", padx=(4, 0), pady=1)
            ctk.CTkLabel(admin, text="●  Administrator", height=30,
                         font=(FONT_FAMILY, 11, "bold"),
                         text_color=TEXT_GREEN).pack(padx=10)

        # -- search + tray --------------------------------------------------
        swrap = ctk.CTkFrame(bar, fg_color="transparent")
        swrap.pack(side="right")
        ctk.CTkButton(
            swrap, text="⌄  Hide", width=78, height=34, font=(FONT_FAMILY, 11),
            corner_radius=8, border_width=1, border_color=INPUT_BORDER,
            fg_color=BG_CARD_ALT, hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            command=self.hide_to_tray).pack(side="left", padx=(0, 8))
        search_box = ctk.CTkFrame(swrap, fg_color="transparent")
        search_box.pack(side="left")
        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text="Search applications…",
            width=224, height=34, font=(FONT_FAMILY, 11),
            corner_radius=8, fg_color=INPUT_BG,
            border_color=INPUT_BORDER, border_width=1,
            text_color=TEXT_MAIN, placeholder_text_color=TEXT_SUBTLE)
        self.search_entry.pack(side="left")
        self.btn_clear_search = ctk.CTkButton(
            search_box, text="×", width=30, height=34, font=(FONT_FAMILY, 14, "bold"),
            corner_radius=6, fg_color="transparent", hover_color=BTN_HOVER,
            text_color=TEXT_MUTED, command=self._clear_search)
        # Hidden until there is text (managed by _on_search).
        self.search_entry.bind("<KeyRelease>", self._on_search)
        self.search_entry.bind("<FocusIn>", lambda _e: self.search_entry.configure(border_color=INPUT_FOCUS))
        self.search_entry.bind("<FocusOut>", lambda _e: self.search_entry.configure(border_color=INPUT_BORDER))

        self._paint_master_states()
        self.toolbar_border = ctk.CTkFrame(self, fg_color=BORDER_COLOR, height=1, corner_radius=0)
        self.toolbar_border.pack(fill="x", side="top")

    @staticmethod
    def _toolbar_sep(parent, pad=10):
        ctk.CTkFrame(parent, width=1, height=36, fg_color=BORDER_COLOR,
                     corner_radius=0).pack(side="left", padx=(pad, pad))

    def _paint_master_states(self):
        """Sync the little status dot / On-Off text with the master vars."""
        for key, var in (("limiter", self.var_limiter), ("blocker", self.var_blocker)):
            try:
                on = bool(var.get())
                color = (TEXT_GREEN if key == "limiter" else "#ff8585") if on else DOT_GRAY
                sw = self._master_switches.get(key)
                if sw is not None and bool(sw.get()) != on:
                    (sw.select if on else sw.deselect)()
                if sw is not None:
                    sw.configure(
                        fg_color="#39434f",
                        progress_color=(PRIMARY_BG if key == "limiter" else "#c65454"),
                        button_color=("#ffffff" if on else "#aab4c2"))
                self._master_dots[key].configure(fg_color=color)
                self._master_states[key].configure(
                    text="On" if on else "Off",
                    text_color=(color if on else TEXT_DISABLED))
                self._master_wraps[key].configure(
                    border_color=("#2b5540" if key == "limiter" else "#552b2b") if on else BORDER_COLOR)
            except Exception:
                pass

    # ---------------- tab bar ----------------
    def _build_tabbar(self):
        self.tabbar = ctk.CTkFrame(self, fg_color=BG_APP, height=46, corner_radius=0)
        self.tabbar.pack(fill="x", padx=12, pady=(2, 2))
        self.tabbar.pack_propagate(False)
        self.tab_btns = {}
        self.tab_labels = {
            "Activity": "Activity",
            "Rules": "Rules",
            "Application List": "Applications",
            "Network List": "Network",
        }
        for t in TABS:
            b = ctk.CTkButton(
                self.tabbar, text=self.tab_labels.get(t, t), height=34,
                width=max(84, 18 + 9 * len(self.tab_labels.get(t, t))),
                font=(FONT_FAMILY, 11), fg_color="transparent",
                text_color=TAB_TEXT, corner_radius=7, anchor="center",
                hover_color=TAB_HOVER, border_width=0,
                command=lambda n=t: self._switch_tab(n))
            b.pack(side="left", padx=(0, 3), pady=6)
            self.tab_btns[t] = b
        # Thin yellow bar under the active tab (NetLimiter accent, modernised).
        self.tab_indicator = ctk.CTkFrame(self.tabbar, fg_color=TAB_ACTIVE_BG,
                                          height=2, width=54, corner_radius=1)
        self.tabbar.bind("<Configure>", lambda _e: self.after_idle(self._position_tab_indicator))
        self._paint_tabs()

    def _paint_tabs(self):
        for t, b in self.tab_btns.items():
            active = (t == self.current_tab)
            try:
                b.configure(
                    fg_color=BG_CARD if active else "transparent",
                    text_color=TAB_ACTIVE_BG if active else TAB_TEXT,
                    font=(FONT_FAMILY, 11, "bold" if active else "normal"),
                    border_width=1 if active else 0,
                    border_color=BORDER_COLOR)
            except Exception:
                pass
        self.after_idle(self._position_tab_indicator)

    def _position_tab_indicator(self):
        try:
            btn = self.tab_btns.get(self.current_tab)
            if btn is None or not self.tab_indicator.winfo_exists():
                return
            btn.update_idletasks()
            width = max(28, btn.winfo_width() - 26)
            x = btn.winfo_x() + (btn.winfo_width() - width) // 2
            self.tab_indicator.configure(width=width)
            self.tab_indicator.place(x=x, y=43)
            self.tab_indicator.lift()
        except Exception:
            pass

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

        self.right = ctk.CTkFrame(self.split, fg_color=BG_PANEL, corner_radius=0, width=470)
        self.right.pack_propagate(False)
        self.split.add(self.right, weight=0)
        try:
            self.split.pane(self.right, minsize=320)
        except Exception:
            pass

        # Right panel: Info (top, expand) + Chart (bottom, draggable).
        from tkinter import ttk as _ttk
        self.right_split = _ttk.PanedWindow(self.right, orient="vertical", style="Dark.TPanedwindow")
        self.right_split.pack(fill="both", expand=True)
        self.info_view = InfoView(self.right_split, on_rule_changed=self._on_rule_changed,
                                  on_rule_removed=self._on_delete_rule,
                                  on_global_changed=self._on_global_changed,
                                  on_toggle_rule=self._on_toggle_rule)
        self.right_split.add(self.info_view, weight=3)
        try:
            self.right_split.pane(self.info_view, minsize=210)
        except Exception:
            pass
        self.traffic_chart = TrafficChart(self.right_split, height=240)
        self.right_split.add(self.traffic_chart, weight=1)
        try:
            self.right_split.pane(self.traffic_chart, minsize=165)
        except Exception:
            pass

    def _build_bottombar(self):
        self.bottom = ctk.CTkFrame(self, fg_color=BG_PANEL, height=30, corner_radius=0)
        self.bottom.pack(fill="x", side="bottom")
        self.bottom.pack_propagate(False)
        # A thin separator above the status bar.
        ctk.CTkFrame(self.bottom, fg_color=BORDER_COLOR, height=1,
                     corner_radius=0).pack(fill="x", side="top")

        self.bottom_left = ctk.CTkFrame(self.bottom, fg_color="transparent", height=25)
        self.bottom_left.pack(side="left", padx=(10, 0), pady=(2, 2))
        self.bottom_left.pack_propagate(False)

        self.status_area = ctk.CTkFrame(self.bottom, fg_color="transparent", height=25)
        self.status_area.pack(side="left", padx=(10, 0), pady=(2, 2))
        self.status_dot = ctk.CTkLabel(self.status_area, text="●", width=12, height=18,
                                       font=(FONT_FAMILY, 10), text_color=DOT_AMBER)
        self.status_dot.pack(side="left")
        self.lbl_engine = ctk.CTkLabel(self.status_area, text="Monitoring", height=18,
                                       font=(FONT_FAMILY, 11), text_color=TEXT_MUTED)
        self.lbl_engine.pack(side="left", padx=(4, 0))
        self._status_sep()
        self.lbl_totals = ctk.CTkLabel(self.status_area, text="↓ 0 B/s   ↑ 0 B/s", height=18,
                                       font=(FONT_FAMILY, 11), text_color=TEXT_MUTED)
        self.lbl_totals.pack(side="left")
        self._status_sep()
        self.lbl_apps = ctk.CTkLabel(self.status_area, text="0 apps", height=18,
                                     font=(FONT_FAMILY, 11), text_color=TEXT_SUBTLE)
        self.lbl_apps.pack(side="left")
        self._status_sep()
        self.lbl_rules = ctk.CTkLabel(self.status_area, text="0 rules", height=18,
                                      font=(FONT_FAMILY, 11), text_color=TEXT_SUBTLE)
        self.lbl_rules.pack(side="left")

        self.btn_reset_view = ctk.CTkButton(self.bottom, text="↺  Reset view",
                                            font=(FONT_FAMILY, 11, "bold"),
                                            fg_color=BG_CARD_ALT, text_color=TEXT_LINK,
                                            border_width=1, border_color=BORDER_STRONG,
                                            corner_radius=7, hover_color=BTN_HOVER,
                                            height=24, width=110,
                                            command=self._reset_view)
        self.btn_reset_view.pack(side="right", padx=(4, 10), pady=2)
        self.lbl_filtered = ctk.CTkLabel(self.bottom, text="● Filtered view",
                                         font=(FONT_FAMILY, 11, "bold"),
                                         text_color=ACCENT)
        self._refresh_bottombar()
        self._update_statusbar(0.0, 0.0, 0, 0, 0, 0)

    def _status_sep(self):
        ctk.CTkLabel(self.status_area, text="·", height=18, width=12,
                     font=(FONT_FAMILY, 11), text_color=TEXT_DISABLED).pack(side="left", padx=2)

    def _reset_view(self) -> None:
        """Restore the default layout: filters, sort, columns, sash, chart."""
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
        for tab in (self.rule_list_tab, self.app_list_tab, self.network_list_tab):
            try:
                tab.set_search("")
            except Exception:
                pass
        try:
            self.rule_list_tab.set_filter("All")
        except Exception:
            pass
        try:
            self.update_idletasks()
            self.split.sashpos(0, max(400, self.split.winfo_width() - self._panel_width()))
            self.right_split.sashpos(0, max(200, self.right.winfo_height() - 230))
        except Exception:
            pass
        self._refresh_bottombar()
        self._periodic_refresh()

    def _link(self, parent, text, cmd):
        prefix = "+ " if text.lower().startswith("add") else ("− " if text.lower().startswith("delete") else "")
        label = f"{prefix}{text}"
        ctk.CTkButton(
            parent, text=label, font=(FONT_FAMILY, 11, "bold"),
            fg_color=BTN_BG, hover_color=BTN_HOVER, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_STRONG,
            corner_radius=6, height=24, width=max(104, 24 + 8 * len(label)),
            command=cmd).pack(side="left", padx=(0, 6))

    def _refresh_bottombar(self):
        for w in self.bottom_left.winfo_children():
            w.destroy()
        t = _LEGACY_TAB_ALIASES.get(self.current_tab, self.current_tab)
        if t == "Activity":
            self._link(self.bottom_left, "↻ Refresh now", self._refresh_now)
        elif t == "Rules":
            self._link(self.bottom_left, "Add rule", self._add_rule_dialog)
            self._link(self.bottom_left, "Delete rule", self._delete_selected_rule)
        elif t == "Network List":
            self._link(self.bottom_left, "↻ Refresh adapters", self._refresh_adapters)
        # Application List has no destructive actions.

        if self._is_filtered_view():
            self.lbl_filtered.pack(side="right", padx=(4, 2))
        else:
            self.lbl_filtered.pack_forget()

    def _refresh_now(self):
        try:
            self.tracker.refresh_now()
        except Exception:
            pass

    def _refresh_adapters(self):
        try:
            self.network_list_tab.refresh_adapters()
        except Exception:
            pass

    def _is_filtered_view(self) -> bool:
        try:
            if self.search_entry.get().strip():
                return True
        except Exception:
            pass
        if self.current_tab == "Activity":
            return getattr(getattr(self, "activity_tab", None), "filter_mode", "All") != "All"
        if self.current_tab == "Rules":
            return getattr(getattr(self, "rule_list_tab", None), "filter_mode", "All") != "All"
        return False

    def _update_statusbar(self, dl, ul, apps, rules, limits, blockers):
        """Live engine + throughput summary in the bottom bar."""
        try:
            running = bool(getattr(self.shaper, "is_running", False))
            if running:
                dot, color, engine = "●", TEXT_GREEN, "Shaper active"
            elif not self.is_elevated:
                dot, color, engine = "●", DOT_AMBER, "Monitoring only"
            else:
                dot, color, engine = "●", DOT_AMBER, "Limiter paused"
            self.status_dot.configure(text=dot, text_color=color)
            self.lbl_engine.configure(text=engine, text_color=TEXT_MUTED)
            self.lbl_totals.configure(
                text=f"↓ {format_rate(dl, self._unit_mode())}   "
                     f"↑ {format_rate(ul, self._unit_mode())}")
            self.lbl_apps.configure(text=f"{apps} apps")
            self.lbl_rules.configure(text=f"{rules} rules")
            self.lbl_filtered.configure(
                text=("● Filtered view" if self._is_filtered_view() else ""))
        except Exception:
            pass

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
        self._update_search_placeholder()
        if name == "Rules":
            self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
        elif name == "Network List":
            self.network_list_tab.refresh_adapters()
        elif name == "Application List":
            self.app_list_tab.update_apps(self.tracker.get_all_apps())
        self._apply_search_to_current()
        self._periodic_refresh()
        # After the layout settles the column widths can change, so re-fit the text.
        try:
            self.after(80, self._refit_current_tab)
        except Exception:
            pass

    def _refit_current_tab(self):
        """Re-fit the visible table text after the tab has been laid out."""
        try:
            tab = self._tab_widgets.get(self.current_tab)
            if tab is not None and hasattr(tab, "_refit_view"):
                tab._refit_view()
        except Exception:
            pass

    def _update_search_placeholder(self):
        text = {
            "Activity": "Search applications…",
            "Rules": "Search rules…",
            "Application List": "Search applications…",
            "Network List": "Search adapters…",
        }.get(self.current_tab, "Search…")
        try:
            self.search_entry.configure(placeholder_text=text)
        except Exception:
            pass

    # ---------------- selection ----------------
    def _on_search(self, _e=None):
        q = self.search_entry.get()
        try:
            self.activity_tab.search_query = q
        except Exception:
            pass
        for tab in (getattr(self, "rule_list_tab", None),
                    getattr(self, "app_list_tab", None),
                    getattr(self, "network_list_tab", None)):
            try:
                tab.set_search(q)
            except Exception:
                pass
        self._sync_clear_button()
        self._refresh_bottombar()
        self._apply_search_to_current()

    def _apply_search_to_current(self):
        """Refresh the visible tab immediately after a search keystroke."""
        try:
            if self.current_tab == "Activity":
                apps, groups, group_totals = self.tracker.snapshot()
                self.activity_tab.set_group_rates(*groups)
                g = self.rules_mgr.get_global_limit()
                self.activity_tab.update_rows(
                    apps, {r.app_name: r for r in self.rules_mgr.get_all_rules()},
                    unit_mode=self._unit_mode(),
                    global_limit_in=g.get("limit_in"),
                    group_totals=group_totals,
                    total_rates=self.tracker.get_total_rates())
            elif self.current_tab == "Rules":
                self.rule_list_tab.update_rules(self.rules_mgr.get_all_rules())
            elif self.current_tab == "Application List":
                self.app_list_tab.update_apps(self.tracker.get_all_apps())
            elif self.current_tab == "Network List":
                self.network_list_tab.render_adapters()
        except Exception:
            pass

    def _sync_clear_button(self) -> None:
        """Show the × button only when the search box contains text."""
        try:
            has_text = bool(self.search_entry.get().strip())
        except Exception:
            has_text = False
        try:
            if has_text:
                self.btn_clear_search.pack(side="left", padx=(2, 0))
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
                host = "This PC"
            if not host or host.strip() in ("-", "This computer"):
                host = "This PC"
            self.traffic_chart.set_target(host, g.get("limit_in"), total_dl, total_ul)
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
        self._paint_master_states()
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
        self._paint_master_states()

    # ---------------- refresh ----------------
    def _periodic_refresh(self):
        # Only one refresh loop should ever be alive; actions that refresh
        # immediately would otherwise stack up timers.
        try:
            if self._refresh_after is not None:
                self.after_cancel(self._refresh_after)
        except Exception:
            pass
        self._refresh_after = None
        try:
            # Snapshot atomik: apps + grup dari tick yang SAMA (anti race).
            apps, groups, group_totals = self.tracker.snapshot()
            all_rules = {r.app_name: r for r in self.rules_mgr.get_all_rules()}
            enabled_rules = [r for r in all_rules.values() if r.enabled]
            n_limits = sum(1 for r in enabled_rules if r.limit_in or r.limit_out)
            n_blockers = sum(1 for r in enabled_rules if r.block_in or r.block_out)
            try:
                unit = self._unit_mode()
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
                                              group_totals=group_totals,
                                              total_rates=self.tracker.get_total_rates())
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
                    host = "This PC"
                if not host or host.strip() in ("-", "This computer"):
                    host = "This PC"
                self.traffic_chart.set_target(host, g.get("limit_in"), total_dl_bytes, total_ul_bytes)
            elif self.selected_app_name:
                info = self.tracker.get_app(self.selected_app_name)
                rule = all_rules.get(self.selected_app_name)
                lim = rule.limit_in if (rule and rule.enabled) else None
                if info:
                    try:
                        self.info_view.update_app_totals(info.total_dl, info.total_ul)
                    except Exception:
                        pass
                    self.traffic_chart.set_target(self.selected_app_name, lim, info.total_dl, info.total_ul)
            else:
                total_dl_bytes = sum(a.total_dl for a in apps)
                total_ul_bytes = sum(a.total_ul for a in apps)
                self.traffic_chart.set_target("Total Traffic", None, total_dl_bytes, total_ul_bytes)
                try:
                    dl_rate, ul_rate = self.tracker.get_total_rates()
                    self.info_view.set_overview({
                        "dl_rate": dl_rate,
                        "ul_rate": ul_rate,
                        "dl_total": total_dl_bytes,
                        "ul_total": total_ul_bytes,
                        "apps": len(apps),
                        "online": sum(1 for a in apps if a.is_online),
                        "rules": len(enabled_rules),
                        "limits": n_limits,
                        "blockers": n_blockers,
                        "limiter": bool(self.rules_mgr.master_limiter_enabled),
                        "blocker": bool(self.rules_mgr.master_blocker_enabled),
                        "unit": unit,
                    })
                except Exception:
                    pass
            try:
                dl_rate, ul_rate = self.tracker.get_total_rates()
                self._update_statusbar(dl_rate, ul_rate, len(apps), len(enabled_rules),
                                       n_limits, n_blockers)
            except Exception:
                pass
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

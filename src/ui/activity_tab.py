"""Activity tab — live process list with download/upload rates.

Layout is NetLimiter-inspired but tuned for readability: a compact filter
toolbar, a soft card around the table, aligned numeric columns and a friendly
empty state when search/filter hides everything.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from src.core.models import ProcessInfo, Rule
from src.ui.theme import (ACCENT, BG_APP, BG_CARD, BG_CARD_ALT, BG_TABLE,
                          BORDER_COLOR, COLOR_DOWNLOAD, COLOR_UPLOAD, DOT_GRAY,
                          DOT_GREEN, FONT_FAMILY, ROW_ALT_BG, SELECT_BLUE,
                          TEXT_DISABLED, TEXT_GREEN, TEXT_MAIN, TEXT_MUTED,
                          TEXT_SUBTLE, bind_mousewheel, fit_text, style_table,
                          tree_col_width)
from src.utils.appinfo import get_computer_name
from src.utils.formatters import format_bytes, format_rate

FRIENDLY_NAMES = {
    "msedge.exe": "Microsoft Edge",
    "msedgewebview2.exe": "Microsoft Edge WebView2",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "code.exe": "VS Code",
    "steam.exe": "Steam",
    "steamwebhelper.exe": "Steam Client WebHelper",
    "spotify.exe": "Spotify",
    "discord.exe": "Discord",
    "svchost.exe": "Host Process for Windows Services",
    "taskhostw.exe": "Host Process for Windows Tasks",
    "lsass.exe": "Local Security Authority Process",
    "msmpeng.exe": "Antimalware Service Executable",
    "nissrv.exe": "Antimalware Core Service",
    "nvcontainer.exe": "NVIDIA Container",
    "git.exe": "Git for Windows",
    "python.exe": "Python",
    "node.exe": "Node.js JavaScript Runtime",
    "bun.exe": "Bun",
    "warp-svc.exe": "warp-svc",
    "opencode.exe": "opencode",
    "antigravity.exe": "Antigravity",
    "agy.exe": "agy.exe",
    "spoolsv.exe": "Print Spooler",
    "services.exe": "Services",
    "wininit.exe": "Windows Init",
    "crossdeviceservice.exe": "Microsoft Cross Device Service",
    "depotdownloadermod.exe": "DepotDownloaderMod",
    "msi.centralserver.exe": "MSI Center",
    "explorer.exe": "Windows Explorer",
    "startmenuexperiencehost.exe": "Windows Start Experience Host",
    "winget.exe": "WindowsPackageManagerServer.exe",
    "dns.exe": "DNS Client",
    "dosvc": "Delivery Optimization",
    "nlsvc.exe": "NLSvc",
}


def friendly_name(exe_name: str) -> str:
    key = (exe_name or "").lower()
    if key in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[key]
    base = key[:-4] if key.endswith(".exe") else key
    if not base:
        return exe_name
    base = base.replace("_", " ").replace("-", " ")
    return base[:1].upper() + base[1:]


def app_icon(exe_name: str) -> str:
    """Compat shim: real icons are drawn by src.utils.icons.get_app_tile()."""
    return ""


class ActivityTab(ctk.CTkFrame):
    def __init__(self, master, on_app_selected: Callable[[str], None],
                 on_refresh_requested: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_app_selected = on_app_selected
        self.on_refresh_requested = on_refresh_requested
        self.filter_mode: str = "All"
        self.search_query: str = ""
        self.selected_app: Optional[str] = None
        self.unit_mode: str = "autoByte"
        self.show_totals: bool = False
        self._group_rates = (0.0, 0.0, 0.0, 0.0)
        self._sort_col: str = "dl"
        self._sort_desc: bool = True
        self._tile_refs: dict = {}
        self._label_cache: dict = {}
        self._resize_job = None
        self._empty_label = None
        self._build_sub_bar()
        self._build_treeview()

    # ------------------------------------------------------------- sub toolbar
    def _build_sub_bar(self):
        from src.ui.theme import BTN_BG, BTN_HOVER, BORDER_STRONG, RADIUS_MD, RADIUS_PILL
        self.sub_bar = ctk.CTkFrame(self, fg_color=BG_APP, height=46)
        self.sub_bar.pack(fill="x", padx=8, pady=(5, 5))
        self.sub_bar.pack_propagate(False)

        # Rate / Total segmented toggle.
        self.btn_rate = ctk.CTkButton(
            self.sub_bar, text="Rate", width=64, height=32,
            font=(FONT_FAMILY, 11, "bold"), fg_color=BG_CARD,
            hover_color=BTN_HOVER, text_color=TEXT_MAIN,
            border_width=1, border_color=BORDER_STRONG,
            corner_radius=6, command=self._toggle_mode)
        self.btn_rate.pack(side="left", padx=(2, 6))

        self.pills = {}
        for name, w in (("All", 46), ("Online", 62), ("Offline", 66),
                        ("Hidden", 62), ("Limited", 66)):
            b = ctk.CTkButton(
                self.sub_bar, text=name, width=w, height=32,
                font=(FONT_FAMILY, 11), fg_color=BG_CARD_ALT,
                border_width=1, border_color=BORDER_COLOR,
                hover_color=BTN_HOVER, text_color=TEXT_MUTED,
                corner_radius=RADIUS_PILL,
                command=lambda n=name: self._set_filter(n))
            b.pack(side="left", padx=(0, 3))
            self.pills[name] = b
        self._paint_filters()

        self.lbl_stats = ctk.CTkLabel(self.sub_bar, text="", height=24,
                                      font=(FONT_FAMILY, 11), text_color=TEXT_SUBTLE)
        self.lbl_stats.pack(side="right", padx=(6, 4))
        self._stats_full = ""
        self._stats_short = ""
        self.sub_bar.bind("<Configure>", self._on_sub_bar_resize)
        self.btn_refresh = ctk.CTkButton(
            self.sub_bar, text="↻", width=32, height=32,
            font=(FONT_FAMILY, 14), fg_color=BG_CARD_ALT,
            border_width=1, border_color=BORDER_COLOR,
            hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            corner_radius=6, command=self._on_refresh)
        self.btn_refresh.pack(side="right", padx=(0, 3))
        self.btn_sort = ctk.CTkButton(
            self.sub_bar, text="Sort  DL ↓", width=96, height=32,
            font=(FONT_FAMILY, 11, "bold"), fg_color=BG_CARD_ALT,
            border_width=1, border_color=BORDER_COLOR,
            hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            corner_radius=6, command=self.cycle_sort)
        self.btn_sort.pack(side="right", padx=(0, 5))

    def _paint_filters(self):
        for name, btn in self.pills.items():
            active = (name == self.filter_mode)
            try:
                btn.configure(
                    fg_color=SELECT_BLUE if active else BG_CARD_ALT,
                    text_color="#ffffff" if active else TEXT_MUTED,
                    font=(FONT_FAMILY, 11, "bold" if active else "normal"),
                    border_color=(ACCENT if active else BORDER_COLOR))
            except Exception:
                pass

    def _paint_sort_button(self):
        labels = {"name": "Name", "dl": "DL", "ul": "UL", "rule": "Rule"}
        arrow = "↓" if self._sort_desc else "↑"
        try:
            self.btn_sort.configure(text=f"Sort  {labels.get(self._sort_col, 'DL')} {arrow}")
        except Exception:
            pass

    def _toggle_mode(self) -> None:
        self.show_totals = not self.show_totals
        try:
            self.btn_rate.configure(text="Total" if self.show_totals else "Rate")
        except Exception:
            pass
        self._paint_headings()

    def cycle_sort(self) -> None:
        order = ["dl", "ul", "name", "rule"]
        nxt = order[(order.index(self._sort_col) + 1) % len(order)]
        self._sort_col = nxt
        self._sort_desc = True if nxt in ("dl", "ul", "rule") else False
        self._paint_sort_button()
        self._paint_headings()

    def _on_refresh(self) -> None:
        if self.on_refresh_requested is not None:
            self.on_refresh_requested()

    def _set_filter(self, mode):
        self.filter_mode = mode
        self._paint_filters()

    # ------------------------------------------------------------------- table
    def _build_treeview(self):
        from src.ui.theme import RADIUS_LG
        self.table_card = ctk.CTkFrame(
            self, fg_color=BG_TABLE, corner_radius=RADIUS_LG,
            border_width=1, border_color=BORDER_COLOR)
        self.table_card.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        style_table("NLM.Treeview", rowheight=31, font_size=12)
        cols = ("dl", "ul", "rule")
        self.tree = ttk.Treeview(
            self.table_card, style="NLM.Treeview", columns=cols,
            show="tree headings", selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="Name", anchor="w",
                          command=lambda: self._on_sort("name"))
        self.tree.heading("dl", text="DL Rate", anchor="e",
                          command=lambda: self._on_sort("dl"))
        self.tree.heading("ul", text="UL Rate", anchor="e",
                          command=lambda: self._on_sort("ul"))
        self.tree.heading("rule", text="Rule Status", anchor="e",
                          command=lambda: self._on_sort("rule"))
        self.tree.column("#0", width=210, minwidth=140, anchor="w", stretch=True)
        self.tree.column("dl", width=118, minwidth=90, anchor="e")
        self.tree.column("ul", width=118, minwidth=90, anchor="e")
        self.tree.column("rule", width=130, minwidth=90, anchor="e")

        vs = ttk.Scrollbar(self.table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(7, 0), pady=7)
        vs.pack(side="right", fill="y", padx=(0, 5), pady=7)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("dim", foreground=TEXT_MUTED)
        self.tree.tag_configure("alt", background=ROW_ALT_BG)
        self.tree.tag_configure("group", foreground=TEXT_MAIN,
                                font=(FONT_FAMILY, 12, "bold"))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._resize_job = None
        self.tree.bind("<Configure>", self._on_tree_resize)

    def destroy(self):
        try:
            if getattr(self, "_resize_job", None) is not None:
                self.after_cancel(self._resize_job)
                self._resize_job = None
        except Exception:
            pass
        super().destroy()

    def _refit_view(self) -> None:
        """Re-render so the cell text matches the current column widths."""
        self._refit_labels()

    def _on_tree_resize(self, event):
        """Re-fit the row labels when the name column is resized/stretched."""
        if event.widget is not self.tree:
            return
        try:
            if self._resize_job is not None:
                self.after_cancel(self._resize_job)
        except Exception:
            pass
        try:
            self._resize_job = self.after(150, self._refit_labels)
        except Exception:
            self._resize_job = None

    def _refit_labels(self) -> None:
        try:
            width = self._col_width("#0", 210)
            for iid, (prefix, disp) in list(self._label_cache.items()):
                if self.tree.exists(iid):
                    self.tree.item(iid, text=fit_text(f"{prefix}{disp}", width,
                                                      reserve=30))
        except Exception:
            pass

        self._empty_label = ctk.CTkLabel(
            self.table_card,
            text="No applications match this view.",
            font=(FONT_FAMILY, 13), text_color=TEXT_SUBTLE,
            fg_color=BG_TABLE)
        # placed/forgotten dynamically in update_rows()
        self._paint_headings()
        self._paint_sort_button()

    def _on_sort(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = True if col in ("dl", "ul", "rule") else False
        self._paint_sort_button()
        self._paint_headings()

    def reset_view(self) -> None:
        self._set_filter("All")
        self.search_query = ""
        if self.show_totals:
            self._toggle_mode()
        self._sort_col = "dl"
        self._sort_desc = True
        self.reset_columns()
        self._paint_sort_button()
        self._paint_headings()

    def reset_columns(self) -> None:
        try:
            self.tree.column("#0", width=210)
            self.tree.column("dl", width=118)
            self.tree.column("ul", width=118)
            self.tree.column("rule", width=130)
        except Exception:
            pass

    def _paint_headings(self) -> None:
        arrow = " ↓" if self._sort_desc else " ↑"
        suffixes = {"autoByte": "B/s", "autoBit": "bit/s", "Mb/s": "Mbps"}
        suffix = suffixes.get(self.unit_mode, self.unit_mode)
        unit = "" if self.show_totals else f" ({suffix})"
        names = {
            "name": "Name" + (arrow if self._sort_col == "name" else ""),
            "dl": ("Total DL" if self.show_totals else "DL Rate") + unit +
                  (arrow if self._sort_col == "dl" else ""),
            "ul": ("Total UL" if self.show_totals else "UL Rate") + unit +
                  (arrow if self._sort_col == "ul" else ""),
            "rule": "Rule Status" + (arrow if self._sort_col == "rule" else ""),
        }
        try:
            self.tree.heading("#0", text=names["name"])
            self.tree.heading("dl", text=names["dl"])
            self.tree.heading("ul", text=names["ul"])
            self.tree.heading("rule", text=names["rule"], anchor="e")
        except Exception:
            pass

    def _col_width(self, col: str, default: int) -> int:
        """Current pixel width of a column (it stretches with the window)."""
        return tree_col_width(self.tree, col, default)

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid == "__root__":
            self.selected_app = "__device__"
            self.on_app_selected("__device__")
            return
        try:
            parent = self.tree.parent(iid)
            if parent and not iid.startswith("app:"):
                iid = parent
        except Exception:
            pass
        if iid.startswith("app:"):
            app = iid[4:]
            self.selected_app = app
            self.on_app_selected(app)
        elif iid.startswith("grp:"):
            pass  # group row: informational only

    def set_group_rates(self, internet_dl, internet_ul, local_dl, local_ul):
        self._group_rates = (internet_dl, internet_ul, local_dl, local_ul)

    # ------------------------------------------------------------------ update
    def update_rows(self, apps: List[ProcessInfo], rules: Dict[str, Rule],
                    unit_mode: str = "autoByte",
                    global_limit_in: Optional[int] = None,
                    group_totals: Optional[tuple] = None,
                    total_rates: Optional[tuple] = None):
        self.unit_mode = unit_mode
        self._paint_headings()
        q = self.search_query.lower().strip()
        i_dl, i_ul, l_dl, l_ul = self._group_rates
        t_dl, t_ul = i_dl + l_dl, i_ul + l_ul
        root_dl, root_ul = total_rates if total_rates is not None else (t_dl, t_ul)
        gt = group_totals or (0, 0, 0, 0)

        def fmt_rate(v):
            if v > 0.5:
                return format_rate(v, unit_mode)
            if unit_mode == "autoByte":
                return "0 B/s"
            if unit_mode in ("autoBit", "Mb/s"):
                return "0 bps"
            return f"0 {unit_mode}"

        def fmt(v_rate, v_total):
            if self.show_totals:
                return format_bytes(v_total)
            return fmt_rate(v_rate)

        try:
            host = get_computer_name()
        except Exception:
            host = ""
        root_label = "This PC"
        if host and host not in ("-", "This computer"):
            root_label = f"This PC  ·  {host}"
        header_ids = ("__root__", "grp:internet", "grp:local",
                      "grp:limited", "grp:blocked")
        for iid, label in (("__root__", root_label),
                           ("grp:internet", "Internet"),
                           ("grp:local", "Local network"),
                           ("grp:limited", "Limited apps"),
                           ("grp:blocked", "Blocked apps")):
            if not self.tree.exists(iid):
                self.tree.insert("", "end", iid=iid, text=label, open=True,
                                 tags=("group",))
            elif iid == "__root__":
                try:
                    self.tree.item(iid, text=label)
                except Exception:
                    pass
        self.tree.set("__root__", "dl", fmt(root_dl, sum(a.total_dl for a in apps)))
        self.tree.set("__root__", "ul", fmt(root_ul, sum(a.total_ul for a in apps)))
        if global_limit_in and global_limit_in > 0:
            try:
                self.tree.set("__root__", "rule",
                              f"↓ {format_rate(global_limit_in, unit_mode)}")
            except Exception:
                pass
        else:
            try:
                self.tree.set("__root__", "rule", "")
            except Exception:
                pass
        groups_unavailable = (
            total_rates is not None and not self.show_totals
            and (t_dl + t_ul) < 1.0 and (root_dl + root_ul) > 1.0
        )
        self.tree.set("grp:internet", "dl",
                      "—" if groups_unavailable else fmt(i_dl, gt[0]))
        self.tree.set("grp:internet", "ul",
                      "—" if groups_unavailable else fmt(i_ul, gt[1]))
        self.tree.set("grp:local", "dl",
                      "—" if groups_unavailable else fmt(l_dl, gt[2]))
        self.tree.set("grp:local", "ul",
                      "—" if groups_unavailable else fmt(l_ul, gt[3]))
        for gid in ("grp:internet", "grp:local"):
            self.tree.set(gid, "rule", "")
        limited_apps = [a for a in apps if a.name in rules and rules[a.name].enabled
                        and (rules[a.name].limit_in or rules[a.name].limit_out)]
        blocked_apps = [a for a in apps if a.name in rules and rules[a.name].enabled
                        and (rules[a.name].block_in or rules[a.name].block_out)]
        for gid, subset in (("grp:limited", limited_apps),
                            ("grp:blocked", blocked_apps)):
            self.tree.set(gid, "dl", fmt(sum(a.dl_rate for a in subset),
                                         sum(a.total_dl for a in subset)))
            self.tree.set(gid, "ul", fmt(sum(a.ul_rate for a in subset),
                                         sum(a.total_ul for a in subset)))
            self.tree.set(gid, "rule", f"{len(subset)} rule"
                                        f"{'s' if len(subset) != 1 else ''}")
        for idx, iid in enumerate(header_ids):
            try:
                if self.tree.index(iid) != idx:
                    self.tree.move(iid, "", idx)
            except Exception:
                pass

        # Filter + sort.
        rows = []
        for app in apps:
            disp = friendly_name(app.name)
            if q and q not in app.name and q not in disp.lower():
                continue
            has_rule = app.name in rules and rules[app.name].enabled
            if self.filter_mode == "Online" and not app.is_online:
                continue
            if self.filter_mode == "Offline" and app.is_online:
                continue
            if self.filter_mode == "Hidden" and (app.is_online or (app.dl_rate + app.ul_rate) > 1.0):
                continue
            if self.filter_mode == "Limited" and not has_rule:
                continue
            rows.append(app)

        if self._sort_col == "name":
            rows.sort(key=lambda a: friendly_name(a.name).lower(), reverse=self._sort_desc)
        elif self._sort_col == "ul":
            key = (lambda a: (a.total_ul, a.total_dl, a.name)) if self.show_totals \
                else (lambda a: (a.ul_rate, a.dl_rate, a.name))
            rows.sort(key=key, reverse=self._sort_desc)
        elif self._sort_col == "rule":
            rows.sort(key=lambda a: (0 if (a.name in rules and rules[a.name].enabled) else 1,
                                     -(a.dl_rate + a.ul_rate), a.name))
            if not self._sort_desc:
                rows.reverse()
        else:
            key = (lambda a: (a.total_dl, a.total_ul, a.name)) if self.show_totals \
                else (lambda a: (a.dl_rate, a.ul_rate, a.name))
            rows.sort(key=key, reverse=self._sort_desc)

        wanted = set()
        try:
            from src.utils.icons import get_app_tile
        except Exception:
            get_app_tile = None  # type: ignore
        online = 0
        limited = 0
        for row_idx, app in enumerate(rows):
            disp = friendly_name(app.name)
            iid = "app:" + app.name
            wanted.add(iid)
            active = (app.dl_rate + app.ul_rate) > 1.0
            if app.is_online:
                online += 1
            if app.name in rules and rules[app.name].enabled:
                limited += 1
            # Small dot only for apps with live traffic; keep names aligned.
            prefix = "● " if active else "  "
            label = fit_text(f"{prefix}{disp}",
                             self._col_width("#0", 210), reserve=30)
            self._label_cache[iid] = (prefix, disp)
            badge = self._badge(app, rules.get(app.name), unit_mode)
            tags = []
            if row_idx % 2 == 1:
                tags.append("alt")
            if not (active or app.is_online):
                tags.append("dim")
            tile = None
            if get_app_tile is not None:
                try:
                    tile = get_app_tile(app.name, master=self.tree, pad_right=4)
                except Exception:
                    tile = None
            img = tile if tile is not None else ""
            if tile is not None:
                self._tile_refs[iid] = tile
            if not self.tree.exists(iid):
                self.tree.insert("", "end", iid=iid, text=label, image=img,
                                 values=(fmt(app.dl_rate, app.total_dl),
                                         fmt(app.ul_rate, app.total_ul), badge),
                                 tags=tuple(tags))
            else:
                self.tree.item(iid, text=label, image=img,
                               values=(fmt(app.dl_rate, app.total_dl),
                                       fmt(app.ul_rate, app.total_ul), badge),
                               tags=tuple(tags))
            target_pos = len(header_ids) + row_idx
            try:
                if self.tree.index(iid) != target_pos:
                    self.tree.move(iid, "", target_pos)
            except Exception:
                pass

        for child in list(self.tree.get_children()):
            if child.startswith("app:") and child not in wanted:
                try:
                    self.tree.delete(child)
                except Exception:
                    pass
                try:
                    self._tile_refs.pop(child, None)
                    self._label_cache.pop(child, None)
                except Exception:
                    pass

        try:
            if rows:
                self._stats_full = (f"{len(rows)} apps · {online} online · "
                                    f"{limited} limited")
                self._stats_short = f"{len(rows)} apps"
            else:
                self._stats_full = "No results"
                self._stats_short = "No results"
            self._render_stats()
        except Exception:
            pass
        self._set_empty(not rows)

    def _render_stats(self) -> None:
        """Show the short summary when the tab is too narrow for the long one."""
        try:
            width = self.sub_bar.winfo_width()
            text = self._stats_short if width and width < 700 else self._stats_full
            self.lbl_stats.configure(text=text)
        except Exception:
            pass

    def _on_sub_bar_resize(self, event):
        if event.widget is not self.sub_bar:
            return
        self._render_stats()

    def _set_empty(self, show: bool):
        try:
            if self._empty_label is None:
                return
            if show:
                self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
                self._empty_label.lift()
            else:
                self._empty_label.place_forget()
        except Exception:
            pass

    def _badge(self, app: ProcessInfo, rule: Optional[Rule], unit_mode: str) -> str:
        if not rule or not rule.enabled:
            return ""
        if rule.block_in and rule.block_out:
            return "■  Blocked"
        if rule.block_in and not (rule.limit_in or rule.limit_out or rule.block_out):
            return "■  Block In"
        if rule.block_out and not (rule.limit_in or rule.limit_out or rule.block_in):
            return "■  Block Out"
        parts = []
        if rule.limit_in:
            parts.append(f"↓ {format_rate(rule.limit_in, unit_mode)}")
        if rule.limit_out:
            parts.append(f"↑ {format_rate(rule.limit_out, unit_mode)}")
        if rule.block_in:
            parts.append("Block In")
        if rule.block_out:
            parts.append("Block Out")
        return "   ".join(parts)

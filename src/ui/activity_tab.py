"""Activity tab 1:1 NetLimiter (Screenshots 091326 + 091342).

- Sub-toolbar: [Rate] [Status v] All/Online/Offline/Hidden + sort/refresh/gear icons
- Tree columns: Name | DL Rate autoByte (def) | UL Rate autoByte (def) | Rule Status
- Group rows: '-' root, Filters, Tags, Internet, LocalNetwork, then apps (friendly names + icons)
- Rule Status: dotted placeholders + blue down-arrow badge when limited
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional
import customtkinter as ctk

from src.core.models import ProcessInfo, Rule
from src.ui.theme import (BG_TABLE, BG_ROW_SELECTED, BORDER_COLOR, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED,
                          DOT_GREEN, DOT_GRAY, SELECT_BLUE, bind_mousewheel)
from src.utils.appinfo import get_computer_name
from src.utils.formatters import format_rate

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
    "nvcontainer.exe": "nvcontainer.exe",
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
    "doSvc".lower(): "Delivery Optimization",
    "nlsvc.exe": "NLSvc",
}


def friendly_name(exe_name: str) -> str:
    key = (exe_name or "").lower()
    if key in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[key]
    base = key[:-4] if key.endswith(".exe") else key
    if not base:
        return exe_name
    return base


def app_icon(exe_name: str) -> str:
    """Compat: dulu glyph unicode, kini "" (ikon digambar via tiles).

    Dipertahankan agar import lama tidak rusak. Ikon asli digambar oleh
    `src.utils.icons.get_app_tile()` sebagai gambar Treeview.
    """
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
        self.show_totals: bool = False  # tombol Rate: tampilkan rate vs total byte
        self._group_rates = (0.0, 0.0, 0.0, 0.0)  # internet_dl,ul,local_dl,ul
        # Sort state (klik header kolom seperti NetLimiter)
        self._sort_col: str = "dl"   # 'name' | 'dl' | 'ul' | 'rule'
        self._sort_desc: bool = True
        self._tile_refs: dict = {}  # iid -> PhotoImage (cegah GC ikon tile)
        self._build_sub_bar()
        self._build_treeview()

    # ---- sub toolbar ----
    def _build_sub_bar(self):
        from src.ui.theme import BTN_BG, BTN_HOVER, RADIUS_PILL
        self.sub_bar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self.sub_bar.pack(fill="x", padx=6, pady=(6, 4))

        # Tombol Rate: toggle tampilkan kecepatan vs total byte (fungsional).
        self.btn_rate = ctk.CTkButton(self.sub_bar, text="Rate", width=64, height=26,
                                      font=(FONT_FAMILY, 10, "bold"), fg_color=BTN_BG,
                                      hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                                      corner_radius=RADIUS_PILL, command=self._toggle_mode)
        self.btn_rate.pack(side="left", padx=2)

        self.pills = {}
        for name, w in (("All", 40), ("Online", 62), ("Offline", 62), ("Hidden", 62)):
            b = ctk.CTkButton(self.sub_bar, text=name, width=w, height=26, font=(FONT_FAMILY, 10),
                              fg_color=SELECT_BLUE if name == "All" else BTN_BG,
                              hover_color=BTN_HOVER, text_color="#ffffff",
                              corner_radius=RADIUS_PILL,
                              command=lambda n=name: self._set_filter(n))
            b.pack(side="left", padx=2)
            self.pills[name] = b

        # right icons: cycle-sort / refresh-now (keduanya fungsional)
        self.btn_sort = ctk.CTkButton(self.sub_bar, text="⇋ Sort", width=64, height=26, font=(FONT_FAMILY, 10, "bold"),
                                      fg_color=BTN_BG, hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                                      corner_radius=RADIUS_PILL, command=self.cycle_sort)
        self.btn_sort.pack(side="right", padx=2)
        self.btn_refresh = ctk.CTkButton(self.sub_bar, text="⟳", width=30, height=26, font=(FONT_FAMILY, 13),
                                        fg_color=BTN_BG, hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                                        corner_radius=RADIUS_PILL, command=self._on_refresh)
        self.btn_refresh.pack(side="right", padx=2)
        self.lbl_stats = ctk.CTkLabel(self.sub_bar, text="", font=(FONT_FAMILY, 10), text_color=TEXT_MUTED)
        self.lbl_stats.pack(side="right", padx=8)

    def _toggle_mode(self) -> None:
        """Tukar tampilan Rate <-> Total."""
        self.show_totals = not self.show_totals
        self.btn_rate.configure(text="Total" if self.show_totals else "Rate")

    def cycle_sort(self) -> None:
        """Ganti kolom sort: dl -> ul -> name -> rule (tombol ⇋)."""
        order = ["dl", "ul", "name", "rule"]
        nxt = order[(order.index(self._sort_col) + 1) % len(order)]
        self._sort_col = nxt
        self._sort_desc = True if nxt in ("dl", "ul", "rule") else False

    def _on_refresh(self) -> None:
        if self.on_refresh_requested is not None:
            self.on_refresh_requested()

    def _set_filter(self, mode):
        self.filter_mode = mode
        for k, btn in self.pills.items():
            is_active = (k == mode)
            btn.configure(fg_color=SELECT_BLUE if is_active else "#2f2f2f",
                          text_color="#ffffff",
                          font=(FONT_FAMILY, 10, "bold" if is_active else "normal"))

    # ---- tree ----
    def _build_treeview(self):
        from src.ui.theme import RADIUS_MD, ROW_ALT_BG, style_table
        # Kartu tabel: bingkai rounded + border halus
        frame = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_MD,
                             border_width=1, border_color=BORDER_COLOR)
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        style_table("NLM.Treeview", rowheight=26, font_size=11)
        cols = ("dl", "ul", "rule")
        self.tree = ttk.Treeview(frame, style="NLM.Treeview", columns=cols, show="tree headings",
                                 selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="Name", anchor="w", command=lambda: self._on_sort("name"))
        self.tree.heading("dl", text="DL Rate", anchor="e", command=lambda: self._on_sort("dl"))
        self.tree.heading("ul", text="UL Rate", anchor="e", command=lambda: self._on_sort("ul"))
        self.tree.heading("rule", text="Rule Status", anchor="w", command=lambda: self._on_sort("rule"))
        self.tree.column("#0", width=225, minwidth=150, anchor="w", stretch=True)
        self.tree.column("dl", width=135, minwidth=100, anchor="e")
        self.tree.column("ul", width=135, minwidth=100, anchor="e")
        self.tree.column("rule", width=150, minwidth=100, anchor="center")
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vs.pack(side="right", fill="y", padx=(0, 4), pady=6)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("dim", foreground="#c9c9c9")
        self.tree.tag_configure("alt", background=ROW_ALT_BG)
        self.tree.tag_configure("group", foreground=TEXT_MAIN, font=(FONT_FAMILY, 11, "bold"))
        self.tree.tag_configure("groupdim", foreground="#a8a8a8")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_sort(self, col: str) -> None:
        """Klik header: ganti kolom sort / balik arah (seperti NetLimiter)."""
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = True if col in ("dl", "ul", "rule") else False

    def reset_view(self) -> None:
        """Kembalikan tampilan Activity ke default (dipakai tombol Reset view)."""
        self._set_filter("All")
        self.search_query = ""
        if self.show_totals:
            self._toggle_mode()
        self._sort_col = "dl"
        self._sort_desc = True
        self.reset_columns()

    def reset_columns(self) -> None:
        """Kembalikan lebar kolom ke default (setelah di-drag user)."""
        try:
            self.tree.column("#0", width=225)
            self.tree.column("dl", width=135)
            self.tree.column("ul", width=135)
            self.tree.column("rule", width=150)
        except Exception:
            pass

    def _paint_headings(self) -> None:
        arrow = " ▼" if self._sort_desc else " ▲"
        names = {"name": "Name", "dl": f"DL Rate ({self.unit_mode})",
                 "ul": f"UL Rate ({self.unit_mode})", "rule": "Rule Status"}
        self.tree.heading("#0", text=names["name"] + (arrow if self._sort_col == "name" else ""))
        self.tree.heading("dl", text=names["dl"] + (arrow if self._sort_col == "dl" else ""))
        self.tree.heading("ul", text=names["ul"] + (arrow if self._sort_col == "ul" else ""))
        self.tree.heading("rule", text=names["rule"] + (arrow if self._sort_col == "rule" else ""))

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid == "__root__":
            # Baris "-" = perangkat ini (device-level, seperti NetLimiter)
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
            pass  # grup diklik: tidak ada aksi (seperti NetLimiter saat klik Internet)

    def set_group_rates(self, internet_dl, internet_ul, local_dl, local_ul):
        self._group_rates = (internet_dl, internet_ul, local_dl, local_ul)

    # ---- update ----
    def update_rows(self, apps: List[ProcessInfo], rules: Dict[str, Rule], unit_mode: str = "autoByte",
                    global_limit_in: Optional[int] = None,
                    group_totals: Optional[tuple] = None):
        self.unit_mode = unit_mode
        self._paint_headings()
        q = self.search_query.lower().strip()
        i_dl, i_ul, l_dl, l_ul = self._group_rates
        t_dl, t_ul = i_dl + l_dl, i_ul + l_ul
        gt = group_totals or (0, 0, 0, 0)

        def fmt_rate(v):
            return format_rate(v, unit_mode) if v > 0.5 else ("0 B/s" if unit_mode == "autoByte" else ("0 bps" if unit_mode in ("autoBit", "Mb/s") else f"0 {unit_mode}"))

        def fmt(v_rate, v_total):
            if self.show_totals:
                from src.utils.formatters import format_bytes
                return format_bytes(v_total)
            return fmt_rate(v_rate)

        # pastikan grup statis ada (root = nama PC dinamis, mis. "- DESKTOP-20")
        # Label teks polos (tanpa emoji) agar tidak jadi kotak/tanda-tanya.
        try:
            host = get_computer_name()
        except Exception:
            host = ""
        root_label = f"- {host}" if host and host not in ("-", "This computer") else "-"
        for iid, label in (("__root__", root_label), ("grp:filters", "Filters"), ("grp:tags", "Tags"),
                           ("grp:internet", "Internet"), ("grp:local", "LocalNetwork")):
            if not self.tree.exists(iid):
                self.tree.insert("", "end", iid=iid, text=label, open=True, tags=("group",))
            elif iid == "__root__":
                try:
                    self.tree.item(iid, text=label)
                except Exception:
                    pass
        self.tree.set("__root__", "dl", fmt(t_dl, sum(a.total_dl for a in apps)))
        self.tree.set("__root__", "ul", fmt(t_ul, sum(a.total_ul for a in apps)))
        # Badge device-level di root "-" ala NetLimiter (▼ saat dilimit)
        if global_limit_in and global_limit_in > 0:
            try:
                self.tree.set("__root__", "rule", f"▼ {format_rate(global_limit_in, unit_mode)}")
            except Exception:
                pass
        else:
            try:
                self.tree.set("__root__", "rule", "")
            except Exception:
                pass
        self.tree.set("grp:internet", "dl", fmt(i_dl, gt[0]))
        self.tree.set("grp:internet", "ul", fmt(i_ul, gt[1]))
        self.tree.set("grp:local", "dl", fmt(l_dl, gt[2]))
        self.tree.set("grp:local", "ul", fmt(l_ul, gt[3]))
        for gid in ("grp:filters", "grp:tags"):
            self.tree.set(gid, "dl", fmt(0, 0))
            self.tree.set(gid, "ul", fmt(0, 0))
            try:
                self.tree.set(gid, "rule", "")
            except Exception:
                pass
        # pindahkan grup ke atas sesuai urutan ref
        for idx, iid in enumerate(("__root__", "grp:filters", "grp:tags", "grp:internet", "grp:local")):
            try:
                self.tree.move(iid, "", idx)
            except Exception:
                pass

        # Kumpulkan kandidat (filter search + pill), lalu sort sesuai kolom aktif
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
            key = (lambda a: (a.total_ul, a.total_dl, a.name)) if self.show_totals else (lambda a: (a.ul_rate, a.dl_rate, a.name))
            rows.sort(key=key, reverse=self._sort_desc)
        elif self._sort_col == "rule":
            rows.sort(key=lambda a: (0 if (a.name in rules and rules[a.name].enabled) else 1,
                                     -(a.dl_rate + a.ul_rate), a.name))
            if not self._sort_desc:
                rows.reverse()
        else:  # 'dl' default: traffic terbesar dulu
            key = (lambda a: (a.total_dl, a.total_ul, a.name)) if self.show_totals else (lambda a: (a.dl_rate, a.ul_rate, a.name))
            rows.sort(key=key, reverse=self._sort_desc)

        wanted = set()
        try:
            from src.utils.icons import get_app_tile
        except Exception:
            get_app_tile = None  # type: ignore
        for row_idx, app in enumerate(rows):
            disp = friendly_name(app.name)
            iid = "app:" + app.name
            wanted.add(iid)
            active = (app.dl_rate + app.ul_rate) > 1.0
            # Rapi: dot hijau hanya untuk yang benar-benar aktif
            label = f"●  {disp}" if active else f"      {disp}"
            badge = self._badge(app, rules.get(app.name), unit_mode)
            tags = []
            if row_idx % 2 == 1:
                tags.append("alt")  # belang tiap baris genap
            if not (active or app.is_online):
                tags.append("dim")
            tile = None
            if get_app_tile is not None:
                try:
                    tile = get_app_tile(app.name, master=self.tree)
                except Exception:
                    tile = None
            img = tile if tile is not None else ""
            if tile is not None:
                self._tile_refs[iid] = tile
            if not self.tree.exists(iid):
                self.tree.insert("", "end", iid=iid, text=label, image=img, values=(fmt(app.dl_rate, app.total_dl), fmt(app.ul_rate, app.total_ul), badge), tags=tags)
            else:
                self.tree.item(iid, text=label, image=img, values=(fmt(app.dl_rate, app.total_dl), fmt(app.ul_rate, app.total_ul), badge), tags=tags)

        for child in list(self.tree.get_children()):
            if child.startswith("app:") and child not in wanted:
                try:
                    self.tree.delete(child)
                except Exception:
                    pass
                try:
                    self._tile_refs.pop(child, None)
                except Exception:
                    pass

        try:
            self.lbl_stats.configure(text=f"{len(rows)} apps")
        except Exception:
            pass

    def _badge(self, app: ProcessInfo, rule: Optional[Rule], unit_mode: str) -> str:
        # Rapi ala NetLimiter: kosong bila tidak ada rule, ikon/badge bila ada.
        # Glyph aman Segoe UI (▼▲■) — emoji/geometri langka jadi kotak/?.
        if not rule or not rule.enabled:
            return ""
        if rule.block_in and rule.block_out:
            return "■ Blocked"
        if rule.block_in and not (rule.limit_in or rule.limit_out or rule.block_out):
            return "■ Block In"
        if rule.block_out and not (rule.limit_in or rule.limit_out or rule.block_in):
            return "■ Block Out"
        parts = []
        if rule.limit_in:
            parts.append(f"▼ {format_rate(rule.limit_in, unit_mode)}")
        if rule.limit_out:
            parts.append(f"▲ {format_rate(rule.limit_out, unit_mode)}")
        if rule.block_in:
            parts.append("Block In")
        if rule.block_out:
            parts.append("Block Out")
        return "  ".join(parts)

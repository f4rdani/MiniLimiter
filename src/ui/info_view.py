"""Info View — right-hand inspector for apps, rules, devices and adapters.

The panel is intentionally calm: a compact header, collapsible cards, and a
single clear rule editor.  It also doubles as an overview dashboard when
nothing is selected, so the right side never looks empty.
"""

import os
import subprocess
from typing import Callable, Optional

import customtkinter as ctk

from src.core.models import ProcessInfo, Rule
from src.ui.theme import (ACCENT, BG_CARD, BG_CARD_ALT, BG_HOVER, BG_PANEL,
                          BG_TABLE, BORDER_COLOR, BORDER_STRONG, BTN_HOVER,
                          COLOR_DOWNLOAD, COLOR_UPLOAD, DOT_GRAY, DOT_GREEN,
                          FONT_FAMILY, FONT_MONO, INPUT_BG, INPUT_BORDER,
                          PRIMARY_BG, PRIMARY_HOVER, RADIUS_MD, RADIUS_PILL,
                          TEXT_DISABLED, TEXT_GREEN, TEXT_LINK, TEXT_MAIN,
                          TEXT_MUTED, TEXT_RED, TEXT_SUBTLE)
from src.utils.formatters import format_bytes, format_rate, parse_rate_string


class InfoView(ctk.CTkFrame):
    def __init__(self, master, on_rule_changed: Callable[[Rule], None],
                 on_rule_removed: Callable[[str], None],
                 on_global_changed=None,
                 on_toggle_rule=None, **kwargs):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=0, **kwargs)
        self.on_rule_changed = on_rule_changed
        self.on_rule_removed = on_rule_removed
        self.on_global_changed = on_global_changed
        self.on_toggle_rule = on_toggle_rule

        self.current_app_name: Optional[str] = None
        self.current_app_info: Optional[ProcessInfo] = None
        self.current_rule: Optional[Rule] = None
        self._device_mode: bool = False
        self._mode: str = "none"
        self._sections = {}
        self._overview_labels = {}
        self._overview_pills = {}
        self._prop_totals = {}
        self._device_lbls = {}
        self._apply_feedback = None
        self._build_shell()

    # ------------------------------------------------------------------ shell
    def _build_shell(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=42)
        header.pack(fill="x", padx=12, pady=(10, 0))
        header.pack_propagate(False)
        dot = ctk.CTkFrame(header, width=8, height=8, corner_radius=4,
                           fg_color=ACCENT)
        dot.pack(side="left", pady=(8, 0))
        ctk.CTkLabel(header, text="Info View", height=24,
                     font=(FONT_FAMILY, 13, "bold"),
                     text_color=TEXT_MAIN).pack(side="left", padx=(8, 0), pady=(1, 0))
        self.header_pill = ctk.CTkLabel(header, text="Overview", height=24,
                                        font=(FONT_FAMILY, 10, "bold"),
                                        text_color=TEXT_SUBTLE,
                                        fg_color=BG_CARD, corner_radius=RADIUS_PILL)
        self.header_pill.pack(side="right", padx=(0, 2), pady=(3, 0))
        ctk.CTkFrame(self, fg_color=BORDER_COLOR, height=1,
                     corner_radius=0).pack(fill="x", pady=(8, 0))

        self.body = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_fg_color=BG_PANEL,
            scrollbar_button_color="#2b323d",
            scrollbar_button_hover_color="#3e4857")
        self.body.pack(fill="both", expand=True, padx=(3, 0), pady=(2, 4))

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()
        self._sections = {}
        self._overview_labels = {}
        self._overview_pills = {}
        self._prop_totals = {}
        self._device_lbls = {}
        self._apply_feedback = None

    def _set_header_pill(self, text: str, bg: str = BG_CARD,
                         text_color: str = TEXT_SUBTLE):
        try:
            self.header_pill.configure(text=text, fg_color=bg, text_color=text_color)
        except Exception:
            pass

    # --------------------------------------------------------------- building
    def _title(self, kind: str, subtitle: str, accent: str = ACCENT):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(12, 3))
        bar = ctk.CTkFrame(row, width=4, height=36, corner_radius=2,
                           fg_color=accent)
        bar.pack(side="left", padx=(0, 10), pady=1)
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text=kind, height=22, anchor="w",
                     font=(FONT_FAMILY, 16, "bold"),
                     text_color=TEXT_MAIN).pack(fill="x")
        ctk.CTkLabel(txt, text=subtitle, anchor="w", justify="left",
                     font=(FONT_FAMILY, 11), text_color=TEXT_MUTED,
                     wraplength=380).pack(fill="x", pady=(1, 0))

    def _section(self, title: str, collapsed: bool = False):
        card = ctk.CTkFrame(self.body, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", padx=10, pady=(7, 0))
        head = ctk.CTkFrame(card, fg_color="transparent", height=32)
        head.pack(fill="x", padx=10, pady=(7, 0))
        head.pack_propagate(False)
        arrow = ctk.CTkLabel(head, text="▼", width=16, height=24,
                             font=(FONT_FAMILY, 9),
                             text_color=TEXT_MUTED)
        arrow.pack(side="left")
        title_lbl = ctk.CTkLabel(head, text=title, height=24,
                                 font=(FONT_FAMILY, 12, "bold"),
                                 text_color=TEXT_MUTED)
        title_lbl.pack(side="left", padx=(4, 0))
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=(3, 10))
        self._sections[title] = (head, content, arrow, collapsed)
        if collapsed:
            content.pack_forget()
            arrow.configure(text="▶")

        def _toggle(_event=None):
            _h, _b, _a, _c = self._sections[title]
            if _c:
                _b.pack(fill="x", padx=10, pady=(3, 10))
                _a.configure(text="▼")
            else:
                _b.pack_forget()
                _a.configure(text="▶")
            self._sections[title] = (_h, _b, _a, not _c)

        for widget in (head, arrow, title_lbl):
            widget.bind("<Button-1>", _toggle)
        return content

    def _kv(self, parent, rows):
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x")
        inner.grid_columnconfigure(1, weight=1)
        for i, (key, value, is_link) in enumerate(rows):
            ctk.CTkLabel(inner, text=key, font=(FONT_FAMILY, 11), height=22,
                         text_color=TEXT_SUBTLE, anchor="w", width=104
                         ).grid(row=i, column=0, padx=(0, 8), pady=2, sticky="nw")
            lbl = ctk.CTkLabel(
                inner, text=value if value not in (None, "") else "—",
                font=(FONT_FAMILY, 11), anchor="w", justify="left", height=22,
                text_color=(TEXT_LINK if is_link else TEXT_MAIN),
                wraplength=300)
            lbl.grid(row=i, column=1, pady=2, sticky="w")
        return inner

    def _link(self, parent, text, cmd):
        b = ctk.CTkButton(parent, text=text, font=(FONT_FAMILY, 11, "bold"),
                          fg_color=BG_CARD_ALT, text_color=TEXT_LINK,
                          border_width=1, border_color=BORDER_STRONG,
                          hover_color=BTN_HOVER, height=30,
                          width=max(104, 24 + 8 * len(text)),
                          anchor="center", corner_radius=6, command=cmd)
        b.pack(side="left", padx=(0, 8), pady=1)
        return b

    def _pill(self, parent, text, bg=BG_CARD_ALT, fg=TEXT_MUTED):
        lbl = ctk.CTkLabel(parent, text=text, height=24, font=(FONT_FAMILY, 10, "bold"),
                           text_color=fg, fg_color=bg, corner_radius=RADIUS_PILL)
        lbl.pack(side="left", padx=(0, 7))
        return lbl

    # ------------------------------------------------------------------ modes
    def set_none(self):
        self._clear()
        self._mode = "none"
        self.current_app_name = None
        self.current_app_info = None
        self.current_rule = None
        self._device_mode = False
        self._set_header_pill("No selection")
        self._title("Nothing selected", "Pick an app, rule or adapter to inspect it.")
        ctk.CTkLabel(self.body, text="No item selected.",
                     font=(FONT_FAMILY, 13), text_color=TEXT_SUBTLE).pack(padx=12, pady=12)

    # -------------------------------------------------------------- overview
    def set_overview(self, stats: dict):
        """Dashboard shown when no app/rule/adapter is selected (live-updates)."""
        if self._mode != "overview" or not self._overview_labels:
            self._clear()
            self._mode = "overview"
            self.current_app_name = None
            self.current_app_info = None
            self.current_rule = None
            self._device_mode = False
            self._set_header_pill("Live summary", bg="#172234", text_color=ACCENT)
            self._title("Overview", "Everything happening on this computer, right now.")
            self._build_overview()
        self._update_overview(stats or {})

    def _build_overview(self):
        # Hero: live download/upload + session totals.
        hero = ctk.CTkFrame(self.body, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        hero.pack(fill="x", padx=10, pady=(10, 0))
        grid = ctk.CTkFrame(hero, fg_color="transparent")
        grid.pack(fill="x", padx=13, pady=14)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        for col, (key, caption, color) in enumerate((
                ("dl", "↓  DOWNLOAD", COLOR_DOWNLOAD),
                ("ul", "↑  UPLOAD", COLOR_UPLOAD))):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="w", padx=(0, 8) if col == 0 else (8, 0))
            ctk.CTkLabel(cell, text=caption, height=18, font=(FONT_FAMILY, 10, "bold"),
                         text_color=color).pack(anchor="w")
            rate = ctk.CTkLabel(cell, text="0 B/s", height=32,
                                font=(FONT_FAMILY, 20, "bold"), text_color=TEXT_MAIN)
            rate.pack(anchor="w")
            total = ctk.CTkLabel(cell, text="0 B total", height=18,
                                 font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE)
            total.pack(anchor="w")
            self._overview_labels[key] = (rate, total)

        # Four small counters.
        counters = ctk.CTkFrame(self.body, fg_color="transparent")
        counters.pack(fill="x", padx=10, pady=(6, 0))
        counters.grid_columnconfigure(0, weight=1)
        counters.grid_columnconfigure(1, weight=1)
        specs = (("apps", "APPS"), ("online", "ONLINE"),
                 ("limits", "LIMITS"), ("blockers", "BLOCKERS"))
        for i, (key, caption) in enumerate(specs):
            card = ctk.CTkFrame(counters, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                                border_width=1, border_color=BORDER_COLOR)
            card.grid(row=i // 2, column=i % 2, sticky="ew",
                      padx=(0, 3) if i % 2 == 0 else (3, 0),
                      pady=(0, 3) if i < 2 else (3, 0))
            num = ctk.CTkLabel(card, text="0", height=30, font=(FONT_FAMILY, 20, "bold"),
                               text_color=TEXT_MAIN)
            num.pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=caption, height=18, font=(FONT_FAMILY, 10, "bold"),
                         text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 8))
            self._overview_labels[key] = num

        # Engine state.
        state = self._section("Engine")
        srow = ctk.CTkFrame(state, fg_color="transparent")
        srow.pack(fill="x", pady=(0, 2))
        self._overview_pills["limiter"] = self._pill(srow, "●  Limiter Off",
                                                     BG_CARD_ALT, TEXT_SUBTLE)
        self._overview_pills["blocker"] = self._pill(srow, "●  Blocker Off",
                                                     BG_CARD_ALT, TEXT_SUBTLE)
        self._overview_labels["rules"] = ctk.CTkLabel(
            state, text="0 active rules", font=(FONT_FAMILY, 11),
            text_color=TEXT_SUBTLE)
        self._overview_labels["rules"].pack(anchor="w", pady=(3, 0))
        ctk.CTkLabel(
            state,
            text="Tip: select an app in Activity to set a limit, or This PC for global.",
            font=(FONT_FAMILY, 11), text_color=TEXT_MUTED, anchor="w",
            justify="left", wraplength=340).pack(anchor="w", pady=(7, 0))

    def _update_overview(self, stats: dict):
        try:
            unit = stats.get("unit", "autoByte")
            for key in ("dl", "ul"):
                rate_lbl, total_lbl = self._overview_labels.get(key, (None, None))
                if rate_lbl is None:
                    continue
                rate_lbl.configure(text=format_rate(stats.get(f"{key}_rate", 0.0), unit))
                total_lbl.configure(text=f"{format_bytes(stats.get(f'{key}_total', 0))} total")
            for key in ("apps", "online", "limits", "blockers"):
                lbl = self._overview_labels.get(key)
                if lbl is not None:
                    lbl.configure(text=str(stats.get(key, 0)))
            rules_lbl = self._overview_labels.get("rules")
            if rules_lbl is not None:
                rules_lbl.configure(
                    text=f"{stats.get('rules', 0)} active rules · "
                         f"{stats.get('limits', 0)} limit · {stats.get('blockers', 0)} blocker")
            for key, label in (("limiter", "Limiter"), ("blocker", "Blocker")):
                pill = self._overview_pills.get(key)
                if pill is None:
                    continue
                on = bool(stats.get(key))
                pill.configure(
                    text=f"●  {label} {'On' if on else 'Off'}",
                    fg_color=("#12301f" if key == "limiter" else "#321719") if on else BG_CARD_ALT,
                    text_color=(TEXT_GREEN if key == "limiter" else TEXT_RED) if on else TEXT_SUBTLE)
        except Exception:
            pass

    # ---------------------------------------------------------------- device
    def set_device(self, global_dict: dict, total_dl: int = 0, total_ul: int = 0):
        self._clear()
        self._mode = "device"
        self.current_app_name = "__device__"
        self.current_app_info = None
        self.current_rule = None
        self._device_mode = True
        self._device_global = dict(global_dict)
        self._device_totals = (total_dl, total_ul)
        try:
            from src.utils.appinfo import get_computer_name
            host = get_computer_name()
        except Exception:
            host = "This computer"
        if not host or host.strip() in ("-", "This computer"):
            host = "This computer"
            subtitle = "Limits apply to ALL traffic on this computer."
        else:
            subtitle = f"{host}  ·  limits apply to ALL traffic"
        self._set_header_pill("Device", bg="#2c2411", text_color="#e8c34a")
        self._title("This computer", subtitle)

        info = self._section("Device")
        self._kv(info, [("Host name:", host, False)])
        trow = ctk.CTkFrame(info, fg_color="transparent")
        trow.pack(fill="x", pady=(2, 0))
        self._device_lbls["dl"] = ctk.CTkLabel(
            trow, text=f"↓ {format_bytes(total_dl)}", font=(FONT_FAMILY, 11),
            text_color=COLOR_DOWNLOAD)
        self._device_lbls["dl"].pack(side="left", padx=(0, 14))
        self._device_lbls["ul"] = ctk.CTkLabel(
            trow, text=f"↑ {format_bytes(total_ul)}", font=(FONT_FAMILY, 11),
            text_color=COLOR_UPLOAD)
        self._device_lbls["ul"].pack(side="left")

        box = self._section("Rules")
        self._build_rule_editor(box, global_dict, default_in="4 MB/s", device=True)
        tools = self._section("Tools")
        trow = ctk.CTkFrame(tools, fg_color="transparent")
        trow.pack(fill="x")
        self._link(trow, "Traffic stats", self._show_device_stats)
        self._link(trow, "Delete rules", self._clear_device)

    def _show_device_stats(self) -> None:
        try:
            from tkinter import messagebox
            g = getattr(self, "_device_global", {}) or {}
            dl, ul = getattr(self, "_device_totals", (0, 0))
            lim = g.get("limit_in")
            messagebox.showinfo(
                "Traffic stats — device",
                f"Total DL: {format_bytes(dl)}\n"
                f"Total UL: {format_bytes(ul)}\n"
                f"Global In limit: {format_rate(lim) if lim else 'Not set'}\n"
                f"Global Out limit: {format_rate(g.get('limit_out')) if g.get('limit_out') else 'Not set'}",
            )
        except Exception:
            pass

    def update_device_totals(self, total_dl: int, total_ul: int) -> None:
        self._device_totals = (total_dl, total_ul)
        try:
            if self._device_lbls.get("dl") is not None:
                self._device_lbls["dl"].configure(text=f"↓ {format_bytes(total_dl)}")
            if self._device_lbls.get("ul") is not None:
                self._device_lbls["ul"].configure(text=f"↑ {format_bytes(total_ul)}")
        except Exception:
            pass

    # ------------------------------------------------------------- app / rule
    def set_app(self, app_info: ProcessInfo, rule: Optional[Rule], file_info: Optional[dict] = None):
        self._clear()
        self._mode = "app"
        self._device_mode = False
        self.current_app_name = app_info.name
        self.current_app_info = app_info
        self.current_rule = rule
        try:
            from src.ui.activity_tab import friendly_name
            disp = friendly_name(app_info.name)
        except Exception:
            disp = app_info.name
        if rule and rule.enabled:
            badge = "Limited" if (rule.limit_in or rule.limit_out) else (
                "Blocked" if (rule.block_in or rule.block_out) else "Rule")
            self._set_header_pill(badge, bg="#172234", text_color=ACCENT)
        else:
            self._set_header_pill("Application")
        self._title("Application", app_info.exe_path or app_info.name)

        prefill = {}
        if rule is not None:
            prefill = {
                "limit_in": rule.limit_in, "limit_out": rule.limit_out,
                "block_in": rule.block_in, "block_out": rule.block_out,
            }
        # Rules first: it is the action people open this panel for.
        rbox = self._section("Rules")
        self._build_rule_editor(rbox, prefill, default_in="2 MB/s", device=False)

        box = self._section("Application properties", collapsed=True)
        fi = file_info or {}
        pids = ", ".join(map(str, sorted(list(app_info.pids))[:4])) or "—"
        self._kv(box, [
            ("Name:", disp, False),
            ("Product:", fi.get("product", "") or disp, False),
            ("Version:", fi.get("version", "") or "—", False),
            ("Company:", fi.get("company", "") or "—", False),
            ("PIDs:", pids, False),
        ])
        totals = ctk.CTkFrame(box, fg_color="transparent")
        totals.pack(fill="x", pady=(4, 0))
        self._prop_totals["dl"] = ctk.CTkLabel(
            totals, text=f"↓ {format_bytes(app_info.total_dl)}",
            font=(FONT_FAMILY, 11), text_color=COLOR_DOWNLOAD)
        self._prop_totals["dl"].pack(side="left", padx=(112, 12))
        self._prop_totals["ul"] = ctk.CTkLabel(
            totals, text=f"↑ {format_bytes(app_info.total_ul)}",
            font=(FONT_FAMILY, 11), text_color=COLOR_UPLOAD)
        self._prop_totals["ul"].pack(side="left")

        tools = self._section("Tools", collapsed=True)
        row = ctk.CTkFrame(tools, fg_color="transparent")
        row.pack(fill="x")
        for t, fn in (("Traffic stats", self._show_stats),
                      ("Delete rules", self._clear_rule)):
            self._link(row, t, fn)
        row2 = ctk.CTkFrame(tools, fg_color="transparent")
        row2.pack(fill="x", pady=(7, 0))
        for t, fn in (("Open folder", self._open_folder),
                      ("Kill process", self._kill)):
            self._link(row2, t, fn)

    def update_app_totals(self, total_dl: int, total_ul: int) -> None:
        for key, value in (("dl", total_dl), ("ul", total_ul)):
            try:
                lbl = self._prop_totals.get(key)
                if lbl is not None:
                    arrow = "↓" if key == "dl" else "↑"
                    lbl.configure(text=f"{arrow} {format_bytes(value)}")
            except Exception:
                pass

    def set_rule(self, row: dict):
        self._clear()
        self._mode = "rule"
        rtype = row.get("type", "Limit")
        self._device_mode = False
        self.current_app_name = None
        self.current_app_info = None
        rule = row.get("rule")
        self.current_rule = rule
        self._set_header_pill(rtype, bg=("#172234" if rtype == "Limit" else "#321719"),
                              text_color=(ACCENT if rtype == "Limit" else TEXT_RED))
        direction = "Incoming" if row.get("dir", "In") == "In" else "Outgoing"
        self._title("Rule", f"{rtype} · {direction}")
        box = self._section("Rule properties")
        self._kv(box, [
            ("Rule type:", rtype, False),
            ("Direction:", row.get("dir", "In"), False),
            ("State:", row.get("state", "Active"), False),
            ("Value:", row.get("value", "—"), False),
            ("Target:", row.get("for", "—"), False),
        ])
        actions = ctk.CTkFrame(self.body, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(10, 2))
        active = row.get("state", "Active") == "Active"
        action_label = "Disable rule" if active else "Enable rule"
        for t in (action_label, "Delete rule"):
            self._link(actions, t, lambda t=t: self._rule_tool(t, row))

    def _rule_tool(self, name, row):
        target = row.get("for", "")
        rule = row.get("rule")
        if not target or rule is None:
            return  # built-in Ignore row: no actions
        if name == "Delete rule":
            self.on_rule_removed(target)
            return
        enabled = name == "Enable rule"
        if self.on_toggle_rule is not None:
            self.on_toggle_rule(target, enabled)
            updated = dict(row)
            updated["state"] = "Active" if enabled else "Disabled"
            self.set_rule(updated)

    # -------------------------------------------------------------- network
    def set_network(self, nic: dict):
        self._clear()
        self._mode = "network"
        self._device_mode = False
        self.current_app_name = None
        self.current_app_info = None
        self.current_rule = None
        self._current_nic = dict(nic)
        up = bool(nic.get("is_up"))
        self._set_header_pill("● Active" if up else "○ Down",
                              bg="#12301f" if up else BG_CARD_ALT,
                              text_color=TEXT_GREEN if up else TEXT_SUBTLE)
        self._title("Network", nic.get("name", ""))
        box = self._section("Network interface")
        self._kv(box, [
            ("Id:", str(nic.get("id", "")), False),
            ("Connection:", nic.get("connection", ""), False),
            ("Interface:", nic.get("name", ""), False),
            ("IPv4:", nic.get("ip4", "") or "—", False),
            ("IPv6:", nic.get("ip6", "") or "—", False),
            ("MAC:", nic.get("mac", "") or "—", False),
            ("Link speed:", f"{nic.get('speed', 0)} Mbps" if nic.get("speed") else "—", False),
        ])
        cbox = self._section("Connected to")
        self._kv(cbox, [
            ("Wi-Fi SSID:", nic.get("ssid", "") or "—", False),
            ("Wi-Fi BSSID:", nic.get("bssid", "") or "—", False),
            ("Gateway IP:", nic.get("gateway", "") or "—", False),
        ])
        actions = ctk.CTkFrame(self.body, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(9, 2))
        self._link(actions, "Traffic stats", self._show_nic_stats)

    def _show_nic_stats(self) -> None:
        nic = getattr(self, "_current_nic", None)
        if not nic:
            return
        try:
            from tkinter import messagebox
            messagebox.showinfo(
                f"Traffic stats — {nic.get('name', '')}",
                f"Connection: {nic.get('connection', '')}\n"
                f"IP: {nic.get('ip4', '')}\n"
                f"MAC: {nic.get('mac', '')}\n"
                f"SSID: {nic.get('ssid', '') or '—'}\n"
                f"Gateway: {nic.get('gateway', '') or '—'}\n"
                f"Link speed: {nic.get('speed', 0)} Mbps",
            )
        except Exception:
            pass

    # ----------------------------------------------------- shared rule editor
    def _build_rule_editor(self, box, values: Optional[dict], default_in: str,
                           device: bool):
        values = values or {}
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 4))
        grid.grid_columnconfigure(1, weight=1)
        for col, capt in ((0, ""), (1, "LIMIT"), (2, "BLOCK")):
            ctk.CTkLabel(grid, text=capt, font=(FONT_FAMILY, 10, "bold"),
                         text_color=TEXT_SUBTLE, anchor="w"
                         ).grid(row=0, column=col, sticky="w", padx=(0, 8), pady=(0, 4))

        for row_idx, (arrow, name, in_key, block_key, ph) in enumerate((
                ("↓", "Download", "limit_in", "block_in", default_in),
                ("↑", "Upload", "limit_out", "block_out", "Not set")), start=1):
            ctk.CTkLabel(grid, text=f"{arrow}  {name}", font=(FONT_FAMILY, 11),
                         text_color=TEXT_MAIN, anchor="w"
                         ).grid(row=row_idx, column=0, sticky="w", padx=(0, 8), pady=5)
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=row_idx, column=1, sticky="w", pady=5)
            chk = ctk.CTkCheckBox(
                cell, text="", width=22, height=22, checkbox_width=20, checkbox_height=20,
                corner_radius=4, fg_color=PRIMARY_BG, hover_color=PRIMARY_HOVER,
                border_color=INPUT_BORDER, border_width=2)
            chk.pack(side="left")
            entry = ctk.CTkEntry(
                cell, width=124, height=34, font=(FONT_FAMILY, 11),
                corner_radius=7, fg_color=INPUT_BG, border_color=INPUT_BORDER,
                text_color=TEXT_MAIN, placeholder_text=ph,
                placeholder_text_color=TEXT_SUBTLE)
            entry.pack(side="left", padx=(6, 0))
            block = ctk.CTkCheckBox(
                grid, text="Block", width=78, height=22, checkbox_width=20, checkbox_height=20,
                corner_radius=4, fg_color=PRIMARY_BG, hover_color=PRIMARY_HOVER,
                border_color=INPUT_BORDER, border_width=2, font=(FONT_FAMILY, 11),
                text_color=TEXT_MUTED)
            block.grid(row=row_idx, column=2, sticky="w", padx=(8, 0), pady=5)
            if row_idx == 1:
                self.chk_limit_in, self.entry_limit_in = chk, entry
                self.chk_block_in = block
            else:
                self.chk_limit_out, self.entry_limit_out = chk, entry
                self.chk_block_out = block

        # Prefill from an existing rule / the device config.
        try:
            if values.get("block_in"):
                self.chk_block_in.select()
            if values.get("block_out"):
                self.chk_block_out.select()
            if values.get("limit_in"):
                self.chk_limit_in.select()
                self.entry_limit_in.delete(0, "end")
                self.entry_limit_in.insert(0, format_rate(values["limit_in"]))
            if values.get("limit_out"):
                self.chk_limit_out.select()
                self.entry_limit_out.delete(0, "end")
                self.entry_limit_out.insert(0, format_rate(values["limit_out"]))
        except Exception:
            pass

        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.pack(fill="x", pady=(9, 4))
        ctk.CTkButton(
            bar, text="Apply rule", height=36, font=(FONT_FAMILY, 12, "bold"),
            corner_radius=7, fg_color=PRIMARY_BG, hover_color=PRIMARY_HOVER,
            text_color="#ffffff", command=self._apply
        ).pack(side="left", expand=True, fill="x", padx=(0, 7))
        ctk.CTkButton(
            bar, text="Remove", width=82, height=36, font=(FONT_FAMILY, 11),
            corner_radius=7, fg_color=BG_CARD_ALT, hover_color=BTN_HOVER,
            border_width=1, border_color=BORDER_STRONG,
            text_color=TEXT_MAIN, command=(self._clear_device if device else self._clear_rule)
        ).pack(side="left")

        prow = ctk.CTkFrame(box, fg_color="transparent")
        prow.pack(fill="x", pady=(3, 1))
        ctk.CTkLabel(prow, text="Presets", font=(FONT_FAMILY, 10, "bold"),
                     text_color=TEXT_SUBTLE).pack(side="left", padx=(0, 7))
        presets = ("512 KB/s", "1 MB/s", "2 MB/s", "5 MB/s") if device else \
                  ("512 KB/s", "1 MB/s", "2 MB/s", "4 MB/s")
        for p in presets:
            ctk.CTkButton(
                prow, text=p, width=74, height=28, font=(FONT_FAMILY, 10),
                corner_radius=RADIUS_PILL, fg_color=BG_CARD_ALT,
                border_width=1, border_color=BORDER_COLOR,
                hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                command=lambda v=p: self._preset(v)).pack(side="left", padx=(0, 4))

        self._apply_feedback = ctk.CTkLabel(box, text="", height=20,
                                            font=(FONT_FAMILY, 11),
                                            text_color=TEXT_SUBTLE)
        self._apply_feedback.pack(anchor="w", pady=(3, 0))

    # ---------------------------------------------------------------- actions
    def _preset(self, v):
        try:
            self.chk_limit_in.select()
            self.entry_limit_in.delete(0, "end")
            self.entry_limit_in.insert(0, v)
        except Exception:
            pass
        self._apply()

    # Backward-compat with the old device preset callback.
    def _preset_device(self, v):
        self._preset(v)

    def _apply(self):
        if self._device_mode:
            self._apply_device()
            return
        if not self.current_app_name:
            return
        try:
            li = parse_rate_string(self.entry_limit_in.get().strip()) if self.chk_limit_in.get() else None
        except Exception:
            li = None
        if self.chk_limit_in.get() and not li:
            li = 2 * 1024 * 1024
        try:
            lo = parse_rate_string(self.entry_limit_out.get().strip()) if self.chk_limit_out.get() else None
        except Exception:
            lo = None
        if self.chk_limit_out.get() and not lo:
            lo = 2 * 1024 * 1024
        rule = Rule(app_name=self.current_app_name, limit_in=li, limit_out=lo,
                    block_in=bool(self.chk_block_in.get()),
                    block_out=bool(self.chk_block_out.get()), enabled=True)
        self.current_rule = rule
        self.on_rule_changed(rule)
        self._feedback("✓ Rule applied", TEXT_GREEN)

    def _apply_device(self):
        if self.on_global_changed is None:
            return
        try:
            li = parse_rate_string(self.entry_limit_in.get().strip()) if self.chk_limit_in.get() else None
        except Exception:
            li = None
        if self.chk_limit_in.get() and not li:
            li = 4 * 1024 * 1024
        try:
            lo = parse_rate_string(self.entry_limit_out.get().strip()) if self.chk_limit_out.get() else None
        except Exception:
            lo = None
        if self.chk_limit_out.get() and not lo:
            lo = 4 * 1024 * 1024
        self.on_global_changed(li, lo, bool(self.chk_block_in.get()),
                               bool(self.chk_block_out.get()))
        self._feedback("✓ Device rule applied", TEXT_GREEN)

    def _clear_rule(self):
        if self.current_app_name:
            self.on_rule_removed(self.current_app_name)
            self._feedback("✓ Rule removed", TEXT_MUTED)

    def _clear_device(self):
        if self.on_global_changed is not None:
            self.on_global_changed(None, None, False, False)
            self._feedback("✓ Device limit cleared", TEXT_MUTED)

    def _feedback(self, text, color=TEXT_SUBTLE):
        try:
            if self._apply_feedback is not None:
                self._apply_feedback.configure(text=text, text_color=color)
        except Exception:
            pass

    # ------------------------------------------------------------------ tools
    def _open_folder(self):
        if self.current_app_info and self.current_app_info.exe_path:
            folder = os.path.dirname(self.current_app_info.exe_path)
            if os.path.exists(folder):
                subprocess.run(f'explorer "{folder}"', shell=True)

    def _show_stats(self):
        if not self.current_app_info:
            return
        try:
            from tkinter import messagebox
            i = self.current_app_info
            messagebox.showinfo(
                f"Traffic stats — {i.name}",
                f"DL: {format_rate(i.dl_rate)} ({format_bytes(i.total_dl)})\n"
                f"UL: {format_rate(i.ul_rate)} ({format_bytes(i.total_ul)})")
        except Exception:
            pass

    def _kill(self):
        if not self.current_app_info:
            return
        try:
            from tkinter import messagebox
            import psutil
            pids = sorted(list(self.current_app_info.pids))[:8]
            if pids and messagebox.askyesno(
                    "Kill process",
                    f"Terminate process {self.current_app_info.name}?\nPIDs: {pids}"):
                for pid in pids:
                    try:
                        psutil.Process(pid).terminate()
                    except Exception:
                        pass
        except Exception:
            pass

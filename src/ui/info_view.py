"""Info View 1:1 NetLimiter (Screenshots 091326/091342/091400/091445).

Modes: application | rule | network | none
Collapsible sections (^ collapsed state), blue links, Rules grid Type/In/Out.
"""

import os
import subprocess
from typing import Callable, Optional
import customtkinter as ctk

from src.core.models import ProcessInfo, Rule
from src.ui.theme import BG_PANEL, BG_TABLE, BORDER_COLOR, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, TEXT_LINK
from src.utils.formatters import format_rate, format_bytes, parse_rate_string


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
        self._sections = {}
        self._build_shell()

    # ---------- shell ----------
    def _build_shell(self):
        top = ctk.CTkFrame(self, fg_color="transparent", height=26)
        top.pack(fill="x", padx=6, pady=(4, 0))
        ctk.CTkLabel(top, text="Info View", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MAIN).pack(side="left")
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=2, pady=2)

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()
        self._sections = {}

    def _section(self, title: str, collapsed: bool = False):
        head = ctk.CTkFrame(self.body, fg_color="transparent")
        head.pack(fill="x", padx=6, pady=(8, 2))
        arrow = ctk.CTkLabel(head, text="﹀" if collapsed else "︿", font=(FONT_FAMILY, 11), text_color=TEXT_MUTED, width=18)
        arrow.pack(side="left")
        ctk.CTkLabel(head, text=title, font=(FONT_FAMILY, 11), text_color=TEXT_MUTED).pack(side="left")
        box = ctk.CTkFrame(self.body, fg_color=BG_TABLE, corner_radius=3, border_width=1, border_color=BORDER_COLOR)
        if not collapsed:
            box.pack(fill="x", padx=6, pady=2)
        self._sections[title] = (head, box, collapsed)

        def _toggle(_e=None):
            h, b, c = self._sections[title]
            if c:
                b.pack(fill="x", padx=6, pady=2)
                arrow.configure(text="︿")
            else:
                b.pack_forget()
                arrow.configure(text="﹀")
            self._sections[title] = (h, b, not c)
        head.bind("<Button-1>", _toggle)
        arrow.bind("<Button-1>", _toggle)
        return box

    def _kv(self, parent, rows):
        for i, (k, v, is_link) in enumerate(rows):
            ctk.CTkLabel(parent, text=k, font=(FONT_FAMILY, 11), text_color=TEXT_MUTED, anchor="w", width=110).grid(row=i, column=0, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(parent, text=v, font=(FONT_FAMILY, 11), text_color=(TEXT_LINK if is_link else TEXT_MAIN),
                         anchor="w", wraplength=230).grid(row=i, column=1, padx=8, pady=2, sticky="w")

    def _link(self, parent, text, cmd):
        b = ctk.CTkButton(parent, text=text, font=(FONT_FAMILY, 11), fg_color="transparent",
                          text_color=TEXT_LINK, hover_color="#333333", height=18, anchor="w", command=cmd)
        b.pack(side="left", padx=(6, 2), pady=2)
        return b

    def _title(self, kind: str, subtitle: str):
        ctk.CTkLabel(self.body, text=kind, font=(FONT_FAMILY, 13, "bold"), text_color=TEXT_LINK, anchor="w").pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(self.body, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_MAIN, anchor="w", wraplength=320).pack(fill="x", padx=8, pady=(0, 2))

    # ---------- modes ----------
    def set_none(self):
        self._clear()
        self.current_app_name = None
        self.current_app_info = None
        self.current_rule = None
        self._device_mode = False
        ctk.CTkLabel(self.body, text="Select an item to view details.", font=(FONT_FAMILY, 11), text_color=TEXT_MUTED).pack(padx=8, pady=12)

    def set_device(self, global_dict: dict, total_dl: int = 0, total_ul: int = 0):
        """Editor device-level (baris '-' = perangkat ini, seperti NetLimiter).

        global_dict: {limit_in, limit_out, block_in, block_out}
        """
        self._clear()
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
        self._title("Device", f"{host} (-) — limit applies to ALL traffic")
        box = self._section("Rules")
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=6, pady=4)
        for c, t in enumerate(("Type", "In", "Out")):
            ctk.CTkLabel(grid, text=t, font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MUTED).grid(row=0, column=c, padx=4, pady=2, sticky="w")
        ctk.CTkLabel(grid, text="Blocker", font=(FONT_FAMILY, 11), text_color=TEXT_MAIN).grid(row=1, column=0, padx=4, pady=3, sticky="w")
        self.chk_block_in = ctk.CTkCheckBox(grid, text="Block", font=(FONT_FAMILY, 11), width=20)
        self.chk_block_in.grid(row=1, column=1, padx=4, pady=3, sticky="w")
        self.chk_block_out = ctk.CTkCheckBox(grid, text="Block", font=(FONT_FAMILY, 11), width=20)
        self.chk_block_out.grid(row=1, column=2, padx=4, pady=3, sticky="w")
        ctk.CTkLabel(grid, text="Limit", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MAIN).grid(row=2, column=0, padx=4, pady=3, sticky="w")
        fi = ctk.CTkFrame(grid, fg_color="transparent")
        fi.grid(row=2, column=1, padx=2, pady=3, sticky="w")
        self.chk_limit_in = ctk.CTkCheckBox(fi, text="", width=18)
        self.chk_limit_in.pack(side="left")
        self.entry_limit_in = ctk.CTkEntry(fi, width=70, height=22, font=(FONT_FAMILY, 11), placeholder_text="4 MB/s")
        self.entry_limit_in.pack(side="left", padx=(2, 0))
        fo = ctk.CTkFrame(grid, fg_color="transparent")
        fo.grid(row=2, column=2, padx=2, pady=3, sticky="w")
        self.chk_limit_out = ctk.CTkCheckBox(fo, text="", width=18)
        self.chk_limit_out.pack(side="left")
        self.entry_limit_out = ctk.CTkEntry(fo, width=70, height=22, font=(FONT_FAMILY, 11), placeholder_text="Not set")
        self.entry_limit_out.pack(side="left", padx=(2, 0))
        # prefill
        try:
            if global_dict.get("block_in"):
                self.chk_block_in.select()
            if global_dict.get("block_out"):
                self.chk_block_out.select()
            if global_dict.get("limit_in"):
                self.chk_limit_in.select()
                self.entry_limit_in.delete(0, "end")
                self.entry_limit_in.insert(0, format_rate(global_dict["limit_in"]))
            if global_dict.get("limit_out"):
                self.chk_limit_out.select()
                self.entry_limit_out.delete(0, "end")
                self.entry_limit_out.insert(0, format_rate(global_dict["limit_out"]))
        except Exception:
            pass
        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 2))
        ctk.CTkButton(bar, text="Apply Rule", height=24, font=(FONT_FAMILY, 11, "bold"), command=self._apply_device).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(bar, text="Clear", width=56, height=24, font=(FONT_FAMILY, 11), fg_color="#444444", hover_color="#555555", command=self._clear_device).pack(side="left")
        prow = ctk.CTkFrame(box, fg_color="transparent")
        prow.pack(fill="x", padx=6, pady=(2, 6))
        ctk.CTkLabel(prow, text="Presets:", font=(FONT_FAMILY, 10), text_color=TEXT_MUTED).pack(side="left")
        for p in ("1 MB/s", "2 MB/s", "4 MB/s", "10 MB/s"):
            ctk.CTkButton(prow, text=p, width=62, height=20, font=(FONT_FAMILY, 10), fg_color="#333333",
                          hover_color="#444444", command=lambda v=p: self._preset_device(v)).pack(side="left", padx=2)
        tbox = self._section("Tools")
        trow = ctk.CTkFrame(tbox, fg_color="transparent")
        trow.pack(fill="x")
        for t in ("Traffic stats", "Delete rules"):
            self._link(trow, t, lambda t=t: self._device_tool(t))

    def _preset_device(self, v):
        try:
            self.chk_limit_in.select()
            self.entry_limit_in.delete(0, "end")
            self.entry_limit_in.insert(0, v)
        except Exception:
            pass
        self._apply_device()

    def _apply_device(self):
        if self.on_global_changed is None:
            return
        try:
            li = parse_rate_string(self.entry_limit_in.get().strip()) if self.chk_limit_in.get() else None
        except Exception:
            li = 4 * 1024 * 1024
        try:
            lo = parse_rate_string(self.entry_limit_out.get().strip()) if self.chk_limit_out.get() else None
        except Exception:
            lo = None
        self.on_global_changed(li, lo, bool(self.chk_block_in.get()), bool(self.chk_block_out.get()))

    def _clear_device(self):
        if self.on_global_changed is not None:
            self.on_global_changed(None, None, False, False)

    def _device_tool(self, name):
        if name == "Delete rules" and self.on_global_changed is not None:
            self.on_global_changed(None, None, False, False)
        elif name == "Traffic stats":
            self._show_device_stats()

    def update_device_totals(self, total_dl: int, total_ul: int) -> None:
        """Segarkan angka untuk popup Traffic stats perangkat."""
        self._device_totals = (total_dl, total_ul)

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

    def set_app(self, app_info: ProcessInfo, rule: Optional[Rule], file_info: Optional[dict] = None):
        self._clear()
        self._device_mode = False
        self.current_app_name = app_info.name
        self.current_app_info = app_info
        self.current_rule = rule
        try:
            from src.ui.activity_tab import friendly_name
            disp = friendly_name(app_info.name)
        except Exception:
            disp = app_info.name
        self._title("Application", app_info.exe_path or app_info.name)
        # Application properties
        box = self._section("Application properties")
        fi = file_info or {}
        pids = ", ".join(map(str, sorted(list(app_info.pids))[:4])) or "—"
        self._kv(box, [
            ("Name:", disp, False),
            ("Product:", fi.get("product", disp), False),
            ("Version:", fi.get("version", "") or "—", False),
            ("Company:", fi.get("company", "") or "—", False),
            ("PIDs:", pids, False),
            ("Total DL:", format_bytes(app_info.total_dl), False),
            ("Total UL:", format_bytes(app_info.total_ul), False),
        ])
        self._rules_editor(default_in="2 MB/s")
        tools = self._section("Tools")
        row = ctk.CTkFrame(tools, fg_color="transparent")
        row.pack(fill="x")
        for t, fn in (("Traffic stats", self._show_stats),
                      ("Delete rules", self._clear_rule), ("Open folder", self._open_folder),
                      ("Kill process", self._kill)):
            self._link(row, t, fn)

    def set_rule(self, row: dict):
        """row dari RuleListTab: {kind,type,dir,for,value,state,rule?}"""
        self._clear()
        rtype = row.get("type", "Limit")
        self._title("Rule", rtype)
        box = self._section("Rule properties")
        rule = row.get("rule")
        created = updated = "—"
        try:
            if rule is not None:
                import json, os
                from pathlib import Path
                p = Path("config/rules.json")
                if p.exists():
                    created = updated = "—"
        except Exception:
            pass
        self._kv(box, [
            ("Rule Type:", rtype, False),
            ("Direction:", row.get("dir", "In"), False),
            ("State:", row.get("state", "Active"), False),
            ("Value:", row.get("value", ""), False),
            ("Created:", created, False),
            ("Updated:", updated, False),
        ])
        fbox = self._section("For")
        frow = ctk.CTkFrame(fbox, fg_color="transparent")
        frow.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(frow, text="Filter Name:", font=(FONT_FAMILY, 11), text_color=TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(frow, text=row.get("for", ""), font=(FONT_FAMILY, 11), text_color=TEXT_LINK).pack(side="left", padx=(6, 0))
        tbox = self._section("Tools")
        trow = ctk.CTkFrame(tbox, fg_color="transparent")
        trow.pack(fill="x")
        for t in ("Enable rule", "Disable rule", "Delete rule"):
            self._link(trow, t, lambda t=t: self._rule_tool(t, row))

    def set_network(self, nic: dict):
        self._clear()
        self._device_mode = False
        self.current_app_name = None
        self.current_app_info = None
        self.current_rule = None
        self._current_nic = dict(nic)
        self._title("Network", nic.get("name", ""))
        box = self._section("Network interface")
        self._kv(box, [
            ("Id:", str(nic.get("id", "")), False),
            ("Connection:", nic.get("connection", ""), False),
            ("Interface:", nic.get("name", ""), False),
            ("IP:", nic.get("ip4", ""), False),
            ("MAC:", nic.get("mac", ""), False),
        ])
        cbox = self._section("Connected to")
        self._kv(cbox, [
            ("WiFi SSID:", nic.get("ssid", "") or "—", False),
            ("Gateway IP:", nic.get("gateway", "") or "—", False),
        ])
        tbox = self._section("Tools")
        trow = ctk.CTkFrame(tbox, fg_color="transparent")
        trow.pack(fill="x")
        self._link(trow, "Traffic stats", self._show_nic_stats)

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

    # ---------- rules editor (grid ala NetLimiter) ----------
    def _rules_editor(self, default_in="2 MB/s"):
        box = self._section("Rules")
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=6, pady=4)
        for c, t in enumerate(("Type", "In", "Out")):
            ctk.CTkLabel(grid, text=t, font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MUTED).grid(row=0, column=c, padx=4, pady=2, sticky="w")
        # Blocker
        ctk.CTkLabel(grid, text="Blocker", font=(FONT_FAMILY, 11), text_color=TEXT_MAIN).grid(row=1, column=0, padx=4, pady=3, sticky="w")
        self.chk_block_in = ctk.CTkCheckBox(grid, text="○ Not set", font=(FONT_FAMILY, 11), width=20)
        self.chk_block_in.grid(row=1, column=1, padx=4, pady=3, sticky="w")
        self.chk_block_out = ctk.CTkCheckBox(grid, text="○ Not set", font=(FONT_FAMILY, 11), width=20)
        self.chk_block_out.grid(row=1, column=2, padx=4, pady=3, sticky="w")
        # Limit
        ctk.CTkLabel(grid, text="Limit", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MAIN).grid(row=2, column=0, padx=4, pady=3, sticky="w")
        fi = ctk.CTkFrame(grid, fg_color="transparent")
        fi.grid(row=2, column=1, padx=2, pady=3, sticky="w")
        self.chk_limit_in = ctk.CTkCheckBox(fi, text="", width=18)
        self.chk_limit_in.pack(side="left")
        self.entry_limit_in = ctk.CTkEntry(fi, width=70, height=22, font=(FONT_FAMILY, 11), placeholder_text=default_in)
        self.entry_limit_in.pack(side="left", padx=(2, 0))
        fo = ctk.CTkFrame(grid, fg_color="transparent")
        fo.grid(row=2, column=2, padx=2, pady=3, sticky="w")
        self.chk_limit_out = ctk.CTkCheckBox(fo, text="", width=18)
        self.chk_limit_out.pack(side="left")
        self.entry_limit_out = ctk.CTkEntry(fo, width=70, height=22, font=(FONT_FAMILY, 11), placeholder_text="Not set")
        self.entry_limit_out.pack(side="left", padx=(2, 0))
        # prefill dari rule aktif
        r = self.current_rule
        if r is not None:
            try:
                if r.block_in:
                    self.chk_block_in.select()
                if r.block_out:
                    self.chk_block_out.select()
                if r.limit_in:
                    self.chk_limit_in.select()
                    self.entry_limit_in.delete(0, "end")
                    self.entry_limit_in.insert(0, format_rate(r.limit_in))
                if r.limit_out:
                    self.chk_limit_out.select()
                    self.entry_limit_out.delete(0, "end")
                    self.entry_limit_out.insert(0, format_rate(r.limit_out))
            except Exception:
                pass
        # Apply + presets
        bar = ctk.CTkFrame(box, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 2))
        ctk.CTkButton(bar, text="Apply Rule", height=24, font=(FONT_FAMILY, 11, "bold"), command=self._apply).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(bar, text="Clear", width=56, height=24, font=(FONT_FAMILY, 11), fg_color="#444444", hover_color="#555555", command=self._clear_rule).pack(side="left")
        prow = ctk.CTkFrame(box, fg_color="transparent")
        prow.pack(fill="x", padx=6, pady=(2, 6))
        ctk.CTkLabel(prow, text="Presets:", font=(FONT_FAMILY, 10), text_color=TEXT_MUTED).pack(side="left")
        for p in ("512 KB/s", "1 MB/s", "2 MB/s", "4 MB/s"):
            ctk.CTkButton(prow, text=p, width=62, height=20, font=(FONT_FAMILY, 10), fg_color="#333333",
                          hover_color="#444444", command=lambda v=p: self._preset(v)).pack(side="left", padx=2)
        ctk.CTkButton(box, text="Add rule", font=(FONT_FAMILY, 11), fg_color="transparent",
                      text_color=TEXT_LINK, height=18, anchor="w", command=self._apply).pack(anchor="w", padx=6, pady=(0, 4))

    # ---------- actions ----------
    def _preset(self, v):
        try:
            self.chk_limit_in.select()
            self.entry_limit_in.delete(0, "end")
            self.entry_limit_in.insert(0, v)
        except Exception:
            pass
        self._apply()

    def _apply(self):
        if self._device_mode:
            self._apply_device()
            return
        if not self.current_app_name:
            return
        try:
            li = parse_rate_string(self.entry_limit_in.get().strip()) if self.chk_limit_in.get() else None
        except Exception:
            li = 2 * 1024 * 1024
        try:
            lo = parse_rate_string(self.entry_limit_out.get().strip()) if self.chk_limit_out.get() else None
        except Exception:
            lo = None
        rule = Rule(app_name=self.current_app_name, limit_in=li, limit_out=lo,
                    block_in=bool(self.chk_block_in.get()), block_out=bool(self.chk_block_out.get()), enabled=True)
        self.current_rule = rule
        self.on_rule_changed(rule)

    def _clear_rule(self):
        if self.current_app_name:
            self.on_rule_removed(self.current_app_name)

    def _rule_tool(self, name, row):
        target = row.get("for", "")
        rule = row.get("rule")
        if not target or rule is None:
            return  # baris Ignore bawaan: tidak ada aksi
        if name == "Delete rule":
            self.on_rule_removed(target)
        elif name == "Enable rule" and self.on_toggle_rule is not None:
            self.on_toggle_rule(target, True)
        elif name == "Disable rule" and self.on_toggle_rule is not None:
            self.on_toggle_rule(target, False)

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
            messagebox.showinfo(f"Traffic stats — {i.name}",
                                f"DL: {format_rate(i.dl_rate)} ({format_bytes(i.total_dl)})\nUL: {format_rate(i.ul_rate)} ({format_bytes(i.total_ul)})")
        except Exception:
            pass

    def _kill(self):
        if not self.current_app_info:
            return
        try:
            from tkinter import messagebox
            import psutil
            pids = sorted(list(self.current_app_info.pids))[:8]
            if pids and messagebox.askyesno("Kill process", f"Terminate process {self.current_app_info.name}?\nPIDs: {pids}"):
                for pid in pids:
                    try:
                        psutil.Process(pid).terminate()
                    except Exception:
                        pass
        except Exception:
            pass

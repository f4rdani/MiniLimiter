"""Blocker tab: daftar aturan block yang benar-benar aktif (fungsional).

Hanya menampilkan rule dengan block_in/block_out. Klik baris -> Info View.
"""

from tkinter import ttk
from typing import Callable, List, Optional
import customtkinter as ctk

from src.core.models import Rule
from src.ui.theme import BG_TABLE, BG_ROW_SELECTED, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, TEXT_GREEN, bind_mousewheel


class BlockerTab(ctk.CTkFrame):
    def __init__(self, master, on_rule_selected: Optional[Callable[[dict], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_rule_selected = on_rule_selected
        self._rows: list = []
        style = ttk.Style()
        style.configure("BL.Treeview", background=BG_TABLE, foreground=TEXT_MAIN,
                        fieldbackground=BG_TABLE, rowheight=24, font=(FONT_FAMILY, 10), borderwidth=0)
        style.configure("BL.Treeview.Heading", background="#2d2d2d", foreground=TEXT_MUTED,
                        font=(FONT_FAMILY, 10, "bold"), relief="raised", borderwidth=1)
        style.map("BL.Treeview", background=[("selected", BG_ROW_SELECTED)],
                  foreground=[("selected", "#ffffff")])
        cols = ("type", "dir", "for_", "value", "state")
        self.tree = ttk.Treeview(self, style="BL.Treeview", columns=cols, show="headings",
                                 selectmode="browse", takefocus=0)
        for c, t, w in (("type", "Type", 80), ("dir", "Dir", 60), ("for_", "For", 220),
                        ("value", "Value", 110), ("state", "State", 80)):
            self.tree.heading(c, text=t, anchor="w")
            self.tree.column(c, width=w, anchor="w", stretch=(c == "for_"))
        self.tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        bind_mousewheel(self.tree)
        self.tree.tag_configure("active", foreground=TEXT_GREEN)
        self.tree.tag_configure("alt", background="#242424")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.on_rule_selected:
            return
        try:
            idx = self.tree.index(sel[0])
            if 0 <= idx < len(self._rows):
                self.on_rule_selected(self._rows[idx])
        except Exception:
            pass

    def get_selected(self) -> dict:
        sel = self.tree.selection()
        if not sel:
            return {}
        try:
            return self._rows[self.tree.index(sel[0])]
        except Exception:
            return {}

    def reset_columns(self) -> None:
        try:
            for c, w in (("type", 80), ("dir", 60), ("for_", 220), ("value", 110), ("state", 80)):
                self.tree.column(c, width=w)
        except Exception:
            pass

    def update_blockers(self, rules: List[Rule]) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows = []
        n = 0
        for rule in sorted(rules, key=lambda r: r.app_name):
            state = "Active" if rule.enabled else "Disabled"
            for direction, blocked in (("In", rule.block_in), ("Out", rule.block_out)):
                if not blocked:
                    continue
                tags = []
                if n % 2 == 1:
                    tags.append("alt")
                if rule.enabled:
                    tags.append("active")
                self.tree.insert("", "end", values=("Blocker", direction, rule.app_name, "Blocked", state), tags=tuple(tags))
                self._rows.append({"kind": "blocker", "type": "Blocker", "dir": direction,
                                   "for": rule.app_name, "value": "Blocked",
                                   "state": state, "rule": rule})
                n += 1

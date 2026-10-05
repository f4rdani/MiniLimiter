"""Rule List tab: semua aturan limit/blocker + status (fungsional).

Hanya kolom yang berisi data nyata (Type | Dir | For | Value | State).
"""

from tkinter import ttk
from typing import Callable, List, Optional
import customtkinter as ctk

from src.core.models import Rule
from src.ui.theme import BG_TABLE, BG_ROW_SELECTED, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, TEXT_GREEN, bind_mousewheel
from src.utils.formatters import format_rate


class RuleListTab(ctk.CTkFrame):
    def __init__(self, master, on_delete_rule: Callable[[str], None],
                 on_toggle_rule: Callable[[str], None],
                 on_rule_selected: Optional[Callable[[dict], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_delete_rule = on_delete_rule
        self.on_toggle_rule = on_toggle_rule
        self.on_rule_selected = on_rule_selected
        self._rows: list = []  # list of dicts {kind, rule?}
        self._build()

    def _build(self):
        style = ttk.Style()
        style.configure("RL.Treeview", background=BG_TABLE, foreground=TEXT_MAIN,
                        fieldbackground=BG_TABLE, rowheight=26, font=(FONT_FAMILY, 11), borderwidth=0)
        style.configure("RL.Treeview.Heading", background="#2d2d2d", foreground=TEXT_MUTED,
                        font=(FONT_FAMILY, 11, "bold"), relief="raised", borderwidth=1)
        style.map("RL.Treeview", background=[("selected", BG_ROW_SELECTED)],
                  foreground=[("selected", "#ffffff")])
        cols = ("type", "dir", "for_", "value", "state")
        self.tree = ttk.Treeview(self, style="RL.Treeview", columns=cols, show="headings", selectmode="browse", takefocus=0)
        widths = {"type": 90, "dir": 60, "for_": 240, "value": 130, "state": 90}
        heads = {"type": "Type", "dir": "Dir", "for_": "For", "value": "Value", "state": "State"}
        for c in cols:
            self.tree.heading(c, text=heads[c], anchor="w")
            self.tree.column(c, width=widths[c], anchor="w", stretch=(c == "for_"))
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        bind_mousewheel(self.tree)
        self.tree.tag_configure("active", foreground=TEXT_GREEN)
        self.tree.tag_configure("alt", background="#242424")
        self.tree.tag_configure("selblue", background=BG_ROW_SELECTED)
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

    def reset_columns(self) -> None:
        try:
            for c, w in (("type", 90), ("dir", 60), ("for_", 240), ("value", 130), ("state", 90)):
                self.tree.column(c, width=w)
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

    def update_rules(self, rules: List[Rule]) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows = []
        n = 0
        for rule in sorted(rules, key=lambda r: r.app_name):
            state_text = "Active" if rule.enabled else "Disabled"
            base = ["alt"] if n % 2 == 1 else []
            if rule.enabled:
                base.append("active")
            tags = tuple(base)
            if rule.limit_in:
                self.tree.insert("", "end", values=("Limit", "In", rule.app_name, format_rate(rule.limit_in), state_text), tags=tags)
                self._rows.append({"kind": "limit", "type": "Limit", "dir": "In", "for": rule.app_name,
                                   "value": format_rate(rule.limit_in), "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.limit_out:
                self.tree.insert("", "end", values=("Limit", "Out", rule.app_name, format_rate(rule.limit_out), state_text), tags=tags)
                self._rows.append({"kind": "limit", "type": "Limit", "dir": "Out", "for": rule.app_name,
                                   "value": format_rate(rule.limit_out), "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.block_in:
                self.tree.insert("", "end", values=("Blocker", "In", rule.app_name, "Blocked", state_text), tags=tags)
                self._rows.append({"kind": "blocker", "type": "Blocker", "dir": "In", "for": rule.app_name,
                                   "value": "Blocked", "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.block_out:
                self.tree.insert("", "end", values=("Blocker", "Out", rule.app_name, "Blocked", state_text), tags=tags)
                self._rows.append({"kind": "blocker", "type": "Blocker", "dir": "Out", "for": rule.app_name,
                                   "value": "Blocked", "state": state_text, "rule": rule})
                n += 1
            if not rule.limit_in and not rule.limit_out and not rule.block_in and not rule.block_out:
                self.tree.insert("", "end", values=("Limit", "In", rule.app_name, "Not set", state_text), tags=tags)
                self._rows.append({"kind": "limit", "type": "Limit", "dir": "In", "for": rule.app_name,
                                   "value": "Not set", "state": state_text, "rule": rule})
                n += 1

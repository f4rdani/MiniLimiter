"""Rules tab (gabungan Rule List + Blocker).

Satu-satunya daftar aturan: Limit (In/Out) + Blocker (In/Out) dengan
filter All | Limit | Blocker di atas tabel. Kolom: Type | Dir | For | Value | State.
"""

from tkinter import ttk
from typing import Callable, List, Optional
import customtkinter as ctk

from src.core.models import Rule
from src.ui.theme import BG_TABLE, BG_ROW_SELECTED, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, TEXT_GREEN, bind_mousewheel
from src.utils.formatters import format_rate

FILTERS = ("All", "Limit", "Blocker")


class RuleListTab(ctk.CTkFrame):
    def __init__(self, master, on_delete_rule: Callable[[str], None],
                 on_toggle_rule: Callable[[str], None],
                 on_rule_selected: Optional[Callable[[dict], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_delete_rule = on_delete_rule
        self.on_toggle_rule = on_toggle_rule
        self.on_rule_selected = on_rule_selected
        self._rows: list = []  # list of dicts {kind, rule?}
        self._all_rules: List[Rule] = []
        self.filter_mode: str = "All"
        self._filter_btns: dict = {}
        self._build()

    def _build(self):
        from src.ui.theme import BTN_BG, BTN_HOVER, RADIUS_MD, RADIUS_PILL, style_table
        # Filter bar: All | Limit | Blocker (pengganti tab Blocker terpisah)
        fbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        fbar.pack(fill="x", padx=6, pady=(6, 4))
        ctk.CTkLabel(fbar, text="Show:", font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(4, 4))
        for mode in FILTERS:
            b = ctk.CTkButton(fbar, text=mode, width=76, height=26, font=(FONT_FAMILY, 11),
                              fg_color=BTN_BG, hover_color=BTN_HOVER, text_color=TEXT_MAIN,
                              corner_radius=RADIUS_PILL,
                              command=lambda m=mode: self.set_filter(m))
            b.pack(side="left", padx=2)
            self._filter_btns[mode] = b
        self._paint_filter()

        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_MD,
                            border_width=1, border_color="#3c3c3c")
        card.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        style_table("RL.Treeview", rowheight=26, font_size=11)
        cols = ("type", "dir", "for_", "value", "state")
        self.tree = ttk.Treeview(card, style="RL.Treeview", columns=cols, show="headings", selectmode="browse", takefocus=0)
        widths = {"type": 90, "dir": 60, "for_": 240, "value": 130, "state": 90}
        heads = {"type": "Type", "dir": "Dir", "for_": "For", "value": "Value", "state": "State"}
        for c in cols:
            self.tree.heading(c, text=heads[c], anchor="w")
            self.tree.column(c, width=widths[c], anchor="w", stretch=(c == "for_"))
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb.pack(side="right", fill="y", padx=(0, 4), pady=6)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("active", foreground=TEXT_GREEN)
        self.tree.tag_configure("alt", background="#232323")
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

    def _paint_filter(self) -> None:
        from src.ui.theme import BTN_BG
        for mode, btn in self._filter_btns.items():
            try:
                if mode == self.filter_mode:
                    btn.configure(fg_color="#c9b400", text_color="#000000",
                                  font=(FONT_FAMILY, 11, "bold"))
                else:
                    btn.configure(fg_color=BTN_BG, text_color=TEXT_MAIN,
                                  font=(FONT_FAMILY, 11))
            except Exception:
                pass

    def set_filter(self, mode: str) -> None:
        if mode not in FILTERS:
            return
        self.filter_mode = mode
        self._paint_filter()
        self._render()

    def reset_columns(self) -> None:
        try:
            for c, w in (("type", 90), ("dir", 60), ("for_", 240), ("value", 130), ("state", 90)):
                self.tree.column(c, width=w)
        except Exception:
            pass

    def reset_view(self) -> None:
        """Kembalikan filter ke All + lebar kolom default."""
        self.filter_mode = "All"
        try:
            self._paint_filter()
        except Exception:
            pass
        self.reset_columns()
        self._render()

    def get_selected(self) -> dict:
        sel = self.tree.selection()
        if not sel:
            return {}
        try:
            return self._rows[self.tree.index(sel[0])]
        except Exception:
            return {}

    def update_rules(self, rules: List[Rule]) -> None:
        self._all_rules = list(rules or [])
        self._render()

    # Backward-compat: tab Blocker lama memanggil update_blockers().
    def update_blockers(self, rules: List[Rule]) -> None:
        self._all_rules = list(rules or [])
        prev = self.filter_mode
        self.filter_mode = "Blocker"
        self._render()
        self.filter_mode = prev
        try:
            self._paint_filter()
        except Exception:
            pass

    def _passes_filter(self, kind: str) -> bool:
        if self.filter_mode == "All":
            return True
        if self.filter_mode == "Limit":
            return kind == "limit"
        if self.filter_mode == "Blocker":
            return kind == "blocker"
        return True

    def _render(self) -> None:
        rules = self._all_rules
        self.tree.delete(*self.tree.get_children())
        self._rows = []
        n = 0
        for rule in sorted(rules, key=lambda r: r.app_name):
            state_text = "Active" if rule.enabled else "Disabled"
            base = ["alt"] if n % 2 == 1 else []
            if rule.enabled:
                base.append("active")
            tags = tuple(base)
            if rule.limit_in and self._passes_filter("limit"):
                self.tree.insert("", "end", values=("Limit", "In", rule.app_name, format_rate(rule.limit_in), state_text), tags=tags)
                self._rows.append({"kind": "limit", "type": "Limit", "dir": "In", "for": rule.app_name,
                                   "value": format_rate(rule.limit_in), "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.limit_out and self._passes_filter("limit"):
                self.tree.insert("", "end", values=("Limit", "Out", rule.app_name, format_rate(rule.limit_out), state_text), tags=tags)
                self._rows.append({"kind": "limit", "type": "Limit", "dir": "Out", "for": rule.app_name,
                                   "value": format_rate(rule.limit_out), "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.block_in and self._passes_filter("blocker"):
                self.tree.insert("", "end", values=("Blocker", "In", rule.app_name, "Blocked", state_text), tags=tags)
                self._rows.append({"kind": "blocker", "type": "Blocker", "dir": "In", "for": rule.app_name,
                                   "value": "Blocked", "state": state_text, "rule": rule})
                n += 1
                base = ["alt"] if n % 2 == 1 else []
                if rule.enabled:
                    base.append("active")
                tags = tuple(base)
            if rule.block_out and self._passes_filter("blocker"):
                self.tree.insert("", "end", values=("Blocker", "Out", rule.app_name, "Blocked", state_text), tags=tags)
                self._rows.append({"kind": "blocker", "type": "Blocker", "dir": "Out", "for": rule.app_name,
                                   "value": "Blocked", "state": state_text, "rule": rule})
                n += 1
            if not rule.limit_in and not rule.limit_out and not rule.block_in and not rule.block_out:
                if self._passes_filter("limit"):
                    self.tree.insert("", "end", values=("Limit", "In", rule.app_name, "Not set", state_text), tags=tags)
                    self._rows.append({"kind": "limit", "type": "Limit", "dir": "In", "for": rule.app_name,
                                       "value": "Not set", "state": state_text, "rule": rule})
                    n += 1

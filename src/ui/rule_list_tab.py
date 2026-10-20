"""Rules tab — one clean table for Limit and Blocker rules."""

from tkinter import ttk
from typing import Callable, List, Optional

import customtkinter as ctk

from src.core.models import Rule
from src.ui.theme import (ACCENT, BG_APP, BG_CARD, BG_CARD_ALT, BG_TABLE,
                          BORDER_COLOR, FONT_FAMILY, ROW_ALT_BG, SELECT_BLUE,
                          TEXT_DISABLED, TEXT_GREEN, TEXT_MAIN, TEXT_MUTED,
                          TEXT_RED, TEXT_SUBTLE, bind_mousewheel, fit_text,
                          style_table, tree_col_width)
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
        self._rows: list = []
        self._iids: list = []
        self._all_rules: List[Rule] = []
        self.filter_mode: str = "All"
        self.search_query: str = ""
        self._filter_btns: dict = {}
        self._last_sig = None
        self._empty_label = None
        self._build()

    def _build(self):
        from src.ui.theme import BTN_HOVER, RADIUS_LG, RADIUS_PILL
        # Filter + summary bar.
        fbar = ctk.CTkFrame(self, fg_color=BG_APP, height=46)
        fbar.pack(fill="x", padx=8, pady=(5, 5))
        fbar.pack_propagate(False)

        ctk.CTkLabel(fbar, text="SHOW", height=26, font=(FONT_FAMILY, 10, "bold"),
                     text_color=TEXT_SUBTLE).pack(side="left", padx=(2, 7))
        for mode in FILTERS:
            b = ctk.CTkButton(
                fbar, text=mode, width=72, height=32, font=(FONT_FAMILY, 11),
                fg_color=BG_CARD_ALT, hover_color=BTN_HOVER, text_color=TEXT_MUTED,
                border_width=1, border_color=BORDER_COLOR, corner_radius=RADIUS_PILL,
                command=lambda m=mode: self.set_filter(m))
            b.pack(side="left", padx=(0, 3))
            self._filter_btns[mode] = b
        self._paint_filter()

        self.lbl_summary = ctk.CTkLabel(fbar, text="", height=26,
                                        font=(FONT_FAMILY, 11), text_color=TEXT_SUBTLE)
        self.lbl_summary.pack(side="right", padx=(6, 4))

        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_LG,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        style_table("RL.Treeview", rowheight=31, font_size=12)
        cols = ("type", "dir", "for_", "value", "state")
        self.tree = ttk.Treeview(card, style="RL.Treeview", columns=cols,
                                 show="headings", selectmode="browse", takefocus=0)
        widths = {"type": 86, "dir": 84, "for_": 180, "value": 118, "state": 100}
        heads = {"type": "Type", "dir": "Direction", "for_": "For",
                 "value": "Value", "state": "State"}
        for c in cols:
            self.tree.heading(c, text=heads[c], anchor="w")
            self.tree.column(c, width=widths[c], anchor="w", stretch=(c == "for_"))
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(7, 0), pady=7)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=7)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("alt", background=ROW_ALT_BG)
        self.tree.tag_configure("blocker", foreground="#ffb3b3")
        self.tree.tag_configure("limit", foreground=TEXT_MAIN)
        self.tree.tag_configure("disabled", foreground=TEXT_DISABLED)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._resize_job = None
        self.tree.bind("<Configure>", self._on_tree_resize)
        self._empty_label = ctk.CTkLabel(
            card,
            text="No rules match this view.\nSelect an app in Activity to create one.",
            font=(FONT_FAMILY, 13), text_color=TEXT_SUBTLE,
            fg_color=BG_TABLE, justify="center")
        self._render()

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
        self._refit()

    def _on_tree_resize(self, event):
        """Re-fit the cell text when the columns are resized or stretched."""
        if event.widget is not self.tree:
            return
        try:
            if self._resize_job is not None:
                self.after_cancel(self._resize_job)
        except Exception:
            pass
        try:
            self._resize_job = self.after(150, self._refit)
        except Exception:
            self._resize_job = None

    def _refit(self) -> None:
        try:
            self._last_sig = None
            self._render()
        except Exception:
            pass

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
        for mode, btn in self._filter_btns.items():
            active = (mode == self.filter_mode)
            try:
                btn.configure(
                    fg_color=SELECT_BLUE if active else BG_CARD_ALT,
                    text_color="#ffffff" if active else TEXT_MUTED,
                    font=(FONT_FAMILY, 11, "bold" if active else "normal"),
                    border_color=ACCENT if active else BORDER_COLOR)
            except Exception:
                pass

    def set_filter(self, mode: str) -> None:
        if mode not in FILTERS:
            return
        self.filter_mode = mode
        self._paint_filter()
        self._last_sig = None
        self._render()

    def set_search(self, query: str) -> None:
        q = (query or "").strip().lower()
        if q == self.search_query:
            return
        self.search_query = q
        self._last_sig = None
        self._render()

    def reset_columns(self) -> None:
        try:
            for c, w in (("type", 86), ("dir", 84), ("for_", 180),
                         ("value", 118), ("state", 100)):
                self.tree.column(c, width=w)
        except Exception:
            pass

    def reset_view(self) -> None:
        self.filter_mode = "All"
        self.search_query = ""
        self._paint_filter()
        self.reset_columns()
        self._last_sig = None
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
        self._last_sig = None
        self._render()
        self.filter_mode = prev
        self._paint_filter()

    def _passes_filter(self, kind: str) -> bool:
        if self.filter_mode == "All":
            return True
        if self.filter_mode == "Limit":
            return kind == "limit"
        if self.filter_mode == "Blocker":
            return kind == "blocker"
        return True

    def _col_width(self, col: str, default: int) -> int:
        """Current pixel width of a column (it stretches with the window)."""
        return tree_col_width(self.tree, col, default)

    def _render(self) -> None:
        rules = self._all_rules
        # Avoid rebuilding the table every 500 ms (keeps selection + scroll).
        sig = (self.filter_mode, self.search_query,
               tuple((r.app_name, r.limit_in, r.limit_out, r.block_in,
                      r.block_out, r.enabled) for r in rules))
        if sig == self._last_sig:
            return
        self._last_sig = sig

        try:
            selected_key = None
            sel = self.tree.selection()
            if sel:
                row = self._rows[self.tree.index(sel[0])]
                selected_key = (row.get("kind"), row.get("dir"), row.get("for"))
            self.tree.delete(*self.tree.get_children())
        except Exception:
            selected_key = None

        self._rows = []
        self._iids = []
        limit_count = 0
        blocker_count = 0

        def add(kind, rtype, direction, rule, value, enabled):
            tags = []
            n = len(self._rows)
            if n % 2 == 1:
                tags.append("alt")
            if not enabled:
                tags.append("disabled")
            elif kind == "blocker":
                tags.append("blocker")
            else:
                tags.append("limit")
            app_label = fit_text(rule.app_name,
                                 self._col_width("for_", 180), reserve=12)
            iid = self.tree.insert(
                "", "end",
                values=(rtype, direction, app_label, value,
                        "● Active" if enabled else "○ Disabled"),
                tags=tuple(tags))
            self._iids.append(iid)
            self._rows.append({"kind": kind, "type": rtype, "dir": direction,
                               "for": rule.app_name, "value": value,
                               "state": "Active" if enabled else "Disabled",
                               "rule": rule})
            if selected_key and selected_key == (kind, direction, rule.app_name):
                try:
                    self.tree.selection_set(iid)
                except Exception:
                    pass

        for rule in sorted(rules, key=lambda r: r.app_name):
            app_l = rule.app_name.lower()
            if self.search_query and self.search_query not in app_l:
                continue
            if rule.limit_in and self._passes_filter("limit"):
                add("limit", "Limit", "In", rule, format_rate(rule.limit_in), rule.enabled)
                limit_count += 1
            if rule.limit_out and self._passes_filter("limit"):
                add("limit", "Limit", "Out", rule, format_rate(rule.limit_out), rule.enabled)
                limit_count += 1
            if rule.block_in and self._passes_filter("blocker"):
                add("blocker", "Blocker", "In", rule, "Blocked", rule.enabled)
                blocker_count += 1
            if rule.block_out and self._passes_filter("blocker"):
                add("blocker", "Blocker", "Out", rule, "Blocked", rule.enabled)
                blocker_count += 1
            if not rule.limit_in and not rule.limit_out and not rule.block_in and not rule.block_out:
                if self._passes_filter("limit"):
                    add("limit", "Limit", "In", rule, "Not set", rule.enabled)
                    limit_count += 1

        try:
            self.lbl_summary.configure(
                text=f"{len(rules)} rules · {limit_count} limit · {blocker_count} blocker")
        except Exception:
            pass
        try:
            if self._rows:
                self._empty_label.place_forget()
            else:
                self._empty_label.place(relx=0.5, rely=0.45, anchor="center")
                self._empty_label.lift()
        except Exception:
            pass

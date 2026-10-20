"""Application List tab — every running process, searchable and smooth."""

from tkinter import ttk
from typing import Callable, List, Optional

import customtkinter as ctk

from src.core.models import ProcessInfo
from src.ui.activity_tab import friendly_name
from src.ui.theme import (BG_APP, BG_TABLE, BORDER_COLOR, FONT_FAMILY,
                          ROW_ALT_BG, TEXT_GREEN, TEXT_MAIN, TEXT_MUTED,
                          TEXT_SUBTLE, bind_mousewheel, fit_text, style_table,
                          tree_col_width)


class ApplicationListTab(ctk.CTkFrame):
    def __init__(self, master, on_app_selected: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_app_selected = on_app_selected
        self.search_query = ""
        self._apps: List[ProcessInfo] = []
        self._tile_refs: dict = {}
        self._sort_col = "name"
        self._sort_desc = False
        self._empty_label = None
        self._build()

    def _build(self):
        from src.ui.theme import RADIUS_LG
        bar = ctk.CTkFrame(self, fg_color=BG_APP, height=46)
        bar.pack(fill="x", padx=8, pady=(5, 5))
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="APPLICATIONS", height=26, font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_SUBTLE).pack(side="left", padx=(2, 0))
        self.lbl_count = ctk.CTkLabel(bar, text="", height=26, font=(FONT_FAMILY, 11),
                                      text_color=TEXT_SUBTLE)
        self.lbl_count.pack(side="right", padx=(6, 4))

        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_LG,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        style_table("App.Treeview", rowheight=31, font_size=12)
        cols = ("process", "status", "path")
        self.tree = ttk.Treeview(card, style="App.Treeview", columns=cols,
                                 show="tree headings", selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="Application", anchor="w",
                          command=lambda: self._on_sort("name"))
        self.tree.heading("process", text="Process", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.heading("path", text="Executable path", anchor="w",
                          command=lambda: self._on_sort("path"))
        self.tree.column("#0", width=210, stretch=True)
        self.tree.column("process", width=140, stretch=True)
        self.tree.column("status", width=84, stretch=False)
        self.tree.column("path", width=150, stretch=True)
        self.tree.pack(side="left", fill="both", expand=True, padx=(7, 0), pady=7)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=7)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("alt", background=ROW_ALT_BG)
        self.tree.tag_configure("online", foreground=TEXT_MAIN)
        self.tree.tag_configure("offline", foreground=TEXT_MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._empty_label = ctk.CTkLabel(
            card, text="No applications match your search.",
            font=(FONT_FAMILY, 13), text_color=TEXT_SUBTLE, fg_color=BG_TABLE)
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
        try:
            self._render()
        except Exception:
            pass

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
            self._resize_job = self.after(150, self._render)
        except Exception:
            self._resize_job = None

    def _on_sort(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self._render()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.on_app_selected:
            return
        try:
            iid = sel[0]
            if iid.startswith("app:"):
                self.on_app_selected(iid[4:])
        except Exception:
            pass

    def reset_columns(self) -> None:
        try:
            self.tree.column("#0", width=210)
            self.tree.column("process", width=140)
            self.tree.column("status", width=84)
            self.tree.column("path", width=150)
        except Exception:
            pass

    def set_search(self, query: str) -> None:
        q = (query or "").strip().lower()
        if q == self.search_query:
            return
        self.search_query = q
        self._render()

    def update_apps(self, apps):
        self._apps = list(apps or [])
        self._render()

    def _col_width(self, col: str, default: int) -> int:
        """Current pixel width of a column (it stretches with the window)."""
        return tree_col_width(self.tree, col, default)

    def _render(self) -> None:
        q = self.search_query
        apps = [a for a in self._apps
                if not q or q in a.name.lower() or q in (a.exe_path or "").lower()]
        if self._sort_col == "path":
            apps.sort(key=lambda a: (a.exe_path or "").lower(), reverse=self._sort_desc)
        else:
            apps.sort(key=lambda a: friendly_name(a.name).lower(), reverse=self._sort_desc)

        sel_name = ""
        try:
            sel = self.tree.selection()
            if sel:
                iid = sel[0]
                if iid.startswith("app:"):
                    sel_name = iid[4:]
        except Exception:
            pass

        try:
            from src.utils.icons import get_app_tile
        except Exception:
            get_app_tile = None  # type: ignore

        wanted = set()
        online = 0
        for i, a in enumerate(apps):
            iid = "app:" + a.name
            wanted.add(iid)
            if a.is_online:
                online += 1
            tile = None
            if get_app_tile is not None:
                try:
                    tile = get_app_tile(a.name, master=self.tree, pad_right=6)
                except Exception:
                    tile = None
            if tile is not None:
                self._tile_refs[iid] = tile
            img = tile if tile is not None else ""
            status = "● Online" if a.is_online else "○ Offline"
            tags = []
            if i % 2 == 1:
                tags.append("alt")
            tags.append("online" if a.is_online else "offline")
            values = (fit_text(a.name, self._col_width("process", 140), reserve=12),
                      status,
                      fit_text(a.exe_path, self._col_width("path", 150), reserve=12)
                      if a.exe_path else "—")
            display = fit_text(friendly_name(a.name),
                               self._col_width("#0", 210), reserve=30)
            if not self.tree.exists(iid):
                self.tree.insert("", "end", iid=iid, text=display,
                                 image=img, values=values, tags=tuple(tags))
            else:
                self.tree.item(iid, text=display, image=img,
                               values=values, tags=tuple(tags))
            try:
                if self.tree.index(iid) != i:
                    self.tree.move(iid, "", i)
            except Exception:
                pass
            if a.name == sel_name:
                try:
                    self.tree.selection_set(iid)
                except Exception:
                    pass

        for child in list(self.tree.get_children()):
            if child not in wanted:
                try:
                    self.tree.delete(child)
                except Exception:
                    pass
                self._tile_refs.pop(child, None)

        try:
            self.lbl_count.configure(text=f"{len(apps)} apps · {online} online")
        except Exception:
            pass
        try:
            if apps:
                self._empty_label.place_forget()
            else:
                self._empty_label.place(relx=0.5, rely=0.45, anchor="center")
                self._empty_label.lift()
        except Exception:
            pass

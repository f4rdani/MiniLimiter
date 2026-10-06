"""Application List tab: semua aplikasi terdaftar (klik -> Info View)."""

from tkinter import ttk
from typing import Callable, Optional
import customtkinter as ctk

from src.ui.theme import BG_TABLE, BG_ROW_SELECTED, FONT_FAMILY, TEXT_MAIN, TEXT_MUTED, bind_mousewheel


class ApplicationListTab(ctk.CTkFrame):
    def __init__(self, master, on_app_selected: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, fg_color=BG_TABLE, **kwargs)
        self.on_app_selected = on_app_selected
        self._tile_refs: dict = {}
        from src.ui.theme import RADIUS_MD, BORDER_COLOR, style_table
        card = ctk.CTkFrame(self, fg_color=BG_TABLE, corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        style_table("App.Treeview", rowheight=26, font_size=11)
        cols = ("name", "path")
        self.tree = ttk.Treeview(card, style="App.Treeview", columns=cols, show="tree headings",
                                 selectmode="browse", takefocus=0)
        self.tree.heading("#0", text="", anchor="w")
        self.tree.heading("name", text="Name", anchor="w")
        self.tree.heading("path", text="Path", anchor="w")
        self.tree.column("#0", width=24)
        self.tree.column("name", width=220, stretch=False)
        self.tree.column("path", width=420, stretch=True)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 4), pady=6)
        bind_mousewheel(self.tree)
        self.tree.tag_configure("alt", background="#232323")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or not self.on_app_selected:
            return
        try:
            vals = self.tree.item(sel[0])["values"]
            if vals:
                self.on_app_selected(str(vals[0]))
        except Exception:
            pass

    def reset_columns(self) -> None:
        try:
            self.tree.column("name", width=220)
            self.tree.column("path", width=420)
        except Exception:
            pass

    def update_apps(self, apps):
        sel_name = ""
        try:
            sel = self.tree.selection()
            if sel:
                sel_name = str(self.tree.item(sel[0])["values"][0])
        except Exception:
            pass
        try:
            from src.utils.icons import get_app_tile
        except Exception:
            get_app_tile = None  # type: ignore
        self.tree.delete(*self.tree.get_children())
        self._tile_refs.clear()
        for i, a in enumerate(sorted(apps, key=lambda x: x.name)[:500]):
            iid = "app:" + a.name
            tile = None
            if get_app_tile is not None:
                try:
                    tile = get_app_tile(a.name, master=self.tree)
                except Exception:
                    tile = None
            img = tile if tile is not None else ""
            if tile is not None:
                self._tile_refs[iid] = tile
            self.tree.insert("", "end", iid=iid, text="", image=img, values=(a.name, a.exe_path or ""),
                             tags=("alt",) if i % 2 == 1 else ())
            if a.name == sel_name:
                try:
                    self.tree.selection_set(iid)
                except Exception:
                    pass

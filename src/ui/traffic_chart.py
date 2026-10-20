"""Traffic chart — live download/upload curves with a limit ceiling.

The chart keeps NetLimiter's dual-axis idea (green download on the left, red
upload on the right) but uses a cleaner grid, rounded card and a hover readout.
"""

import tkinter as tk
from typing import List, Optional, Tuple

import customtkinter as ctk

from src.ui.theme import (BG_CARD, BG_CARD_ALT, BG_PANEL, BORDER_COLOR,
                          COLOR_DOWNLOAD, COLOR_LIMIT_BADGE, COLOR_UPLOAD,
                          FONT_FAMILY, RADIUS_MD, TEXT_DISABLED, TEXT_MUTED,
                          TEXT_SUBTLE)
from src.utils.formatters import format_bytes, format_rate

WINDOW_SECONDS = 600.0


class TrafficChart(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=0, **kwargs)
        self.current_app_name = "—"
        self.active_limit_bytes: Optional[int] = None
        self.total_dl_bytes = 0
        self.total_ul_bytes = 0
        self.unit_mode: str = "autoByte"
        self._history: List[Tuple[float, float, float]] = []
        self._hover_x: Optional[int] = None
        self._last_dl_rate = 0.0
        self._last_ul_rate = 0.0
        self._build()

    def _build(self):
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        top = ctk.CTkFrame(card, fg_color="transparent", height=28)
        top.pack(fill="x", padx=11, pady=(8, 0))
        top.pack_propagate(False)
        ctk.CTkFrame(top, width=8, height=8, corner_radius=4,
                     fg_color=COLOR_DOWNLOAD).pack(side="left", pady=(7, 0))
        ctk.CTkLabel(top, text="Traffic chart", height=24,
                     font=(FONT_FAMILY, 12, "bold"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(8, 0), pady=(1, 0))
        self.lbl_target = ctk.CTkLabel(top, text="Total traffic", height=24,
                                       font=(FONT_FAMILY, 10, "bold"),
                                       text_color=TEXT_MUTED,
                                       fg_color=BG_CARD_ALT, corner_radius=8)
        self.lbl_target.pack(side="right", padx=(0, 1), pady=(1, 0))

        leg = ctk.CTkFrame(card, fg_color="transparent", height=24)
        leg.pack(fill="x", padx=11, pady=(3, 0))
        leg.pack_propagate(False)
        self.lbl_dl = ctk.CTkLabel(leg, text="↓ 0 B/s  ·  0 B", height=22,
                                   font=(FONT_FAMILY, 11, "bold"),
                                   text_color=COLOR_DOWNLOAD)
        self.lbl_dl.pack(side="left")
        self.lbl_ul = ctk.CTkLabel(leg, text="↑ 0 B/s  ·  0 B", height=22,
                                   font=(FONT_FAMILY, 11, "bold"),
                                   text_color=COLOR_UPLOAD)
        self.lbl_ul.pack(side="right")
        # Kept for compatibility with older callers.
        self.lbl_mid = ctk.CTkLabel(leg, text="", height=22,
                                    font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE)
        self.lbl_mid.pack(side="left", expand=True, padx=6)

        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=5, pady=(2, 5))
        self.canvas = tk.Canvas(wrap, bg=BG_CARD, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

    # ------------------------------------------------------------------ data
    def set_target(self, app_name, limit_in, total_dl, total_ul):
        self.current_app_name = app_name or "—"
        self.active_limit_bytes = limit_in
        self.total_dl_bytes = total_dl
        self.total_ul_bytes = total_ul
        name = self.current_app_name
        if len(name) > 26:
            name = name[:25] + "…"
        self.lbl_target.configure(text=name or "Total traffic")
        self.lbl_dl.configure(
            text=f"↓ {format_rate(self._last_dl_rate, self.unit_mode)}  ·  {format_bytes(total_dl)}")
        self.lbl_ul.configure(
            text=f"↑ {format_rate(self._last_ul_rate, self.unit_mode)}  ·  {format_bytes(total_ul)}")

    def update_data(self, history, unit_mode="autoByte"):
        self._history = history or []
        self.unit_mode = unit_mode
        try:
            if self._history:
                _t, dl, ul = self._history[-1]
                self._last_dl_rate, self._last_ul_rate = dl, ul
                self.lbl_dl.configure(
                    text=f"↓ {format_rate(dl, unit_mode)}  ·  {format_bytes(self.total_dl_bytes)}")
                self.lbl_ul.configure(
                    text=f"↑ {format_rate(ul, unit_mode)}  ·  {format_bytes(self.total_ul_bytes)}")
        except Exception:
            pass
        self.redraw()

    # ------------------------------------------------------------------ hover
    def _on_motion(self, event):
        self._hover_x = event.x
        self.redraw()

    def _on_leave(self, _event=None):
        self._hover_x = None
        self.redraw()

    # ---------------------------------------------------------------- drawing
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 60 or h < 60:
            return
        ml, mr, mt, mb = 66, 74, 12, 26
        pw, ph = w - ml - mr, h - mt - mb
        if pw <= 10 or ph <= 5:
            return

        now = self._history[-1][0] if self._history else 0.0
        pts = [(t, dl, ul) for (t, dl, ul) in self._history
               if (now - t) <= WINDOW_SECONDS]
        span = (now - pts[0][0]) if pts else 0.0
        win = max(15.0, min(WINDOW_SECONDS, span if span > 0 else 15.0))

        max_dl = 512 * 1024.0
        max_ul = 64 * 1024.0
        for _, dl, ul in pts:
            dl = min(dl, 1.25e9)
            ul = min(ul, 1.25e9)
            max_dl = max(max_dl, dl * 1.15)
            max_ul = max(max_ul, ul * 1.25)
        if self.active_limit_bytes:
            max_dl = max(max_dl, self.active_limit_bytes * 1.2)
        max_dl = self._nice_max(min(max_dl, 1.25e9))
        max_ul = self._nice_max(min(max_ul, 1.25e9))

        def y_dl(v):
            return mt + ph - (min(v, max_dl) / max_dl * ph)

        def y_ul(v):
            return mt + ph - (min(v, max_ul) / max_ul * ph)

        def x_at(t):
            age = now - t
            frac = 1.0 - age / win
            return ml + pw * max(0.0, min(1.0, frac))

        # Subtle grid.
        for i in range(7):
            x = ml + pw * i / 6.0
            c.create_line(x, mt, x, mt + ph, fill="#2a323d", width=1)
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = mt + ph * f
            c.create_line(ml, y, ml + pw, y, fill="#2a323d", width=1)
        # Zero baseline a touch brighter.
        c.create_line(ml, mt + ph, ml + pw, mt + ph, fill="#3a4553", width=1)

        # Y axis: download on the left, upload on the right.
        for f, frac in ((0.0, 1.0), (0.5, 0.5), (1.0, 0.0)):
            y = mt + ph * f
            txt = self._fmt_axis(max_dl * frac) if frac else "0"
            c.create_text(ml - 6, y, text=txt, fill=COLOR_DOWNLOAD,
                          anchor="e", font=(FONT_FAMILY, 10))
        for f, frac in ((0.0, 1.0), (0.5, 0.5), (1.0, 0.0)):
            y = mt + ph * f
            txt = self._fmt_axis(max_ul * frac) if frac else "0"
            c.create_text(ml + pw + 6, y, text=txt, fill=COLOR_UPLOAD,
                          anchor="w", font=(FONT_FAMILY, 10))

        # X labels (elapsed window).
        for i in range(7):
            x = ml + pw * i / 6.0
            c.create_text(x, mt + ph + 12, text=self._fmt_dur(win * i / 6.0),
                          fill=TEXT_SUBTLE, anchor="center", font=(FONT_FAMILY, 10))

        if len(pts) >= 2:
            dl_line, ul_line = [], []
            for (t, dl, ul) in pts:
                x = x_at(t)
                dl_line += [x, y_dl(min(dl, max_dl))]
                ul_line += [x, y_ul(min(ul, max_ul))]
            base = mt + ph
            c.create_polygon([dl_line[0], base] + dl_line + [dl_line[-2], base],
                             fill="#20351f", outline="", stipple="gray25")
            c.create_polygon([ul_line[0], base] + ul_line + [ul_line[-2], base],
                             fill="#3a2020", outline="", stipple="gray25")
            c.create_line(dl_line, fill=COLOR_DOWNLOAD, width=2, smooth=False)
            c.create_line(ul_line, fill=COLOR_UPLOAD, width=2, smooth=False)
            # Live dot on the newest sample.
            c.create_oval(dl_line[-2] - 2, dl_line[-1] - 2,
                          dl_line[-2] + 2, dl_line[-1] + 2,
                          fill=COLOR_DOWNLOAD, outline="")
            c.create_oval(ul_line[-2] - 2, ul_line[-1] - 2,
                          ul_line[-2] + 2, ul_line[-1] + 2,
                          fill=COLOR_UPLOAD, outline="")
        else:
            c.create_text(ml + pw / 2, mt + ph / 2,
                          text="Waiting for traffic…",
                          fill=TEXT_DISABLED, font=(FONT_FAMILY, 11))

        # Limit ceiling.
        if self.active_limit_bytes and self.active_limit_bytes < max_dl:
            ly = y_dl(self.active_limit_bytes)
            c.create_line(ml, ly, ml + pw, ly, fill=COLOR_LIMIT_BADGE,
                          dash=(4, 3), width=1)
            c.create_text(ml + pw - 4, ly - 3,
                          text=f"limit {format_rate(self.active_limit_bytes, self.unit_mode)}",
                          fill=COLOR_LIMIT_BADGE, anchor="e",
                          font=(FONT_FAMILY, 10, "bold"))

        # Hover readout.
        if self._hover_x is not None and pts and ml <= self._hover_x <= ml + pw:
            hx = self._hover_x
            c.create_line(hx, mt, hx, mt + ph, fill="#3b4553", width=1)
            target_t = now - (1.0 - (hx - ml) / pw) * win
            nearest = min(pts, key=lambda p: abs(p[0] - target_t))
            txt = (f"↓ {format_rate(nearest[1], self.unit_mode)}   "
                   f"↑ {format_rate(nearest[2], self.unit_mode)}")
            tid = c.create_text(ml + 8, mt + 3, text=txt, fill=TEXT_MUTED,
                                anchor="nw", font=(FONT_FAMILY, 10))
            box = c.bbox(tid)
            if box:
                rect = c.create_rectangle(box[0] - 4, box[1] - 2,
                                          box[2] + 4, box[3] + 2,
                                          fill=BG_CARD, outline=BORDER_COLOR)
                c.tag_lower(rect, tid)

    def _fmt_axis(self, value: float) -> str:
        mode = self.unit_mode or "autoByte"
        scale = 1000.0 if mode in ("autoBit", "Mb/s") else 1024.0
        dec = 0 if value >= 10 * scale else 1
        return format_rate(value, mode, decimal_places=dec)

    @staticmethod
    def _nice_max(value: float) -> float:
        """Round a maximum up to a friendly 1/2/5 × 10ⁿ value."""
        if value <= 0:
            return 1.0
        import math
        exp = math.floor(math.log10(value))
        base = 10 ** exp
        for mult in (1, 2, 5, 10):
            if value <= mult * base:
                return float(mult * base)
        return float(10 * base)

    @staticmethod
    def _fmt_dur(sec: float) -> str:
        sec = int(round(sec))
        if sec < 60:
            return f"{sec}s" if sec != 0 else "0"
        m, s = divmod(sec, 60)
        if s == 0:
            return f"{m}m"
        return f"{m}m {s:02d}s"

"""Traffic chart 1:1 NetLimiter (bottom-right of every screenshot).

- Header: 'Traffic chart' + dropdown + X
- Legend: green 'Download (1,16 GB)' left, center name, red 'Upload (210,26 KB)' right
- Dual axis: left green MB, right red KB, X 0..10m (0,1m 40s,3m 20s,5m,6m 40s,8m 20s,10m)
- Window: last 10 minutes of history (older points compressed)
- Blue round buttons on right edge (decorative, like NetLimiter)
"""

import tkinter as tk
from typing import List, Optional, Tuple
import customtkinter as ctk

from src.ui.theme import BG_PANEL, BG_TABLE, FONT_FAMILY, TEXT_MUTED, COLOR_DOWNLOAD, COLOR_UPLOAD, COLOR_LIMIT_BADGE
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
        self._build()

    def _build(self):
        from src.ui.theme import RADIUS_MD, BORDER_COLOR
        card = ctk.CTkFrame(self, fg_color="#202020", corner_radius=RADIUS_MD,
                            border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        top = ctk.CTkFrame(card, fg_color="transparent", height=26)
        top.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(top, text="●", font=(FONT_FAMILY, 10), text_color=COLOR_DOWNLOAD, width=16).pack(side="left")
        ctk.CTkLabel(top, text="Traffic chart", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_MUTED).pack(side="left")

        leg = ctk.CTkFrame(card, fg_color="transparent", height=18)
        leg.pack(fill="x", padx=10, pady=(2, 0))
        self.lbl_dl = ctk.CTkLabel(leg, text="Download (0 B)", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_DOWNLOAD)
        self.lbl_dl.pack(side="left")
        self.lbl_mid = ctk.CTkLabel(leg, text="", font=(FONT_FAMILY, 10), text_color=TEXT_MUTED)
        self.lbl_mid.pack(side="left", expand=True, padx=6)
        self.lbl_ul = ctk.CTkLabel(leg, text="Upload (0 B)", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_UPLOAD)
        self.lbl_ul.pack(side="right")

        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        self.canvas = tk.Canvas(wrap, bg="#202020", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())

    def set_target(self, app_name, limit_in, total_dl, total_ul):
        self.current_app_name = app_name or "—"
        self.active_limit_bytes = limit_in
        self.total_dl_bytes = total_dl
        self.total_ul_bytes = total_ul
        self.lbl_dl.configure(text=f"Download ({format_bytes(total_dl)})")
        self.lbl_ul.configure(text=f"Upload ({format_bytes(total_ul)})")
        self.lbl_mid.configure(text=self.current_app_name)

    def update_data(self, history, unit_mode="autoByte"):
        self._history = history or []
        self.unit_mode = unit_mode
        self.redraw()

    # ---------- drawing ----------
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 60 or h < 60:
            return
        ml, mr, mt, mb = 44, 40, 8, 20
        pw, ph = w - ml - mr, h - mt - mb
        if pw <= 10 or ph <= 5:
            return

        now = self._history[-1][0] if self._history else 0.0
        pts = [(t, dl, ul) for (t, dl, ul) in self._history if (now - t) <= WINDOW_SECONDS]
        # Window X DINAMIS: ikuti rentang data (min 15 dtk) sampai maks 10 mnt.
        # Window tetap 10 mnt membuat data awal menumpuk sekelip di kanan.
        span = (now - pts[0][0]) if pts else 0.0
        win = max(15.0, min(WINDOW_SECONDS, span if span > 0 else 15.0))
        # sumbu independen
        max_dl = 10 * 1024 * 1024.0
        max_ul = 10 * 1024.0
        for _, dl, ul in pts:
            dl = min(dl, 1.25e9)
            ul = min(ul, 1.25e9)
            if dl > max_dl:
                max_dl = dl * 1.15
            if ul > max_ul:
                max_ul = ul * 1.3
        if self.active_limit_bytes:
            max_dl = max(max_dl, self.active_limit_bytes * 1.25)
        max_dl = min(max_dl, 1.25e9)
        max_ul = min(max_ul, 1.25e9)

        def y_dl(v):
            return mt + ph - (min(v, max_dl) / max_dl * ph)

        def y_ul(v):
            return mt + ph - (min(v, max_ul) / max_ul * ph)

        def x_at(t):
            age = now - t
            frac = 1.0 - age / win
            return ml + pw * max(0.0, min(1.0, frac))

        # grid vertikal 6 kolom + label waktu adaptif (0 ... win)
        for i in range(7):
            x = ml + pw * i / 6.0
            c.create_line(x, mt, x, mt + ph, fill="#2a2a2a", width=1)
        # grid horizontal
        for f in (0.0, 0.5, 1.0):
            y = mt + ph * f
            c.create_line(ml, y, ml + pw, y, fill="#2a2a2a", width=1)
        # label Y kiri hijau (skala DL) — ikut Units yang dipilih
        for f, frac in ((0.0, 1.0), (0.5, 0.5), (1.0, 0.0)):
            y = mt + ph * f
            txt = format_rate(max_dl * frac, unit_mode=self._axis_unit(), decimal_places=1) if frac else "0"
            c.create_text(ml - 3, y, text=txt, fill=COLOR_DOWNLOAD, anchor="e", font=(FONT_FAMILY, 10))
        # label Y kanan merah (skala UL) — ikut Units yang dipilih
        for f, frac in ((0.0, 1.0), (0.5, 0.5), (1.0, 0.0)):
            y = mt + ph * f
            txt = format_rate(max_ul * frac, unit_mode=self._axis_unit(), decimal_places=1) if frac else "0"
            c.create_text(ml + pw + 3, y, text=txt, fill=COLOR_UPLOAD, anchor="w", font=(FONT_FAMILY, 10))
        # label X: elapsed 0 ... win (win=600 -> persis ref: 0,1m 40s,...,10m)
        for i in range(7):
            x = ml + pw * i / 6.0
            c.create_text(x, mt + ph + 11, text=self._fmt_dur(win * i / 6.0),
                          fill=TEXT_MUTED, anchor="center", font=(FONT_FAMILY, 10))

        if len(pts) >= 2:
            dl_line, ul_line = [], []
            for (t, dl, ul) in pts:
                x = x_at(t)
                dl_line += [x, y_dl(min(dl, max_dl))]
                ul_line += [x, y_ul(min(ul, max_ul))]
            base = mt + ph
            c.create_polygon([dl_line[0], base] + dl_line + [dl_line[-2], base], fill="#2a4d1e", outline="", stipple="gray25")
            c.create_polygon([ul_line[0], base] + ul_line + [ul_line[-2], base], fill="#4d1a1a", outline="", stipple="gray25")
            c.create_line(dl_line, fill=COLOR_DOWNLOAD, width=1)
            c.create_line(ul_line, fill=COLOR_UPLOAD, width=1)
            if self.active_limit_bytes and self.active_limit_bytes < max_dl:
                ly = y_dl(self.active_limit_bytes)
                c.create_line(ml, ly, ml + pw, ly, fill=COLOR_LIMIT_BADGE, dash=(4, 3), width=1)
        else:
            # baseline hijau tipis seperti ref saat idle
            c.create_line(ml, mt + ph - 1, ml + pw, mt + ph - 1, fill="#2a4d1e", width=1)

    def _axis_unit(self) -> str:
        """Unit sumbu mengikuti Units terpilih (autoByte/MB/s/Mb/s/...)."""
        return getattr(self, "unit_mode", "autoByte") or "autoByte"

    @staticmethod
    def _fmt_dur(sec: float) -> str:
        sec = int(round(sec))
        if sec < 60:
            return f"{sec}s" if sec != 0 else "0"
        m, s = divmod(sec, 60)
        if s == 0:
            return f"{m}m"
        return f"{m}m {s:02d}s"

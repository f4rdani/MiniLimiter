"""MiniLimiter Dark Theme (NetLimiter-inspired, modern polish).

Token terpusat agar search / tabel / tombol / dropdown konsisten.
Nama lama dipertahankan demi backward-compat dengan modul UI lain.
"""

# Layout
BG_APP = "#1e1e1e"            # main window background
BG_DARK = "#1e1e1e"
BG_PANEL = "#252526"          # toolbar / panel
BG_TABLE = "#1e1e1e"          # tree background
BG_HEADER = "#2d2d2d"         # column header (legacy, lihat HEADER_BG baru)
BG_SECONDARY = "#1e1e1e"
BG_ROW_HOVER = "#2a2d2e"
BG_ROW_SELECTED = "#007acc"   # selected row blue (NetLimiter)
SELECT_BLUE = "#007acc"

# Tabs (NetLimiter active tab = yellow)
TAB_ACTIVE_BG = "#c9b400"
TAB_ACTIVE_TEXT = "#000000"
TAB_BG = "#2d2d2d"
TAB_TEXT = "#d0d0d0"

# Accents
ACCENT_LIME = "#7cbb00"       # NetLimiter lime dots / DL
DOT_GREEN = "#7cbb00"
DOT_GRAY = "#b5b5b5"
COLOR_DOWNLOAD = "#7cbb00"    # chart + DL green
COLOR_UPLOAD = "#e51400"      # chart + UL red
COLOR_LIMIT_BADGE = "#3498db"
LIMIT_BLUE = "#1f6fb2"        # limit value badge

# Text (diterangkan agar mudah dibaca — tanpa teks redup)
TEXT_MAIN = "#ffffff"
TEXT_MUTED = "#d6d6d6"
TEXT_DISABLED = "#9a9a9a"
TEXT_LINK = "#6db8f2"         # blue links (Traffic stats, Add rule...)
TEXT_GREEN = "#8fd400"        # Active state
TEXT_YELLOW = "#e5c500"

BORDER_COLOR = "#3c3c3c"
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11

# --- polish tokens (baru, dipakai tombol/search/dropdown/card) ---
SURFACE_1 = "#252526"   # panel
SURFACE_2 = "#2b2b2b"   # card / header
SURFACE_3 = "#333333"   # idle button / pill
HEADER_BG = "#262626"
HEADER_FG = "#e8e8e8"
ROW_ALT_BG = "#232323"
ROW_SEL_BG = "#0e639c"
ROW_SEL_FG = "#ffffff"
GRID_COLOR = "#2a2a2a"
BTN_BG = "#2f2f2f"
BTN_HOVER = "#3d3d3d"
BTN_ACTIVE_BG = "#c9b400"
BTN_ACTIVE_FG = "#000000"
PRIMARY_BG = "#007acc"
PRIMARY_HOVER = "#1a86d0"
DANGER_BG = "#a83a3a"
INPUT_BG = "#1b1b1b"
INPUT_BORDER = "#3d3d3d"
INPUT_FOCUS = "#007acc"
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_PILL = 16

# Scrollbar gelap (ganti default terang ttk yang jadi "kotak putih")
SCROLL_BG = "#2d2d2d"       # track
SCROLL_SLIDER = "#4d4d4d"   # thumb
SCROLL_ACTIVE = "#6b6b6b"   # thumb hover
SCROLL_ARROW = "#b5b5b5"


def apply_dark_ttk():
    """Terapkan sekali saat startup: theme clam + scrollbar default gelap.

    Tanpa ini, ttk.Scrollbar polos tampil putih terang (kotak putih jelek).
    """
    from tkinter import ttk
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    for orient in ("Vertical", "Horizontal"):
        sname = orient + ".TScrollbar"
        style.configure(
            sname,
            background=SCROLL_SLIDER,
            troughcolor=SCROLL_BG,
            bordercolor=BG_APP,
            arrowcolor=SCROLL_ARROW,
            relief="flat",
            borderwidth=0,
            arrowsize=12,
        )
        style.map(sname, background=[("active", SCROLL_ACTIVE), ("pressed", SCROLL_ACTIVE)])
    # Divider drag antar panel (gelap, bukan putih)
    try:
        style.configure("Dark.TPanedwindow", background="#2d2d2d", borderwidth=0,
                        sashwidth=6, sashrelief="flat")
        style.configure("Dark.Vertical.TPanedwindow", background="#2d2d2d", borderwidth=0,
                        sashwidth=6, sashrelief="flat")
        style.configure("Dark.Horizontal.TPanedwindow", background="#2d2d2d", borderwidth=0,
                        sashwidth=6, sashrelief="flat")
    except Exception:
        pass
    # Combobox dropdown gelap (default clam terang).
    try:
        style.configure("Dark.TCombobox", fieldbackground=INPUT_BG, background=SURFACE_3,
                        foreground=TEXT_MAIN, arrowcolor=TEXT_MUTED, borderwidth=1,
                        relief="flat", padding=4)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", INPUT_BG), ("focus", INPUT_BG)],
                  foreground=[("disabled", TEXT_DISABLED)],
                  bordercolor=[("focus", INPUT_FOCUS)])
    except Exception:
        pass


def style_table(style_name: str, rowheight: int = 26, font_size: int = 11) -> None:
    """Style Treeview terpadu: header flat gelap + baris belang + seleksi biru.

    Dipakai semua tab tabel agar search/tabel terlihat satu bahasa desain.
    Aman dipanggil berulang (configure ulang style yang sama).
    """
    from tkinter import ttk
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    try:
        style.configure(style_name, background=BG_TABLE, foreground=TEXT_MAIN,
                        fieldbackground=BG_TABLE, rowheight=rowheight,
                        font=(FONT_FAMILY, font_size), borderwidth=0, relief="flat",
                        focuscolor=BG_TABLE, lightcolor=BG_TABLE, darkcolor=BG_TABLE)
        style.configure(f"{style_name}.Heading", background=HEADER_BG, foreground=HEADER_FG,
                        font=(FONT_FAMILY, font_size, "bold"), relief="flat",
                        borderwidth=0, padding=(8, 6))
        style.map(style_name,
                  background=[("selected", ROW_SEL_BG)],
                  foreground=[("selected", ROW_SEL_FG)])
        style.map(f"{style_name}.Heading",
                  background=[("active", "#333333")],
                  foreground=[("active", "#ffffff")])
    except Exception:
        pass


def decorate_tree(tree, alt_bg: str = ROW_ALT_BG) -> None:
    """Tag belang + seleksi standar untuk sebuah Treeview."""
    try:
        tree.tag_configure("alt", background=alt_bg)
        tree.tag_configure("active", foreground=TEXT_GREEN)
        tree.tag_configure("selblue", background=ROW_SEL_BG)
    except Exception:
        pass


def bind_mousewheel(tree):
    """Scroll roda mouse untuk ttk.Treeview (Windows/macOS/Linux)."""
    def _on_wheel(e):
        try:
            delta = 0
            if getattr(e, "delta", 0):
                delta = -1 * (e.delta // 120)
            elif getattr(e, "num", None) in (4, 5):
                delta = -1 if e.num == 4 else 1
            if delta:
                tree.yview_scroll(delta, "units")
        except Exception:
            pass
        return "break"
    try:
        tree.bind("<MouseWheel>", _on_wheel)
        tree.bind("<Button-4>", lambda e: tree.yview_scroll(-1, "units"))
        tree.bind("<Button-5>", lambda e: tree.yview_scroll(1, "units"))
    except Exception:
        pass
    return tree

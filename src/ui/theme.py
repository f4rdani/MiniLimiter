"""NetLimiter exact Dark Theme (sampled from ui-refrensi screenshots)."""

# Layout
BG_APP = "#1e1e1e"            # main window background
BG_DARK = "#1e1e1e"
BG_PANEL = "#252526"          # toolbar / panel
BG_TABLE = "#1e1e1e"          # tree background
BG_HEADER = "#2d2d2d"         # column header
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

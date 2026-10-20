"""MiniLimiter dark theme.

A single source of truth for colours, spacing and ttk styling so every tab,
panel, table and control speaks the same visual language.  Legacy token names
are kept intact for the other UI modules (and for older tests).
"""

# ---------------------------------------------------------------------------
# Layout / surfaces
# ---------------------------------------------------------------------------
BG_APP = "#0d1014"             # window / empty space
BG_DARK = "#0d1014"
BG_PANEL = "#171c23"           # toolbar, side panel
BG_PANEL_ALT = "#12171d"       # recessed panel
BG_TABLE = "#11161c"           # tree background
BG_CARD = "#1b212a"            # cards inside panels
BG_CARD_ALT = "#232c38"
BG_HOVER = "#2a3442"
BG_SECONDARY = "#171c23"
BG_HEADER = "#1d242e"
BG_ROW_HOVER = "#242d39"
BG_ROW_SELECTED = "#2a6da8"
SELECT_BLUE = "#2c7fc7"

# Tabs
TAB_ACTIVE_BG = "#f0c94f"      # NetLimiter-style yellow indicator
TAB_ACTIVE_TEXT = "#101318"
TAB_BG = "transparent"
TAB_TEXT = "#bcc7d6"
TAB_HOVER = "#252e3a"

# Accents
ACCENT = "#6cb5ff"
ACCENT_HOVER = "#8cc7ff"
ACCENT_SOFT = "#173a5c"
ACCENT_LIME = "#9ee66b"
DOT_GREEN = "#9ee66b"
DOT_GRAY = "#737f92"
DOT_AMBER = "#f0c94f"
COLOR_DOWNLOAD = "#9ee66b"
COLOR_UPLOAD = "#ff9090"
COLOR_LIMIT_BADGE = "#7cc2ff"
LIMIT_BLUE = "#2b6ea8"
PRIMARY_BG = "#3a8df0"
PRIMARY_HOVER = "#5aa2ff"
DANGER_BG = "#c65454"
DANGER_HOVER = "#de6b6b"
WARN = "#f0b34d"

# Text
TEXT_MAIN = "#f3f6fb"
TEXT_MUTED = "#c9d2df"
TEXT_DISABLED = "#8a96a8"
TEXT_SUBTLE = "#aab5c5"
TEXT_LINK = "#86c6ff"
TEXT_GREEN = "#9ee66b"
TEXT_YELLOW = "#f0c94f"
TEXT_RED = "#ff9d9d"

# Lines / controls
BORDER_COLOR = "#3a4554"
BORDER_STRONG = "#536176"
GRID_COLOR = "#303947"
SURFACE_1 = "#171c23"
SURFACE_2 = "#232c38"
SURFACE_3 = "#303b4a"
HEADER_BG = "#1e2631"
HEADER_FG = "#e8eef7"
ROW_ALT_BG = "#171d25"
ROW_SEL_BG = "#2a6da8"
ROW_SEL_FG = "#ffffff"
BTN_BG = "#2a3441"
BTN_HOVER = "#3b4859"
BTN_ACTIVE_BG = "#f0c94f"
BTN_ACTIVE_FG = "#101318"
INPUT_BG = "#11161d"
INPUT_BORDER = "#4c5a6e"
INPUT_FOCUS = "#6cb5ff"
CHIP_BG = "#2a3441"
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 10
RADIUS_PILL = 999

# Scrollbar
SCROLL_BG = "#11161c"
SCROLL_SLIDER = "#4a5769"
SCROLL_ACTIVE = "#66758a"
SCROLL_ARROW = "#11161c"

# Fonts
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"
FONT_SIZE = 12


def apply_dark_ttk():
    """Configure global ttk styles once at startup (clam + dark scrollbars)."""
    from tkinter import ttk
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    for orient in ("Vertical", "Horizontal"):
        sname = orient + ".TScrollbar"
        try:
            style.configure(
                sname,
                background=SCROLL_SLIDER,
                troughcolor=SCROLL_BG,
                bordercolor=SCROLL_BG,
                lightcolor=SCROLL_SLIDER,
                darkcolor=SCROLL_SLIDER,
                arrowcolor=SCROLL_ARROW,
                arrowsize=1,
                width=13,
                relief="flat",
                borderwidth=0,
            )
            style.map(
                sname,
                background=[("active", SCROLL_ACTIVE), ("pressed", SCROLL_ACTIVE)],
                arrowcolor=[("active", SCROLL_ARROW), ("pressed", SCROLL_ARROW)],
            )
        except Exception:
            pass

    # Draggable panel dividers (dark, thin, with a little breathing room).
    for name in ("Dark.TPanedwindow", "Dark.Vertical.TPanedwindow",
                 "Dark.Horizontal.TPanedwindow"):
        try:
            style.configure(name, background=BORDER_COLOR, borderwidth=0,
                            sashwidth=8, sashrelief="flat", gripcount=0)
        except Exception:
            pass

    try:
        style.configure(
            "Dark.TCombobox",
            fieldbackground=INPUT_BG,
            background=SURFACE_3,
            foreground=TEXT_MAIN,
            arrowcolor=TEXT_MUTED,
            borderwidth=1,
            relief="flat",
            padding=4,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", INPUT_BG), ("focus", INPUT_BG)],
            foreground=[("disabled", TEXT_DISABLED)],
            bordercolor=[("focus", INPUT_FOCUS)],
        )
    except Exception:
        pass


def style_table(style_name: str, rowheight: int = 31, font_size: int = 12) -> None:
    """Style a Treeview consistently: flat dark header + clean readable rows."""
    from tkinter import ttk
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    try:
        style.configure(
            style_name,
            background=BG_TABLE,
            foreground=TEXT_MAIN,
            fieldbackground=BG_TABLE,
            rowheight=rowheight,
            font=(FONT_FAMILY, font_size),
            borderwidth=0,
            relief="flat",
            focuscolor=BG_TABLE,
            lightcolor=BG_TABLE,
            darkcolor=BG_TABLE,
        )
        style.configure(
            f"{style_name}.Heading",
            background=HEADER_BG,
            foreground=HEADER_FG,
            font=(FONT_FAMILY, 11, "bold"),
            relief="flat",
            borderwidth=0,
            padding=(10, 8),
        )
        style.map(
            style_name,
            background=[("selected", ROW_SEL_BG)],
            foreground=[("selected", ROW_SEL_FG)],
        )
        style.map(
            f"{style_name}.Heading",
            background=[("active", SURFACE_3)],
            foreground=[("active", "#ffffff")],
        )
    except Exception:
        pass


def fit_text(text: str, pixels: int, reserve: int = 0,
             char_width: float = 6.6) -> str:
    """Truncate a label with an ellipsis so it fits the given pixel width.

    Tables clip text without any marker, which reads like a bug.  This keeps
    the value readable ("Antimalware Service Exec…") on every column width.
    """
    text = text or ""
    if pixels <= 0:
        return text
    usable = pixels - reserve
    max_chars = int(usable / char_width)
    if max_chars < 4:
        max_chars = 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1].rstrip() + "…"


def tree_col_width(tree, col: str, default: int = 120) -> int:
    """Displayed width of a treeview column (accounts for stretching)."""
    try:
        children = tree.get_children("")
        if children:
            bbox = tree.bbox(children[0], col)
            if bbox and bbox[2] > 0:
                return int(bbox[2])
    except Exception:
        pass
    try:
        width = int(tree.column(col, "width"))
        if width > 0:
            return width
    except Exception:
        pass
    return default


def decorate_tree(tree, alt_bg: str = ROW_ALT_BG) -> None:
    """Standard zebra + state tags for a Treeview."""
    try:
        tree.tag_configure("alt", background=alt_bg)
        tree.tag_configure("active", foreground=TEXT_GREEN)
        tree.tag_configure("selblue", background=ROW_SEL_BG)
    except Exception:
        pass


def bind_mousewheel(tree):
    """Mouse-wheel scrolling for a ttk.Treeview (Windows/macOS/Linux)."""
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

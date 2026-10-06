"""Letter-tile icons per aplikasi.

Menggantikan placeholder glyph unicode yang dirender sebagai
kotak/tanda-tanya di font Windows. Setiap exe dapat tile 16px deterministik:
warna dari hash nama + huruf awal — selalu tampil, tanpa dependensi font.

Aman headless: tanpa display Tk, `get_app_tile()` mengembalikan None
(pemanggil harus fallback ke teks saja).
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("MiniLimiter.Icons")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    _HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore
    ImageTk = None  # type: ignore
    _HAS_PIL = False

# Palet gelap-ramah (kontras cukup untuk huruf putih di atasnya).
_TILE_COLORS = (
    "#007acc", "#7cbb00", "#b35400", "#6a5acd", "#008080",
    "#a83a3a", "#5c6bc0", "#00897b", "#8e24aa", "#978a00",
    "#546e7a", "#6d4c41",
)

_pil_cache: Dict[Tuple[str, int], object] = {}
_photo_cache: Dict[Tuple[str, int, object], object] = {}


def tile_color(app_name: str) -> str:
    """Warna tile deterministik dari nama aplikasi (stabil antar run)."""
    key = (app_name or "").lower().strip() or "?"
    digest = hashlib.md5(key.encode("utf-8", "ignore")).digest()
    return _TILE_COLORS[digest[0] % len(_TILE_COLORS)]


def tile_letter(app_name: str) -> str:
    """Huruf tile: karakter alfanumerik pertama, kapital. Fallback '•'."""
    for ch in (app_name or ""):
        if ch.isalnum():
            return ch.upper()
    return "•"


def _render_tile(app_name: str, size: int):
    """Gambar PIL tile (tanpa Tk) — bisa di-cache lintas interpreter."""
    name = (app_name or "").lower().strip() or "?"
    color = tile_color(name)
    letter = tile_letter(app_name or "?")
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=max(2, size // 4), fill=color)
    except Exception:
        d.rectangle([0, 0, size - 1, size - 1], fill=color)
    try:
        font = ImageFont.load_default(size=max(8, int(size * 0.62)))
    except TypeError:
        font = ImageFont.load_default()
    try:
        bbox = d.textbbox((0, 0), letter, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - 1),
               letter, font=font, fill=(255, 255, 255, 255))
    except Exception:
        pass
    return img


def get_app_tile(app_name: str, size: int = 16, master=None):
    """Bangun (atau ambil dari cache) ikon tile PhotoImage untuk Treeview.

    `master` = widget Treeview pemilik (dipakai sebagai master PhotoImage agar
    ikon menempel ke interpreter Tk yang benar — wajib saat ada >1 root,
    mis. antar test). Tanpa master dipakai default root.

    Returns None bila Pillow/Tk tidak tersedia (headless) — pemanggil
    wajib memakai `tile or ""` saat insert ke Treeview.
    """
    if not _HAS_PIL:
        return None
    name = (app_name or "").lower().strip()
    size = int(size)
    interp = None
    if master is not None:
        try:
            interp = id(master.tk)
        except Exception:
            interp = None
    key = (name, size, interp)
    hit = _photo_cache.get(key)
    if hit is not None:
        try:
            hit.width()  # validasi: cache dari root Tk lama ikut mati saat root dihancurkan
            return hit
        except Exception:
            _photo_cache.pop(key, None)
    try:
        pil_key = (name, size)
        pil = _pil_cache.get(pil_key)
        if pil is None:
            pil = _render_tile(app_name or "?", size)
            _pil_cache[pil_key] = pil
        if master is not None:
            photo = ImageTk.PhotoImage(image=pil, master=master)
        else:
            photo = ImageTk.PhotoImage(image=pil)
    except Exception as e:
        logger.debug(f"tile icon failed for {app_name!r}: {e}")
        return None
    _photo_cache[key] = photo
    return photo


def clear_cache() -> None:
    _pil_cache.clear()
    _photo_cache.clear()

"""Tests for app tile icons + no-tofu glyph regression (headless-safe)."""

import pathlib
import unittest


class TestNoTofuGlyphs(unittest.TestCase):
    # Glyph yang terbukti jadi kotak/tanda-tanya di font Windows/Tk:
    # emoji warna (tidak ada versi mono) + geometri langka + panah suplemen.
    FORBIDDEN = ["🌐", "⛔", "⧩", "⧫", "▤", "◫", "⌕", "﹀", "︿", "⬇", "⬆", "⚙", "◆"]

    def test_no_tofu_glyphs_in_ui(self):
        bad = []
        for path in (pathlib.Path("src/ui").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for g in self.FORBIDDEN:
                if g in text:
                    bad.append(f"{path.name} masih mengandung {g!r}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_no_tofu_glyphs_in_repo_src(self):
        bad = []
        for path in (pathlib.Path("src").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for g in self.FORBIDDEN:
                if g in text:
                    bad.append(f"{path} masih mengandung {g!r}")
        self.assertEqual(bad, [], "\n".join(bad))


class TestAppTiles(unittest.TestCase):
    def test_tile_color_deterministic(self):
        from src.utils.icons import tile_color, _TILE_COLORS
        c1 = tile_color("chrome.exe")
        self.assertIn(c1, _TILE_COLORS)
        self.assertEqual(c1, tile_color("CHROME.EXE"))  # case-insensitive
        self.assertEqual(tile_color(""), tile_color("?"))

    def test_tile_letter(self):
        from src.utils.icons import tile_letter
        self.assertEqual(tile_letter("chrome.exe"), "C")
        self.assertEqual(tile_letter("7zip.exe"), "7")
        self.assertEqual(tile_letter(""), "•")

    def test_get_app_tile_graceful(self):
        """Dengan display: PhotoImage 16px + cache. Tanpa display: None (tidak raise)."""
        from src.utils.icons import get_app_tile
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
        except Exception as e:
            self.assertIsNone(get_app_tile("chrome.exe"))
            return
        try:
            t1 = get_app_tile("chrome.exe")
            self.assertIsNotNone(t1)
            self.assertEqual(int(t1.width()), 16)
            self.assertEqual(int(t1.height()), 16)
            self.assertIs(t1, get_app_tile("chrome.exe"))  # cache
            t2 = get_app_tile("spotify.exe", size=20)
            self.assertEqual(int(t2.width()), 20)
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()

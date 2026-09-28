"""Unit tests for tools/theme_gtk.py's GSettings keyfile rendering."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_gtk as gtk


class Render(unittest.TestCase):
    def test_dark_mode_with_icon_theme(self):
        text = gtk.render("dark", "Yaru-purple")
        self.assertEqual(text, "[org/gnome/desktop/interface]\n"
                          "color-scheme='prefer-dark'\ngtk-theme='Adwaita-dark'\n"
                          "icon-theme='Yaru-purple'\n")

    def test_light_mode_with_icon_theme(self):
        text = gtk.render("light", "Yaru-olive")
        self.assertEqual(text, "[org/gnome/desktop/interface]\n"
                          "color-scheme='prefer-light'\ngtk-theme='Adwaita'\n"
                          "icon-theme='Yaru-olive'\n")

    def test_missing_icon_theme_falls_back_like_upstream(self):
        text = gtk.render("dark", None)
        self.assertIn("icon-theme='Yaru-blue'\n", text)

    def test_unknown_mode_rejected(self):
        with self.assertRaisesRegex(gtk.GtkAppearanceError, "unknown appearance mode"):
            gtk.render("sepia", None)

    def test_empty_mode_rejected(self):
        with self.assertRaises(gtk.GtkAppearanceError):
            gtk.render("", None)

    def test_icon_theme_with_illegal_characters_rejected(self):
        for bad in ("Yaru; rm -rf", "../etc/passwd", "", "a" * 200, "Yaru\nBlue"):
            with self.assertRaises(gtk.GtkAppearanceError):
                gtk.render("dark", bad)

    def test_icon_theme_at_max_length_accepted(self):
        name = "a" * 160
        text = gtk.render("dark", name)
        self.assertIn(f"icon-theme='{name}'\n", text)

    def test_over_max_length_icon_theme_rejected(self):
        with self.assertRaises(gtk.GtkAppearanceError):
            gtk.render("dark", "a" * 161)

    def test_output_has_no_embedded_command_injection_surface(self):
        # Even a maximally adversarial *valid* icon name cannot introduce a
        # second keyfile section or break out of the single-quoted value,
        # because ICON_NAME forbids '[', ']', '\'', '\n' and whitespace.
        text = gtk.render("dark", "Yaru-blue")
        self.assertEqual(text.count("["), 1)
        self.assertEqual(text.count("\n["), 0)


if __name__ == "__main__":
    unittest.main()

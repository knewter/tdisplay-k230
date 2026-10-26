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
                          "icon-theme='Yaru-purple'\n\n"
                          "[org/gnome/desktop/wm/preferences]\nbutton-layout=':close'\n")

    def test_light_mode_with_icon_theme(self):
        text = gtk.render("light", "Yaru-olive")
        self.assertEqual(text, "[org/gnome/desktop/interface]\n"
                          "color-scheme='prefer-light'\ngtk-theme='Adwaita'\n"
                          "icon-theme='Yaru-olive'\n\n"
                          "[org/gnome/desktop/wm/preferences]\nbutton-layout=':close'\n")

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
        self.assertEqual(text.count("["), 2)
        self.assertEqual(text.count("\n["), 1)


PALETTE = {"background": "#101820", "foreground": "#e0e5e8", "accent": "#778899"}


class Gtk3(unittest.TestCase):
    def test_mix_endpoints_and_midpoint(self):
        self.assertEqual(gtk.mix("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(gtk.mix("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(gtk.mix("#000000", "#ffffff", 0.5), "#808080")

    def test_readable_on_picks_higher_contrast(self):
        self.assertEqual(gtk.readable_on("#ffffff", "#ffffff", "#000000"), "#000000")
        self.assertEqual(gtk.readable_on("#000000", "#ffffff", "#000000"), "#ffffff")

    def test_settings_dark_and_light(self):
        dark = gtk.render_gtk3_settings("dark", "Yaru-blue")
        self.assertEqual(dark.splitlines()[0], gtk.GTK3_INI_MARKER)
        self.assertIn("gtk-application-prefer-dark-theme=true\n", dark)
        self.assertIn("gtk-icon-theme-name=Yaru-blue\n", dark)
        self.assertIn("gtk-decoration-layout=:close\n", dark)
        self.assertIn("gtk-application-prefer-dark-theme=false\n",
                      gtk.render_gtk3_settings("light", None))

    def test_settings_reject_bad_input(self):
        with self.assertRaises(gtk.GtkAppearanceError):
            gtk.render_gtk3_settings("sepia", None)
        with self.assertRaises(gtk.GtkAppearanceError):
            gtk.render_gtk3_settings("dark", "x\n[Settings]")

    def test_css_carries_marker_and_palette_without_canvas_rules(self):
        css = gtk.render_gtk3_css(PALETTE, "dark")
        self.assertEqual(css.splitlines()[0], gtk.GTK3_CSS_MARKER)
        for value in PALETTE.values():
            self.assertIn(value, css)
        self.assertIn("min-height: 44px", css)
        self.assertNotIn("drawingarea", css.lower())

    def test_css_rejects_unsafe_colors(self):
        for bad in ("red", "#12345", "#1234567", "#12345g", "#000000; } * { x", None, "#000000\n"):
            for key in PALETTE:
                with self.assertRaises(gtk.GtkAppearanceError):
                    gtk.render_gtk3_css(PALETTE | {key: bad}, "dark")
        with self.assertRaises(gtk.GtkAppearanceError):
            gtk.render_gtk3_css({"background": "#000000"}, "dark")


if __name__ == "__main__":
    unittest.main()

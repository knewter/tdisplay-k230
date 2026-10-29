"""Print the font GTK4/libadwaita resolves and a label's laid-out height.

Run inside a Wayland session with GSETTINGS_BACKEND=keyfile, as the board's
Files launcher does. One JSON line on stdout, then exit.
"""
import json
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk


def report(window, body, caption):
    settings = Gtk.Settings.get_default()
    def label(widget):
        desc = widget.get_pango_context().get_font_description()
        return {"font": desc.to_string(), "height_px": widget.get_height()}
    print(json.dumps({
        "gtk": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        "adw": f"{Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
        "gtk-font-name": settings.props.gtk_font_name,
        "gtk-xft-dpi": settings.props.gtk_xft_dpi,
        "body": label(body), "caption": label(caption)}), flush=True)
    window.get_application().quit()
    return GLib.SOURCE_REMOVE


def activate(app):
    window = Adw.ApplicationWindow(application=app, default_width=600, default_height=300)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    body = Gtk.Label(label="Pictures", valign=Gtk.Align.START)
    caption = Gtk.Label(label="open-test.png", valign=Gtk.Align.START)
    caption.add_css_class("caption")
    box.append(body); box.append(caption)
    window.set_content(box)
    window.present()
    GLib.timeout_add(1500, report, window, body, caption)


app = Adw.Application(application_id="org.k230.FontProbe")
app.connect("activate", activate)
app.run([])

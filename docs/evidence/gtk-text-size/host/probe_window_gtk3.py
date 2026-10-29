"""GTK3 counterpart of probe_window.py: resolved gtk-font-name, and the font
and height of a menu-bar item and a label, as the GTK3 puzzles draw them."""
import json
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


def report(window, item, body):
    def label(widget):
        desc = widget.get_style_context().get_font(Gtk.StateFlags.NORMAL)
        return {"font": desc.to_string(), "height_px": widget.get_allocated_height()}
    print(json.dumps({
        "gtk": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        "gtk-font-name": Gtk.Settings.get_default().props.gtk_font_name,
        "menu_item": label(item.get_child()), "body": label(body)}), flush=True)
    Gtk.main_quit()
    return GLib.SOURCE_REMOVE


window = Gtk.Window(default_width=600, default_height=300)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
bar = Gtk.MenuBar()
item = Gtk.MenuItem(label="Game")
bar.append(item)
body = Gtk.Label(label="Active: 4/25")
box.pack_start(bar, False, False, 0)
box.pack_start(body, False, False, 0)
window.add(box)
window.show_all()
GLib.timeout_add(1500, report, window, item, body)
Gtk.main()

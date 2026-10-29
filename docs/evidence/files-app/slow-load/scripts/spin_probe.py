"""Minimal GTK4 window with one AdwSpinner (or a GtkSpinner) to measure per-frame damage."""
import sys, site
for p in ["/nix/store/a8nrpdvm3f6c479cb5jr66852vlmd2zm-python3.14-pycairo-1.29.0-riscv64-unknown-linux-gnu/lib/python3.14/site-packages",
          "/nix/store/ggxwkn8vpkw2ws8ca2bwrw6pd4lqfy6n-python3.14-pygobject-3.56.3-riscv64-unknown-linux-gnu/lib/python3.14/site-packages"]:
    site.addsitedir(p)
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
kind = sys.argv[1]
app = Adw.Application(application_id="org.k230.SpinProbe")
def activate(a):
    w = Adw.ApplicationWindow(application=a, title="spin")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
    box.append(Gtk.Label(label="spinner probe"))
    if kind == "adw": box.append(Adw.Spinner())
    elif kind == "gtk": s = Gtk.Spinner(); s.start(); box.append(s)
    w.set_content(box); w.present()
    GLib.timeout_add_seconds(int(sys.argv[2]), lambda: a.quit())
app.connect("activate", activate)
app.run([])

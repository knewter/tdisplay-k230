#!/usr/bin/env python3
"""gnotify_probe.py: send one notification the way a GTK app does, through
GApplication.send_notification, then keep the app alive for a few seconds."""
import site
# Portfolio's pygobject and pycairo on the board image (no system site-packages).
for p in ["/nix/store/a8nrpdvm3f6c479cb5jr66852vlmd2zm-python3.14-pycairo-1.29.0-riscv64-unknown-linux-gnu/lib/python3.14/site-packages",
          "/nix/store/ggxwkn8vpkw2ws8ca2bwrw6pd4lqfy6n-python3.14-pygobject-3.56.3-riscv64-unknown-linux-gnu/lib/python3.14/site-packages"]:
    site.addsitedir(p)
import gi; gi.require_version('Gio', '2.0'); gi.require_version('GLib', '2.0')
from gi.repository import Gio, GLib
app = Gio.Application(application_id='org.k230.GNotifyProbe', flags=Gio.ApplicationFlags.NON_UNIQUE)
app.register(None)
n = Gio.Notification.new('GNotify probe')
n.set_body('sent with g_application_send_notification')
n.set_priority(Gio.NotificationPriority.HIGH)
app.send_notification('probe', n)
print('sent; backend env GNOTIFICATION_BACKEND =', GLib.getenv('GNOTIFICATION_BACKEND'), flush=True)
loop = GLib.MainLoop(); GLib.timeout_add_seconds(6, loop.quit); loop.run()

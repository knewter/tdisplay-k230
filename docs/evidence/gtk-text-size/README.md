# GTK app text follows the text size

Change: `gtk-app-text-follows-the-text-size`.

## Host: which setting GTK4 honours (task 1.1)

This is host evidence only.

- **Command:** `docs/evidence/gtk-text-size/host/probe-env.sh`, run
  2026-10-29 08:37 CDT. Output: `host/probe-output.txt`.
- **Versions:** the repo's pinned nixpkgs, GTK 4.22.4 and libadwaita 1.9.3,
  the same versions as the board image.
- **Environment:** a headless Sway, with the Files launcher's environment
  (`GDK_BACKEND=wayland`, `GSETTINGS_BACKEND=keyfile`, `GSK_RENDERER=cairo`).
  There was no session bus, because the board runs no xdg-desktop-portal.
- **What was measured:** `probe_window.py` reads the resolved
  `gtk-font-name` and the font and laid-out height of a plain label and a
  `.caption` label.

| Variant | Resolved font | Body label | Caption label |
|---|---|---|---|
| neither | Sans 10 | 13.3 px font, 19 px tall | 10.9 px font, 16 px tall |
| keyfile `font-name='DejaVu Sans 13'` | Sans 10 | 13.3 px, 19 | 10.9 px, 16 |
| keyfile font + `text-scaling-factor=2.0` | Sans 10 | 13.3 px, 19 | 10.9 px, 16 |
| `gtk-4.0/settings.ini` `gtk-font-name=DejaVu Sans 13` | DejaVu Sans 13 | 17.3 px, 21 | 14.2 px, 20 |
| settings.ini 26, keyfile 13 | DejaVu Sans 26 | 34.7 px, 41 | 28.4 px, 40 |

Findings:

- GTK4 takes its font from `gtk-4.0/settings.ini` and ignores the GSettings
  keyfile's `font-name` and `text-scaling-factor` when there is no portal.
- libadwaita's `.caption` is relative to the base font (about 0.82×), so it
  scales with it.
- The default, "Sans 10" (13.3 px), matches the about 13 px text measured in
  the board's Files capture (`docs/evidence/open-with/board/files-home.png`).

A first run with the host's session bus present resolved every variant to
the desktop portal's "Noto Sans 14". The probe therefore unsets
`DBUS_SESSION_BUS_ADDRESS`.

### GTK3 (found during task 3.1)

Net did not change on the board at 200% even though its `settings.ini`
said 26 pt, so the probe gained a GTK3 run: `PROBE_GTK=3 host/probe-env.sh`,
2026-10-29 09:02 CDT. It used GTK 3.24.52 with `gsettings-desktop-schemas`
on `XDG_DATA_DIRS`, which is how nixpkgs wraps every GTK3 app (Net's
environment on the board carries that schema and the dconf GIO module).

| Variant | Resolved font | Menu item |
|---|---|---|
| neither | Adwaita Sans 11 | 19 px |
| `settings.ini` `gtk-font-name=DejaVu Sans 13` | Adwaita Sans 11 | 19 px |
| `settings.ini` 26 | Adwaita Sans 11 | 19 px |
| `gtk.css` `window, tooltip { font-family: "DejaVu Sans"; font-size: 26pt; }` | DejaVu Sans 26 | 42 px |

- GTK3 on Wayland takes `gtk-font-name` from GSettings whenever the schema
  is installed, so `settings.ini` never reached Net.
- The adapter's generated `gtk-3.0/gtk.css` now sets the font on the
  toplevel and tooltip nodes. Every widget inherits it, and rules relative
  to it, such as the menu bar's 115%, keep their ratio.

## Board (task 3.1)

This is board evidence: native `grim` captures, with Files opened by an
injected tap on its Home dock icon, Net by `swaymsg exec`, and the menu by
an injected tap. The text step was changed with
`k230-theme vision --text-scale largest|default`, the path the Settings
Vision page uses. shell-idle was stopped during the captures and restarted
afterwards.

| Capture | Build | Step | Measured |
|---|---|---|---|
| `board/files-100.png` | `njzllqxw…` | 100% | "Pictures" and "Starred" ink 14 px tall, against 10 px in `docs/evidence/open-with/board/files-home.png` (GTK4 default Sans 10) |
| `board/files-200.png` | `yrfr1x6b…` | 200% | sidebar, title and path bar at twice the size; window 1232x568, no overflow |
| `board/net-100.png`, `board/net-100-menu.png` | `2867v7pm…` | 100% | Game menu "Restart" ink 13 px |
| `board/net-200.png`, `board/net-200-menu.png` | `2867v7pm…` | 200% | menu bar doubled; "Restart" ink 26 px; the menu scrolls within the panel |

Builds `njzllqxw` and `yrfr1x6b` already had the GTK4 mechanism that
`2867v7pm` ships. `2867v7pm` adds only the GTK3 CSS rule.

### The step reaches new launches without a restart

Theme and step changes run `app_appearance.sync` from the theme
transaction. That moves the adapter's `app-appearance/active` pointer, but
before this change the `~/.config/gtk-3.0` and `gtk-4.0` links pointed at
one concrete generation. Only a CLI `sync` relinked them, and it ran at
shell start and at each terminal launch.

On build `njzllqxw` the board showed the result: after a step change to
200%, `active` held 26 pt while `~/.config/gtk-4.0/settings.ini` still
linked to the previous generation at 13 pt.

The links now go through `active`. On `yrfr1x6b` and later, switching
200% → 100% with `k230-theme vision` changed
`~/.config/gtk-4.0/settings.ini` from 26 to 13 pt at once, with no restart.

### Not caused by this change: Files takes minutes to load a folder

Files sat at "Loading…" for over two minutes, with its main thread at about
70% of a core, at both steps. A fresh Nautilus started with the
pre-change GTK4 settings (no font line) behaved the same (`board/files-old-config-loading.png`,
CPU sampled every 10 s), so this predates the change. Earlier captures in
`docs/evidence/gtk-touch-floor/` showed the folder about 20 s after launch.
It needs its own investigation.

## Operator on glass (task 3.2)

The operator used build `2867v7pm…` (test-activated) at the 100% step,
2026-10-29 ~09:53 CDT. Reply, verbatim: "works great.", then "loading is very
slow like you said". This confirms the slow folder load recorded above as
the operator saw it; that load predates this change.

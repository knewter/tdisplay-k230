# Omarchy and NixOS research for the K230 shell

Checked 2026-09-22. This is a source and UX comparison; it does not propose
importing an Omarchy desktop into the image.

## What is upstream

[Omarchy](https://github.com/omacom/omarchy/tree/quattro) is the official
project from omacom. Its own manual describes it as Arch Linux plus Hyprland,
and its primary implementation is a Hyprland/Lua configuration with a large
set of shell scripts. The official repository is MIT licensed
([LICENSE](https://github.com/omacom/omarchy/blob/quattro/LICENSE)). The
current upstream `quattro` ref observed during this audit is
`d3cfd53b997f8bdcf776b8db68bf0d735e7a065d`; see its
[commit history](https://github.com/omacom/omarchy/commits/quattro) and
[releases](https://github.com/omacom/omarchy/releases).

The following are independent community ports, not official Omarchy NixOS
releases:

* [zicochaos/omarchy-nix](https://github.com/zicochaos/omarchy-nix) vendors
  the upstream tree and supplies NixOS/Home Manager modules. Its README says
  x86_64-only and its options pull in Hyprland, uwsm, SDDM, Plymouth, a large
  application set, fonts and desktop services. Its observed `main` ref is
  `20ed5de64aae2c1e1a07f03cdd4eef2aa52be69f`. The repository is MIT licensed,
  with upstream portions also MIT licensed ([LICENSE](https://github.com/zicochaos/omarchy-nix/blob/main/LICENSE)).
* [olafkfreund/nixarchy](https://github.com/olafkfreund/nixarchy) is another
  community, vendored Omarchy 4.x port. It uses Hyprland, QuickShell and a
  much larger shell/app surface; its observed `main` ref is
  `e87452ed2edf9ed16a1af6279bf8e5ffb67fd8fc`. The repository has no root
  `LICENSE` at the checked URL, so its code should not be copied without a
  file-level license review.
* [fandangos/nixos-omarchy-kde](https://github.com/fandangos/nixos-omarchy-kde)
  is a community KDE/Home Manager port, not a K230/Sway port. Its observed
  `main` ref is `7506a48f4c5566a4d43ce92f5793b9b079ecb3dc` and its repository
  declares MIT ([LICENSE](https://github.com/fandangos/nixos-omarchy-kde/blob/main/LICENSE)).

The official manual links to a user-maintained NixOS port and warns that it
can go stale. The Nix ports are useful references for packaging and first-run
workflow, not evidence that Omarchy supports riscv64, Sway, Pixman, or this
panel.

## Fit for this image

The target is a 568x1232 portrait panel with Sway/wlroots and Pixman on
riscv64, 1 GiB RAM, and an existing shell status-bar touch menu. The current
menu is deliberately small: [nix/touch-menu.sh](../../nix/touch-menu.sh#L19)
has Apps, Windows, Keyboard, and System pages; its window list and 128/178 px
touch targets are at lines 22-69, and it launches the existing foot/htop and
wvkbd tools at lines 73-109. [nix/shell.nix](../../nix/shell.nix#L59) explains
why it uses swaybar click hotspots and avoids a gesture or heavyweight
launcher.

Do not reuse the Omarchy compositor/session layer, Hyprland Lua bindings,
QuickShell/QML, SDDM, Plymouth, PipeWire/Bluetooth/NetworkManager defaults,
the full application catalogue, or x86_64-specific package assumptions. They
add closure and runtime cost and depend on GPU/compositor or keyboard-centric
desktop behavior that this image does not have. Omarchy's use of a keyboard
launcher, Super-key bindings, and ordinary desktop-sized windows also does
not prove physical touch accuracy.

## Low-cost adaptations

These are UX and small-data ideas, in priority order. They can remain in the
current shell process and do not require a new compositor or package manager.

1. **Make the existing Apps page the one launcher surface.** Keep Terminal,
   Monitor, Keyboard and System as large, named buttons, add a visible Home/
   Back affordance on every page, and keep a second page or vertical list if
   more apps arrive. Preserve the current `swaymsg` focus-or-start behavior.
   This gives the Omarchy single-entry launcher feel while matching portrait
   fingers and the current worker's scope.
2. **Use a declarative built-in action table.** The Nix ports' module/options
   split is a useful pattern: define label, command, icon/text, and required
   confirmation in one Nix-generated table. For this image it should describe
   only already-installed programs and Sway actions; a tap must never run
   `nix`, `pacman`, or an unreviewed network installer. A future preference
   file can change the table at rebuild time.
3. **Add a tiny theme token layer.** Omarchy's TOML/template themes suggest
   centralizing background, foreground, accent, warning, font size and target
   width. Generate the existing swaybar/foot/wvkbd colors from one small Nix
   attrset or shell config, with a high-contrast default. Do not copy its icon
   and font catalogue or introduce GTK/Qt theme machinery.
4. **Add a local first-run/help page.** Borrow the ports' first-run hooks as a
   one-time, offline explanation of Apps, Windows, Keyboard, System,
   confirmation behavior, and the physical-vs-injected touch evidence. Store a
   marker under the shell user's writable state and make Help reopenable. Keep
   it static and text-based so it costs no daemon or network access.
5. **Extend the existing System and Windows pages conservatively.** Add
   restart-shell/help only where recovery is safe, retain explicit reboot and
   poweroff confirmation, and show a scrollable/finger-sized window list from
   the existing Sway tree. This borrows Omarchy's session-control discoverability
   without importing polkit, lock-screen, display-manager, or QuickShell code.

Each adaptation needs acceptance evidence on the real panel: readable in
portrait, injected taps reach the intended control, and a separate physical
touch recording establishes accuracy. Omarchy screenshots or x86_64/GPU
tests cannot substitute for that evidence.

## What the current Omarchy launcher actually does

The current official `quattro` tree has moved past the older Walker/Elephant
stack. At immutable ref
[`d3cfd53b997f8bdcf776b8db68bf0d735e7a065d`](https://github.com/omacom/omarchy/commit/d3cfd53b997f8bdcf776b8db68bf0d735e7a065d), the launcher is a menu in the
long-running Quickshell process, and its application data service is
[`shell/services/AppLibrary.qml`](https://github.com/omacom/omarchy/blob/d3cfd53b997f8bdcf776b8db68bf0d735e7a065d/shell/services/AppLibrary.qml):

* It consumes Quickshell's `DesktopEntries.applications.values`, filters both
  configured hidden IDs and IDs discovered by the session's hidden-entry
  helper, and sorts through `AppSearch.sortedEntries` (lines 785-810).
* It resolves icons through a small XDG icon index, falling back to themed
  lookup and then `application-x-executable` (lines 812-844). The index scans
  `$HOME/.icons`, `$HOME/.local/share/icons`, each `$XDG_DATA_DIRS` icon
  directory, and `/usr/share/pixmaps`; a 750 ms debounce coalesces changes
  (lines 923-949 and 1075-1085).
* It does not interpolate `Exec=` itself. `launch()` starts
  `uwsm-app -- gtk-launch <desktop-id>.desktop` and shell-quotes the ID (lines
  846-863). This lets the desktop-entry launcher perform the specification's
  field-code and environment handling while keeping the entry ID bounded.
* The old Walker/Elephant behavior remains useful historical context: Walker
  indexed desktop applications through Elephant and offered fuzzy/prefix
  modes. It is not the current Quattro implementation; importing either
  daemon would be the wrong dependency decision for this image.

For a future K230 app page, use the same data contract rather than copying
Quickshell: scan the standard application directories, parse `Name`, `Icon`,
`NoDisplay`/`Hidden`, and `Exec`, sort a bounded list, and refresh after a
directory change. Prefer GLib's `GDesktopAppInfo`/`GAppInfo` for parsing and
launching if the existing closure already contains GLib; it handles quoting,
field codes, and desktop-entry launch context more safely than a handwritten
`Exec` parser. Confirm the incremental closure cost with `nix path-info` before
adding GLib solely for this feature. If GLib is not already present, retain a
small allowlisted action table until that cost and the launch environment
(`DISPLAY`, Wayland, D-Bus) are measured. Never execute raw `Exec=` text with
`sh -c`, and keep package installation or network actions outside a tap.

The low-cost adaptation for this panel is therefore a bounded desktop-entry
provider behind the existing portrait UI: cache entries in memory, show large
text/icon cards, use a single selected entry, and invoke the desktop-entry
API with a fixed launch context. Keep Terminal, Monitor, Keyboard, Windows,
and System as built-in fallback actions when no desktop file is available.

### GLib launch caveats for this image

`GDesktopAppInfo` is the right parser/launcher boundary, but it is not a
complete terminal policy. The UNIX header is
`<gio/gdesktopappinfo.h>`, so the derivation must use `gio-unix-2.0` in
`pkg-config` and link the UNIX GIO library. `g_app_info_launch()` inherits the
launcher environment and can add launch-context variables such as
`GIO_LAUNCHED_DESKTOP_FILE`; it does not magically repair a missing session
environment. Preserve `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `SWAYSOCK`, and
the Nix service's PATH when starting it from swaybar.

For a desktop entry with `Terminal=true`, GLib prepends a terminal selected
from a fixed known list. In the current GLib source that list includes
`xdg-terminal-exec`, `kgx`, `gnome-terminal`, `mate-terminal`, `xfce4-terminal`,
`tilix`, `konsole`, `nxterm`, `color-xterm`, `rxvt`, `dtterm`, and `xterm`; it
does not include `foot`. With only foot installed, `g_app_info_launch()` can
therefore fail with “Unable to find terminal required for application.” Add a
small Nix-provided `xdg-terminal-exec` wrapper that invokes the pinned foot
profile (and put it in the service PATH), or explicitly handle Terminal=true
through the same trusted Foot bridge. Do not replace `Exec` with a shell
string.

Use `g_app_info_should_show()` and desktop-entry type/ID filtering, retain
user-over-system desktop-ID precedence, and skip `Hidden`, `NoDisplay`, and
inapplicable `OnlyShowIn`/`NotShowIn` entries. `DBusActivatable=true` can
require a working user D-Bus session; either verify the existing shell's bus
is available or mark such entries unavailable with an explanatory error.
`g_app_info_launch()` reports only launch handoff success, not whether the
application later stayed alive, so the launcher should close after a true
handoff and show a bounded error on a GLib failure.

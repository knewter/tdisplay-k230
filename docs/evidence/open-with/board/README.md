# Opening files: board evidence

Build `l2ds6vvr…` on 2026-10-28, test-activated with `switch-to-configuration
test` and `systemctl restart shell`. Evidence class: injected board. Commands
went over SSH, keys and taps went through `/var/tmp/ui.py` (uinput), and
captures are native `grim`. Task 2.1 names `tools/console.py` on the USB
console; SSH was used instead, and the reads are the same.

Test files: `~shell/open-test.png` (a generated 240x160 RGB gradient),
`~shell/open-test.pdf` (a hand-written one-page PDF; Zathura repairs its
xref and shows it), and `~shell/open-test-folder`.

## Two faults found and fixed on the way

1. **PDF had no default (build `1nhfnwx0…`).** In the running session,
   `gio mime application/pdf` printed "No default applications".
   Upstream's `org.pwmt.zathura-pdf-mupdf.desktop` runs a bare `zathura`.
   The session's PATH (read from a foot process's environ) has no system bin
   directory, so GIO drops the entry. Viewnior and Files already had overrides
   with absolute `Exec` lines. Fix: the same override for Zathura's PDF entry
   in `nix/handheld-desktop-entries.nix`.
2. **`xdg-open` from a terminal failed for images (build `wi19sdxx…`).**
   Viewnior printed "Cannot open display". The terminal's bash rebuilds
   `XDG_DATA_DIRS` from `/etc/set-environment`, which drops the session's
   overrides, so upstream `viewnior.desktop` ran. Its nixpkgs wrapper
   defaults `GDK_BACKEND` to x11. Fix: `environment.extraInit` puts the
   overrides back first, after that line.

## 2.1 GIO in the session (`gio-mime-session.txt`)

This ran as the shell user with the environment copied from a running foot
process (`/proc/<pid>/environ`).

- `image/png`: default `viewnior.desktop`; also registered: Zathura.
- `application/pdf`: default `org.pwmt.zathura-pdf-mupdf.desktop`.
- `inode/directory`: default `org.gnome.Nautilus.desktop`, alone.

`XDG_CONFIG_DIRS` is not set in the session, so GIO uses the spec default
`/etc/xdg`. `/etc/xdg/mimeapps.list` holds the defaults above.

## 2.2 `xdg-open` typed in a terminal card (`meminfo.txt`)

- `open-png.png`: `xdg-open open-test.png`. `get_tree` shows `viewnior`
  focused at 21:20:02Z, and the capture shows the gradient. MemAvailable
  went from 575824 kB (21:19:39Z, after the shell restart) to 566168 kB
  (-9.4 MB). Two of Viewnior's toolbar buttons render without icons.
- `open-pdf.png`: `xdg-open open-test.pdf`. `org.pwmt.zathura` was focused
  at 21:21:58Z. MemAvailable was 566228 kB at 21:20:16Z with Viewnior closed
  and 527616 kB with Zathura up. That interval also includes an exhibition
  card, which opened during a first attempt whose keys were lost, so the
  38.6 MB drop is not Zathura's alone.

## 2.3 Injected touch in Files

Files opened from `xdg-open .` (`files-home.png`). It opened as a floating
window about 890 px wide, not full screen. A single tap only selects
(`“open-test.png” selected`); opening takes a double tap, which is a new
`dtap` action in `ui.py`: two 60 ms touches 90 ms apart.

- PNG: `viewnior` opened and was focused (`files-dtap-png.png`).
- PDF: `org.pwmt.zathura` opened and was focused (`files-dtap-pdf.png`).
- Folder: Files navigated into it, and the window title became
  `open-test-folder` (`files-dtap-folder.png`).
- Chooser: a 900 ms long press on the PNG opened the menu, offering "Open With
  Viewnior" and "Open With…" (`files-longpress-png.png`). "Open With…"
  showed the chooser, and its search field raised the on-screen keyboard.
  With the keyboard swiped away, the list shows Viewnior (the default), then
  Recommended Apps with Viewnior and Zathura, then Other Apps starting with
  Files (`files-open-with-list.png`, `files-open-with-list-scrolled.png`).
  Cancel was tapped; no handler was changed.

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

## 2.5 Files as a full card, build `37nvncgk…`, 2026-10-28

The run was injected and unattended on the board, with the charger online
and `shell-idle` stopped. The earlier short window (about 1232x380, build
`q8k8w3mb…`) was seen during on-screen-keyboard work. Four new launches on
this build all filled the card:

- **Drawer launch, twice.** In [`files-full-drawer-rect.txt`](files-full-drawer-rect.txt),
  `get_tree` shows the container and the window rect at 1232x568 from +2 s
  to +15 s. [`files-full-card.png`](files-full-card.png) is the `grim`
  taken after that. The second drawer launch, made after the clock card had
  closed, matched it.
- **`swaymsg exec` with `WAYLAND_DEBUG=1`.** In
  [`files-wayland-sizes.txt`](files-wayland-sizes.txt), Nautilus starts with
  its own 890x550 window geometry and declares a minimum of 360x380. When
  sway configures 1232x568, Nautilus sets its window geometry to 1232x568 in
  the next commit. The 890x550 that `get_tree` reports as `geometry` is that
  first commit; sway does not update the field.
- **Keyboard raised, then hidden, over Files.**
  [`files-osk-cycle-rect.txt`](files-osk-cycle-rect.txt) shows the rect
  falling to 1232x272 while the keyboard was up and returning to 1232x568
  within 1 s of `hide`.
- **Launch with the keyboard already up.** This is the second half of
  `files-wayland-sizes.txt` and [`files-osk-first-rect.txt`](files-osk-first-rect.txt).
  Sway configured 1232x272. Nautilus could not go below its 380 minimum and
  committed 1232x380, the size of the earlier short window. Mapping the new
  card dropped the keyboard, sway configured 1232x568, and Nautilus filled it
  within 0.7 s.

**Reading.** Files fills the card whenever the layout gives it the full
height. The earlier short window matches the 1232x380 that Nautilus commits
for a layout reduced by the keyboard. It is most likely a layout left reduced
by the keyboard show/hide race that `bc450ea8` later fixed. That link is
inferred; the earlier state was not reproduced on this build.

**Not covered.** While the keyboard is up, Files cannot fit: its 380 px
minimum is taller than the 272 px left. On the first launch, the Home view
also showed "Loading…" for more than a minute before its files appeared
(`files-full-card.png` is from that wait). Neither is part of 2.5.

Scripts: [`filesrect.sh.txt`](filesrect.sh.txt), [`oskcycle.sh.txt`](oskcycle.sh.txt),
[`oskfirst.sh.txt`](oskfirst.sh.txt).

## Why

A person browsing in Files who taps a photo, a PDF or a folder should get the
image viewer, the document viewer or the file manager, and should be able to
pick another app when two can open it. On this image only text and Markdown
have a default (`xdg.mime.defaultApplications` in `nix/shell.nix` names
Omawrite for `text/plain`, `text/markdown` and `text/x-markdown`). Nothing names
a default for images, PDFs or folders, and the desktop entries disagree about
who handles what: Viewnior declares the image types, Nautilus and the hidden
Portfolio both declare `inode/directory`, and the Video entry declares no
MimeType at all and plays one fixed playlist. Whichever app GIO happens to
rank first wins, and no part of the design says what "Open with..." should do
on a 568 px glass (gap 14 of
`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`).

## What Changes

- The image carries a generated system `mimeapps.list` (NixOS writes
  `/etc/xdg/mimeapps.list` from `xdg.mime.defaultApplications`) with a default
  for each class of file the installed apps can open: images to Viewnior, PDF to
  Zathura, `inode/directory` to Nautilus's Files entry, and text as today. A
  fresh home needs nothing restored; a per-user `mimeapps.list` still overrides
  it.
- Each handler's desktop entry states the types it can really open, from the
  overrides in `nix/handheld-desktop-entries.nix` where the upstream entry is
  wrong for this image, so the chooser lists only apps that work here.
- Opening from Files and from a terminal's `xdg-open` (already installed as
  `pkgs.xdg-utils`) reach the same default.
- The chooser is Nautilus's own "Open With Other Application" dialog, with no
  new shell sheet. It lists the apps whose entries declare the file's type. At
  touch size it follows `gtk-app-chrome-reaches-the-touch-floor` (72 px rows in
  GTK4), not a bespoke control.
- No `xdg-desktop-portal`. Nautilus and GTK4 launch through GIO directly when not
  sandboxed, so a portal and its backend would add two resident processes on
  one CPU for no behaviour this image needs (design.md).

## Non-goals

- No shell-drawn "Open with" sheet. The review wanted a one-line chooser only
  when a type has two handlers; with one handler per type here there is nothing
  to choose, and the GTK dialog covers the rest.
- No portal, no Flatpak, no sandbox and no `gvfs` mounts.
- No video-file association unless the Video session is shown to take a path
  within its bounds (design.md open question 1). The Video entry stays as it
  is.
- No new app and no web browser, so no `x-scheme-handler/*`.
- No change to which apps the drawer lists.

## Capabilities

### Modified Capabilities

- `runtime/files`: a file opened from Files, or by `xdg-open`, opens in its
  default app, and another installed app can be chosen.

## Impact

- `nix/shell.nix` (`xdg.mime.defaultApplications`), 
  `nix/handheld-desktop-entries.nix` (MimeType lines; an `org.pwmt.zathura`
  override only if the upstream entry proves wrong on the board).
- No Rust, compositor or kernel change.

Host-verifiable for the generated list and entries (`nix build`, `gio mime`
against the built tree). It needs the physical board to observe a tap in Files
launching the right app and the chooser on glass (tasks 2 and 3).

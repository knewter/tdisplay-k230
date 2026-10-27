## Context

Layer: Nix (the NixOS closure) and userspace desktop entries; no kernel or
shell-client change.

*Grounding: read at cff47b1e. `nix/shell.nix` sets `xdg.mime.enable = true` and
`xdg.mime.defaultApplications` for three text types only, and installs
`pkgs.xdg-utils`. `nix/handheld-desktop-entries.nix` writes the Viewnior entry
with the image MimeType list, and the Portfolio and Nautilus entries each with
`MimeType=inode/directory;`. The Video entry (`videoDesktop` in `nix/shell.nix`)
has no MimeType and `exec = k230-video-session run`. `nix/shell.nix`'s
`mkFilesAppLauncher` comment records that no `xdg-desktop-portal` runs on the
image, and the GTK4 launchers put the handheld entries in `XDG_DATA_DIRS`
(`launcherDataDirs`). No board observation of opening a file from Files exists
in `docs/evidence`.*

## Decisions

- **Defaults in the image, as data.** NixOS renders
  `xdg.mime.defaultApplications` to `/etc/xdg/mimeapps.list`; it is read after
  the user's own file, so a person's choice persists but a fresh home works
  (`openspec/config.yaml`: never rely on restored home state). The list is a
  Nix attribute set, so a type with no installed handler fails the build
  review rather than a tap.
- **Defaults chosen from what is installed.** Images to `viewnior.desktop`, PDF
  (and the other types Zathura's entry declares) to Zathura's entry,
  `inode/directory` to `org.gnome.Nautilus.desktop` (the one drawer "Files"
  entry; Portfolio stays installed but hidden, so it must not win the
  association). Text stays Omawrite. UNVERIFIED: the Zathura desktop ID and its
  MimeType set on this image (`pkgs.zathura` is the default mupdf build); task
  1.1 reads it from the built store path before it is written down.
- **Entries declare only what works.** An upstream entry that claims types the
  image cannot render (Zathura's djvu or postscript without a plugin) is
  overridden in `handheld-desktop-entries.nix`, same pattern as Viewnior. This
  keeps the chooser short.
- **The chooser is GTK's.** Nautilus's "Open With Other Application" is a
  `GtkAppChooserDialog` fed by GIO's association tables. It needs no code here
  and no portal. Its row size comes from the GTK4 stylesheet in
  `gtk-app-chrome-reaches-the-touch-floor`; this change does not set a size,
  and the glass proof depends on that change landing first or being checked
  with it.
- **No xdg-desktop-portal.** GTK4's `GtkFileLauncher` and Nautilus use the portal
  only when sandboxed or when asked (`GTK_USE_PORTAL`). A portal would add
  `xdg-desktop-portal` plus a backend (`-gtk`, which pulls GTK3 and its own
  GSettings and D-Bus activation) as resident or on-demand processes on a
  board with one online CPU, and it needs the session bus, which the shell
  gives only to its notification services. The cost is unmeasured but the benefit
  on this image is nil. Revisit if an app is added that refuses to open files
  without a portal.
- **Video is left alone.** `k230-video-session` plays a bounded profile of one
  playlist; handing it an arbitrary file path changes its memory and CPU
  bounds. Associating `video/*` with a generic player entry would make a tap
  in Files start something unmeasured. See open question 1.

## Rejected

- *A shell-drawn chooser sheet.* One handler per type means nothing to choose
  most of the time, and it would be a second picker beside GTK's.
- *Writing `~/.config/mimeapps.list` at first boot.* It is home state; a
  system file is reproducible and a user override still wins.
- *Leaving defaults to GIO's ranking.* Two apps already claim
  `inode/directory`.

## Risks

- `XDG_CONFIG_DIRS` may not contain `/etc/xdg` in the Sway session; then GIO
  would miss the system list. UNVERIFIED; task 2.1 reads
  `gio mime image/png` inside a running app's environment. If missing, the fix
  is a one-line environment entry beside `XDG_DATA_DIRS` in `nix/shell.nix`.
- Nautilus has no `gvfs`; remote or trash locations are not offered and are out
  of scope.

## Open questions

1. Should a video tapped in Files play? If yes, which player entry and under
   which memory bound; that is a separate proposal measured on the board.
2. Is the GTK chooser at 72 px rows acceptable, or does the operator want the
   shell's 99 px floor enforced for dialogs too?

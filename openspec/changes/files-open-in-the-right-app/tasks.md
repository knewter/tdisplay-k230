## 1. Nix, host

- [ ] 1.1 Read the built Zathura, Viewnior, Nautilus and Portfolio entries for
  their desktop IDs and MimeType sets, then write the defaults (images, PDF,
  `inode/directory`, text) into `xdg.mime.defaultApplications` and correct any
  entry that over-claims in `handheld-desktop-entries.nix`. Proof:
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link`
  (cross-build; a long build, so run it in a build slot), then read
  `etc/xdg/mimeapps.list` in the result. Host build proof only.
- [ ] 1.2 Resolve the associations from the built tree: for `image/png`,
  `application/pdf`, `inode/directory` and `text/plain`, `gio mime <type>`
  with `XDG_DATA_DIRS` and `XDG_CONFIG_DIRS` pointing at the built tree names
  the intended default and lists any other handler. Proof: the transcript saved
  as `docs/evidence/open-with/host/gio-mime.txt`. This runs on the build
  host's GIO, not the board's.
- [ ] 1.3 Proof: `openspec validate files-open-in-the-right-app --strict`.

## 2. Board, injected and console (hardware-only)

- [ ] 2.1 Test-activate the build. In the running shell's environment, read
  `gio mime image/png`, `gio mime application/pdf` and `gio mime
  inode/directory`, and confirm `XDG_CONFIG_DIRS` reaches `/etc/xdg`. Proof:
  `./tools/console.py /dev/ttyACM0 --wait=3 "<cmd>"` transcripts under
  `docs/evidence/open-with/board/`. Operator command: a live
  `switch-to-configuration test` per the board practice in
  `docs/evidence/settings-about/`.
- [ ] 2.2 `xdg-open` a PNG and a PDF from a terminal card. Viewnior and Zathura
  map. Proof: `swaymsg -t get_tree` app ids plus a `grim` capture, injected, in
  the same directory. Measure free memory before and after
  (`/proc/meminfo`), since the viewers are the first things opened this way.
- [ ] 2.3 Inject a tap in Files on a PNG, a PDF and a folder. The right app
  opens; open the chooser from the file menu and confirm the other installed
  handler (if any) is listed. Proof: grim captures from the injector in
  `docs/evidence/open-with/board/`. Injected touch, not glass.

## 3. Glass (physical)

- [ ] 3.1 A person opens a photo and a PDF from Files and switches handler once
  through the chooser, on the real panel. Proof: a timestamped operator report
  tied to the installed build, plus a note on whether the chooser rows are
  comfortable at the GTK4 size; keep open until it exists.

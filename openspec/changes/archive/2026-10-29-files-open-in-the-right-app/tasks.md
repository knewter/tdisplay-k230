## 1. Nix, host

- [x] 1.1 Read the built Zathura, Viewnior, Nautilus and Portfolio entries for
  their desktop IDs and MimeType sets, then write the defaults (images, PDF,
  `inode/directory`, text) into `xdg.mime.defaultApplications` and correct any
  entry that over-claims in `handheld-desktop-entries.nix`. Proof:
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link`
  (cross-build; a long build, so run it in a build slot), then read
  `etc/xdg/mimeapps.list` in the result. Host build proof only.
  Done 2026-10-28 (host build): built `k230-mainline-drm-shell-landscape-hdmi`
  (system `/nix/store/lkkl0z7p60cdwh9cy73zklrrvk6s4rcb-nixos-system-nixos-26.11.20260919.20b1ddd`);
  Zathura's PDF handler is `org.pwmt.zathura-pdf-mupdf.desktop` (the main
  `org.pwmt.zathura.desktop` has no MimeType), and `-cb` also claims
  `inode/directory`. `etc/xdg/mimeapps.list` now defaults images to Viewnior,
  PDF to that Zathura entry, `inode/directory` to Files, text unchanged, and
  removes Portfolio and Zathura-cb from `inode/directory`; the handheld entries
  directory gained a `mimeinfo.cache` (without it Viewnior and Files vanished
  from GIO's registered list).
- [x] 1.2 Resolve the associations from the built tree: for `image/png`,
  `application/pdf`, `inode/directory` and `text/plain`, `gio mime <type>`
  with `XDG_DATA_DIRS` and `XDG_CONFIG_DIRS` pointing at the built tree names
  the intended default and lists any other handler. Proof: the transcript saved
  as `docs/evidence/open-with/host/gio-mime.txt`. This runs on the build
  host's GIO, not the board's.
  Done 2026-10-28 (host build): `tests/gio_mime_built_tree.sh sys-mime`
  transcript saved as `docs/evidence/open-with/host/gio-mime.txt`: PNG ->
  viewnior (Zathura also listed), PDF -> Zathura, folder -> Files only, text ->
  Omawrite. Host GIO 2.88.3, not the board's.
- [x] 1.3 Proof: `openspec validate files-open-in-the-right-app --strict`.
  Done 2026-10-28 (host build): validate --strict passed.

## 2. Board, injected and console (hardware-only)

- [x] 2.1 Test-activate the build. In the running shell's environment, read
  `gio mime image/png`, `gio mime application/pdf` and `gio mime
  inode/directory`, and confirm `XDG_CONFIG_DIRS` reaches `/etc/xdg`. Proof:
  `./tools/console.py /dev/ttyACM0 --wait=3 "<cmd>"` transcripts under
  `docs/evidence/open-with/board/`. Operator command: a live
  `switch-to-configuration test` per the board practice in
  `docs/evidence/settings-about/`.
  Done 2026-10-28 (injected board, SSH not the console): PNG→Viewnior, PDF→Zathura, folder→Files in the session env after two fixes (Zathura override, terminal XDG_DATA_DIRS). `docs/evidence/open-with/board/README.md`.
- [x] 2.2 `xdg-open` a PNG and a PDF from a terminal card. Viewnior and Zathura
  map. Proof: `swaymsg -t get_tree` app ids plus a `grim` capture, injected, in
  the same directory. Measure free memory before and after
  (`/proc/meminfo`), since the viewers are the first things opened this way.
  Done 2026-10-28 (injected): Viewnior and Zathura mapped from `xdg-open` typed in a terminal card; MemAvailable figures in `meminfo.txt`.
- [x] 2.3 Inject a tap in Files on a PNG, a PDF and a folder. The right app
  opens; open the chooser from the file menu and confirm the other installed
  handler (if any) is listed. Proof: grim captures from the injector in
  `docs/evidence/open-with/board/`. Injected touch, not glass.
  Done 2026-10-28 (injected double tap): PNG→Viewnior, PDF→Zathura, folder navigated; the chooser lists Viewnior (default) and Zathura.
- [x] 2.4 Viewnior's rotate buttons draw their icons. Defect seen in
  `docs/evidence/open-with/board/open-png.png`: the two toolbar buttons for
  `object-rotate-left` and `object-rotate-right` were blank. Likely cause (not seen on the board): GTK3 falls
  back to Adwaita, which has no such icons, and the Yaru copies sit in themes
  that fallback never reaches. Fix: `nix/handheld-theme-icons` puts the four
  `object-rotate-*` / `object-flip-*` icons in `hicolor/scalable/actions`, the
  last stop of every theme chain. Host proof: GTK3 icon lookup with Adwaita as
  the theme resolves the names from the built tree. Board proof still open:
  `grim` of Viewnior shows both rotate icons.
  Done 2026-10-28, injected on the board (build `q8k8w3mb…`): a double tap on
  `open-test.png` in Files opened Viewnior, and the native `grim`
  `docs/evidence/open-with/board/viewnior-rotate-icons.png` shows both rotate
  icons drawn.
- [x] 2.5 Files opens as a full card. Reported: Files opened floating, about
  890 px wide. Host reading: the Sway rule `for_window [app_id=".+"] card_shell
  ordinary, floating enable, resize set 100 ppt 100 ppt, move position 0 0`
  already matches `org.gnome.Nautilus`, and 890x550 is Nautilus's own default
  window size (also in its "890 px available" warning in `files-home.png`);
  `files-home.png` shows the card mid-open, and `files-open-with-list.png`
  shows Files filling 1232x568. No rule change was made. Board proof still
  open: after launch, `swaymsg -t get_tree` rect for `org.gnome.Nautilus` over
  10 s, and a `grim` once settled, to tell a slow first layout from a window
  that stays small.
  Board, 2026-10-28 (injected, build `q8k8w3mb…`): it stays small; not a slow
  layout. Opened from the drawer, the container rect is 1232x568 from +6 s
  (`files-rect.txt`), but the visible window is a rounded card about 1232x380,
  centred, with the terminal above and below. It is unchanged 20 s later,
  after a tap inside it, and after `resize set 1232 568`
  (`files-stays-short.png`). `get_tree` reports Nautilus's `geometry` as
  890x550. Viewnior, under the same rule, fills 1232x568
  (`files-viewnior-tree.txt`, `viewnior-rotate-icons.png`), so the rule is not
  at fault. Next: log the xdg_toplevel configure and the size Nautilus commits
  (`WAYLAND_DEBUG=1`) to see whether it refuses the configured height or
  whether the card shell draws it short.
  *Done 2026-10-28, injected, build `37nvncgk…` (docs/evidence/open-with/board/README.md § 2.5): four launches (drawer ×2, `swaymsg exec`, keyboard-first) filled 1232x568. `WAYLAND_DEBUG` shows Nautilus committing the configured size, or 1232x380 (its minimum) when the keyboard has reduced the layout to 272. The earlier short window matches that keyboard-reduced layout; it was not reproduced on this build, so the cause is inferred.*

## 3. Glass (physical)

- [x] 3.1 A person opens a photo and a PDF from Files and switches handler once
  through the chooser, on the real panel. Proof: a timestamped operator report
  tied to the installed build, plus a note on whether the chooser rows are
  comfortable at the GTK4 size; keep open until it exists.
  *Glass, operator report, 2026-10-29T22:23Z, build `ql630glm…`: "it all worked". This covers opening the photo and the PDF and switching handler through Open With…. It does not say separately whether the chooser rows were comfortable (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

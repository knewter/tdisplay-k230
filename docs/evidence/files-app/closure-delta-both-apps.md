# System closure delta: both apps vs. Portfolio-only vs. master

Companion to `closure-delta.md` (read that first for the master-vs-Portfolio
comparison and method). This adds the `k230-coherent-shell-both-files-apps`
configuration (`k230.shell.filesAppNautilus = true`), built with the same
command against that configuration:
`nix build .#nixosConfigurations.k230-coherent-shell-both-files-apps.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.

Store path:
`/nix/store/b2f6yqk428w599jcc7w6rcjawld85bp6-nixos-system-nixos-26.11.20260919.20b1ddd`.

## Result

| | requisite paths | summed size |
| --- | ---: | ---: |
| master baseline | 1041 | 3.196 GiB (3,432,123,872 B) |
| Portfolio-only | 1114 | 3.576 GiB (3,840,008,000 B) |
| Both apps | 1154 | 3.704 GiB (3,976,704,760 B) |
| **Nautilus's marginal delta** (both vs. Portfolio-only) | **+40 net** (54 new, 14 superseded) | **+130.4 MiB (+0.127 GiB, +136,696,760 B)** |
| **Both apps vs. master** | **+113 net** | **+519.4 MiB (+0.507 GiB, +544,580,888 B)** |

## Reading this

Nautilus's own standalone riscv64 closure (`docs/evidence/files-app/`
task 2.3) is 1015.3 MiB -- but almost all of that is gtk4/libadwaita and
GStreamer's default media backend, which Portfolio's own presence in this
system already pays for. What Nautilus adds *on top of* an already-GTK4
system is much smaller in bytes, and is itemized dependency-surface growth
rather than raw size:

- **Device sync**: `libimobiledevice`, `libimobiledevice-glue`,
  `libusbmuxd`, `libplist`, `libtatsu` (iOS-over-USB support Nautilus links
  unconditionally).
- **Network directory sharing**: `gnome-user-share`, `apache-httpd`,
  `apr`/`apr-util`, `mod_dnssd`, `cyrus-sasl`.
- **Search/indexing**: `localsearch` (Nautilus's own search backend,
  distinct from the `tinysparql` library both apps already share).
- **Directory/LDAP/PDF/metadata**: `polkit`, `openldap`, `poppler-glib`,
  `poppler-data`, `libgxps`, `gexiv2`, `exempi`, `libgsf`, `libzip`.
- **Desktop integration**: `libnotify`, `libcloudproviders`,
  `libosinfo`+`osinfo-db`, `gnome-autoar`, `gnome-desktop`, `libproxy`,
  `totem-pl-parser`, `glib-networking`, `nspr`/`nss`, `bubblewrap`,
  `libportal-gtk4`.
- **Nautilus and its image-loader backend themselves**:
  `nautilus-riscv64-unknown-linux-gnu-50.2.2`, `glycin-loaders`,
  `libglycin`, `libglycin-gtk4`, and `k230-nautilus` (this change's
  launcher wrapper).

None of this is started as a running service by this change (no systemd
user unit wiring for gvfs/tracker/localsearch/gnome-user-share) -- see
`proposal.md`'s non-goals. Nautilus falls back to plain directory reads
without them; whether that is fast enough on this board's single in-order
core over a large directory is the coordinator's own scroll/large-directory
task (`tasks.md` 5.3), not measured here.

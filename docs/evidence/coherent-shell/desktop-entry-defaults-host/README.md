# Coherent shell desktop-entry defaults: host and target-package checks

Source: `787e7ae1` (`nix/handheld-desktop-entries.nix`, `nix/shell.nix`). This is a declarative override of existing desktop IDs for the coherent shell session. The Rust catalog still discovers applications through GIO and applies `should_show`; no name-based launcher filter was added.

The exact target wrapper build completed with:

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.k230.shell.rustFrontend \
  --no-link --print-out-paths --max-jobs 1 --cores 4
```

Output: `/nix/store/hnv1qbqji99b1vs1qf0kj7kkm5iv50cy-k230-shell-rust`. Its desktop-entry bundle is `/nix/store/r1wrac827m0g8fnyrvz72gm43h7p9rs7-k230-handheld-desktop-entries` (derivation `/nix/store/i6fd1rqwf6wz4xvrchc5y1i3kkda04jw-k230-handheld-desktop-entries.drv`). All five packaged files passed `desktop-file-validate` without diagnostics.

The checked-in host GIO probe was compiled and run with the bundle first in `XDG_DATA_DIRS`, followed by the exact Foot, htop, and nnn package share roots:

```sh
gcc -Wall -Wextra -Werror tests/handheld_desktop_entries_probe.c \
  -o /tmp/k230-handheld-desktop-entries-probe \
  $(pkg-config --cflags --libs gio-unix-2.0)
XDG_DATA_HOME=/tmp/k230-desktop-empty \
XDG_DATA_DIRS=/nix/store/r1wrac827m0g8fnyrvz72gm43h7p9rs7-k230-handheld-desktop-entries/share:/nix/store/kv21hqgv043bmdfi5i1f791n9x7crwgg-foot-riscv64-unknown-linux-gnu-1.28.0/share:/nix/store/nyy80gvhfcalcm8g9x3fcx3bgilllj3g-htop-riscv64-unknown-linux-gnu-3.5.3/share:/nix/store/x4lhz9qljs7159byrzjffzhaa8p2sxc0-nnn-riscv64-unknown-linux-gnu-5.3/share \
  /tmp/k230-handheld-desktop-entries-probe
```

Result:

```text
foot.desktop name=Terminal shown=1 icon=foot
htop.desktop name=Monitor shown=1 icon=htop
nnn.desktop name=Files shown=1 icon=folder
footclient.desktop name=Foot Client shown=0 icon=foot
foot-server.desktop name=Foot Server shown=0 icon=foot
```

The probe also checks that `g_app_info_get_all()` yields exactly one visible entry for each of the first three IDs and zero visible helper entries. The `folder` icon was confirmed present in the pinned Yaru-purple and Yaru-blue icon trees. Friendly names and helper hiding rely on standard desktop-entry precedence and `NoDisplay`; they do not change the upstream package desktop IDs. This is host GIO and cross-built package evidence. Actual drawer contents, icon appearance, launch, and touch on the panel still require installed-system observation.

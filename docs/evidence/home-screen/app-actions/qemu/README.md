# Home app actions: paired RISC-V compositor and Rust proof

2026-10-01: all ten checks passed with source
`288535289172c8465c4fa408eaa8ba2c7ab8a5ac`.
[result.json](result.json) records exact store identities and image hashes.

- [Right-click menu](home-actions-right-click.png): declared New Window,
  current window, named Preferences action, Remove from Home and rearranging.
- [Touch hold](home-actions-touch-grab.png): lifted icon in rearrange mode,
  with no menu opened by holding.
- [Placement](home-actions-touch-placement.png): Badge moved to chosen cell 2,
  and Extra dragged from All apps into Home cell 3.

The real Sway and Rust RISC-V binaries run under `qemu-riscv64-static` with a
headless backend, a real virtual-pointer protocol device and injected touchscreen
events through Sway's input-manager path. Native synthetic app clients carry
stable container identities. Primary taps focus an existing most-recent window;
explicit New Window creates a second distinct container; a menu row can select
the older window. Named desktop actions execute their fixture marker, single-window
metadata suppresses New Window, and outside/secondary dismissal preserves both
layout and windows. Long-press grab and drawer-to-Home placement remain intact.

```sh
python3 tests/rust_home_screen_qemu.py --actions-only \
  --sway /nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --swaymsg /nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/swaymsg \
  --rust /nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --theme-bundle /nix/store/lv1rpkgv05ri76zz828xygiz0vggcch8-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --client "$NATIVE_PROBE_CLIENT" --output "$EVIDENCE_OUTPUT"
```

`NATIVE_PROBE_CLIENT` is the previously built card-composition-probe-client from
`nix/card-composition-probe-client/card-composition-probe-client.c`; output is a fresh directory. Both variables
are operator-selected harmless paths. The fixture must advertise a pointer device;
cursor IPC alone never gives the Rust client a pointer seat capability. It uses
production `focus_follows_mouse no`, installed single-window metadata and distinct
100-ms click phases. A Wayland roundtrip acknowledges the compositor, not the
emulated client's event loop. Earlier back-to-back phases intermittently missed
routing; the final fixture allows separate dispatch turns. Touch holds are one
second to exceed the unchanged gesture threshold under emulation. No timing or
physical usability claim is made from this run.

Images were reviewed. The fixture Terminal icon falls back to its initial because
its Foot icon is absent from the fixture lookup; this is synthetic desktop content.
The whole Home proposal remains open for its original physical layout gate and
operator app-menu acceptance on a recoverably installed candidate.

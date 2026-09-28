# Power key host checks

`power-sheet-host.png` is a **host-rendered Rust shell fixture**, generated
from the themed renderer at 568×1232. It is not a camera or board capture.

Command (2026-09-27 America/Chicago):

```sh
K230_VISUAL_FIXTURE_DIR=/tmp/k230-power-visual cargo test \
  --manifest-path nix/rust-shell-client/Cargo.toml --lib \
  themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles -- --nocapture
```

The fixture test passed and produced `power.png`, copied here as
`power-sheet-host.png`. The sheet has separate Restart, Power off and Cancel
targets. The destructive targets issue a request for a second confirmation;
they do not execute a system power command on their first tap.

`nix build .#deviceTree` produced
`/nix/store/hh5qj43fd6lvv5phva61v5mvhcicqbyz-k230-tdisplay.dtb`.
`nix build .#kernel --max-jobs 2 --cores 12 --option substituters
https://cache.nixos.org/` produced
`/nix/store/p6z5nsr2dyb1kfjk1hkzh9vb2nha0ka6-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`.
The candidate kernel configuration contains
`CONFIG_INPUT_K230_PMU_PWRKEY=y` in the built Nix kernel-config output.
This checks DT construction and Kconfig selection, not physical key input.

`python3 tests/test_power_keyd.py` passed ten host tests covering press
timing, held-key deduplication, disconnect, waking before opening the sheet,
and refused display commands. `cargo test --manifest-path
nix/rust-shell-client/Cargo.toml --lib --bin k230-shell-rust` passed 240
library and 22 binary tests, including the power-sheet confirmation hit test.
`nix build .#power-keyd` produced
`/nix/store/lai8gf1awj7732402jxlj5lgmrwaasjz-k230-power-keyd` and
`nix build .#handheld-shell-rust` produced
`/nix/store/dwik36s7lfrj1g5m9yq04j9jzqdkxprf-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
`python3 tests/test_device_settings.py` passed nine backend tests covering
request-before-confirm, cancel, denial, expiry and the action allowlist.
The unrestricted Cargo integration-test command currently fails in an
unrelated pre-existing `theme_catalog_module` import of `runtime_trace`.

**UNVERIFIED:** The operator's physical switch has not yet been identified
as PMU INT0 versus a hardware RESET switch. No press/release, display
off/on, long-hold sheet, reboot or power-off result has been observed on
the board with this change. The candidate kernel and service remain behind
the physical proof tasks in the OpenSpec change.

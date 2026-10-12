# Backgrounds load with no saved theme choice, 2026-10-12

Tasks 19.1 and 19.2 of change `the-shell-swaps-themes-without-a-python-stall`.

The source is master `1cc7ebe1`, in worktree `/home/jadams/tmp/k230-bg-fix`,
branch `fix/backgrounds-without-saved-theme`. Times are UTC.

Evidence classes:

- coherent-installer serial checks;
- one software-injected tap over SSH;
- one native `grim` capture.

No finger or camera observation is claimed.

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/8h1986l9ywg5g73mjjssm5zgg9iy6xcs-k230-coherent-shell-boot-files` |
| System | `/nix/store/cwfx0amrcgxb0ni7pdpq2ij4rr8yz7bh-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/k2z9z61khs97ks3m2sm2ymhrisk13h5m-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Kernel, `Image`, `initrd.uimg` | unchanged from the baseline |
| Baseline | combined install `zvxmd93g…` ([../combined-install-2026-10-12/](../combined-install-2026-10-12/README.md)) |

## Install

The build ran with
`flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/bg-fix-2026-10-12/candidate --print-out-paths --max-jobs 1 --cores 4`
and exited 0.

The coherent installer then ran with the same recipes as the combined
install. Only the paths and the baseline differ (see the `*-used.py` files).
Every step passed:

1. **Preflight:** boot `9de0e538-…`, 07:43:53 ([preflight.json](preflight.json)).
2. **Stage:** ([stage.log](stage.log), [transfer.json](transfer.json),
   [staged-state.json](staged-state.json), [host-inspection.json](host-inspection.json)).
3. **Candidate boot:** ([candidate-boot.json](candidate-boot.json)). The
   runtime check ran on boot `8909583b-…` at 07:49:36
   ([candidate-runtime.json](candidate-runtime.json)).
4. **Qualification:** ([deployment-authorization.json](deployment-authorization.json)).
5. **Install and ordinary autoboot:** ([ordinary-boot.json](ordinary-boot.json)).
   The runtime check ran on boot `a563b9fb-…` at 07:52:48
   ([ordinary-runtime.json](ordinary-runtime.json)). The current system and
   profile are both `cwfx0amr…`, and the four shell services are active.

## Task 19.2 check

[open-themes-used.py](open-themes-used.py) ran as root over SSH, on the
ordinary boot `a563b9fb-…`. It performs these steps:

1. Starts a temporary virtual `K230 injected touchscreen` (`evemu-device`).
2. Runs `k230-shell-rust --surface settings` as `shell`.
3. Taps Themes at (480, 130).
4. Waits 15 s.
5. Runs `grim -s 0.5`.
6. Prints `k230-theme list`'s `active` field.
7. Stops the device unit.

Results:

- **Saved choice:** `k230-theme list` printed `"active": {"generation": null, "id": null}`,
  so the board still has no durable theme choice.
- **Picker:** [themes-without-saved-choice-native.png](themes-without-saved-choice-native.png).
  The theme carousel is centred on `catppuccin`, labelled "Built in" rather
  than "Current theme".
- **Backgrounds row:** it shows Totoro, labelled "Current background on
  Home", with neighbours to the right, instead of "Loading backgrounds".

Before the fix, the same state left the row on "Loading backgrounds". The
board-session agent reproduced that twice
([../board-session-2026-10-12/README.md](../board-session-2026-10-12/README.md)).

This is one opening. The tap was software-injected, and no glass or finger
view was taken.

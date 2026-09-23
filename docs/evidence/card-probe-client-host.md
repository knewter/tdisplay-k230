# Card probe client and session harness: host evidence

Recorded 2026-09-23T06:17Z, worktree `k230-card-probe-client`, branch
`impl/card-probe-client`, base `08ce5c919598edfb89df8720a77610fd4c4d5d68`.
This evidence covers the synthetic Wayland client and mocked service ownership.
Board execution, real touch, visible card content, keyboard return and restored
normal Apps/terminal behavior remain **UNVERIFIED**. No board or UART was opened.

## Source and build

`nix/card-composition-probe-client/card-composition-probe-client.c` is compiled
from this repository with the flake's pinned Wayland and generated XDG-shell
protocol code. It accepts only `k230.card.one` and `k230.card.two`, uses
XRGB8888 SHM buffers, and animates the parent and desynchronized child solely
from their separate `wl_surface.frame` callbacks. Released buffers are reused;
unreleased buffers are never overwritten. Resizing retires released buffers
before allocating new dimensions. Three buffers per surface bound allocation.

The top row is a moving-frame counter, and the second row shows a green binary
key-press count. Logs contain counts, never key codes or text. `--refuse-close`
logs the actual XDG close callback and keeps the client mapped. A 1-second
watchdog logs callback age even when a hidden surface receives no callbacks.
The default lifetime is 120 seconds, the maximum 600 seconds. JSON records are
bounded to 10,000 and distinguish callbacks from unmeasured presentation.

Commands (both exit 0; run with the reserved build slot):

```sh
nix build --impure --no-link --print-out-paths --max-jobs 1 --cores 8 --expr \
  'let f = builtins.getFlake (toString ./.); p = f.inputs.nixpkgs.legacyPackages.x86_64-linux; in p.pkgsCross.riscv64.callPackage ./nix/card-composition-probe-client {}'
nix build --impure --no-link --print-out-paths --max-jobs 1 --cores 8 --expr \
  'let f = builtins.getFlake (toString ./.); p = f.inputs.nixpkgs.legacyPackages.x86_64-linux; in p.callPackage ./nix/card-composition-probe-client {}'
```

Outputs:

- RISC-V: `/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1`
- Native: `/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1`

An initial cross-build found that the cross pkg-config executable must be invoked
through `$PKG_CONFIG`; this was corrected before both successful builds.

## Actual host protocol check

```sh
python3 tests/test_card_probe_client.py \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --sway /nix/store/jh2y4bkbdd6a0dkpw6ryz0j8cgy6hg7k-sway-unwrapped-1.12/bin/sway
```

Result:

```text
PASS actual XDG configure, SHM release, independent child callbacks, close acceptance/refusal, hidden starvation and return, disconnect
```

This launches real native Sway with `WLR_BACKENDS=headless` and
`WLR_RENDERER=pixman`, then two compiled clients. It checks parent and child
callback/commit/release progress, sends an actual XDG close request through Sway
IPC to each client, verifies the refusing client keeps animating, hides that
client on another workspace, observes callback age above 1 second for both
surfaces, and verifies resumed progress on return. Finally it checks compositor
disconnection reports an error. These are protocol and host rendering checks;
no touch or keyboard event is synthesized by this test, and no physical
presentation is established.

## Harness checks and operator use

```sh
python3 tests/test_card_board_session.py
shellcheck tools/card-composition-board-session.sh
python3 tools/blob-scan.py --no-vendor
```

The fault tests check normal shell stop before probe start, probe cgroup stop
before shell restoration, failure propagation, restoration failure, refusal to
start beside another Sway, operator lock exclusion, the explicit restoration
argument, missing seatd, and SIGTERM cleanup. Collection excludes arbitrary
journal text, unknown compositor events and unapproved fields. Resource samples
are cgroup CPU nanoseconds and current bytes, not a derived CPU percentage.
`--verify-restored` checks service state only; real Apps/keyboard/terminal proof
must be recorded separately by the operator. No task checkbox is completed by
these host checks.

The package coordinator must make `bin/card-composition-probe-client` available
beside `bin/card-composition-probe` (or set `K230_CARD_CLIENT` to its absolute
path). The wrapper must accept `--sway --config FILE` and execute the opt-in
patched Sway. The following runs **on the reserved board**, with root owning
service transitions:

```sh
K230_CARD_DURATION=120 tools/card-composition-board-session.sh \
  --probe /nix/store/PROBE/bin/card-composition-probe --restore-shell
tools/card-composition-board-session.sh --collect > card-session-evidence.txt
tools/card-composition-board-session.sh --verify-restored
```

Optionally set `K230_CARD_KEYBOARD` to an absolute keyboard executable before the
probe to exercise keyboard focus. The normal shell must already be active.
The harness serializes operator actions with `flock`, stops `shell`, checks its
MainPID and for any remaining Sway, and synchronously starts a transient systemd
unit with `Conflicts=shell.service`, `After=shell.service`, `Type=exec` and
`KillMode=control-group`. Thus an interrupt cannot race an unstarted background
service into the restored shell. The unit has a bounded lifetime. Cleanup stops
the complete probe cgroup before starting and checking normal shell and seatd;
restoration errors remain errors. An independently detected competing Sway is
left alone and blocks both startup and unsafe restoration.

Session state is in `/run/k230-card-composition`, outside the normal shell's
runtime directory. `--collect` selects the exact transient invocation's bounded
journal and outputs only approved `K230_CARD` telemetry plus client JSON counts.
Logs explicitly leave physical touch and normal-shell app usability unverified.
`--restore-shell` is available for explicit recovery after an operator confirms
ownership. Never run two board operators or open a second UART reader.

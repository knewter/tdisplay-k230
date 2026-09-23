# Booted QEMU card-shell smoke

`tools/qemu-k230.sh --card-shell-smoke` runs the selected `k230-qemu`
configuration under **system-mode** RISC-V QEMU and drives its guest serial
console. It does not substitute the existing host/user-mode compositor suite.
The ordinary tool invocation still boots its existing console image unchanged.

The selected image must contain the `card-shell-smoke` service and
`card-shell-guest-smoke` executable. Absent integration is an error before
building, not a skipped/passing test. The current default QEMU image has no card
shell integration, and task 5.1 therefore remains open.

An explicit fixture validates the tooling before default image integration:

```sh
tools/qemu-k230.sh --card-shell-smoke --fixture-image \
  --output /tmp/card-guest-smoke --timeout 900
```

This extends only the QEMU configuration with `nix/qemu-card-shell-smoke.nix`,
which packages the source-built card compositor, real SHM/XDG fixture client,
virtual keyboard helper and guest verifier. It creates an unprivileged
headless Pixman service with a 568x1232 logical output. It does not edit or
activate the normal shell service, modify the board configuration, or access
UART hardware. Builds use one Nix job and eight cores; reserve the build slot.
The first run may need the pinned mainline QEMU kernel and netboot closure.

Use `--no-build` to require existing evaluated artifacts. `--output` must be new
or empty; omitted output creates a temporary evidence directory. The deadline
bounds the guest run after artifact realization, not compilation. `MEM` defaults
to 6G because the guest holds its whole closure in a ramdisk; this is not a
statement about the board's memory requirements.

The guest must demonstrate two mapped applications with progressing root and
desynchronized-subsurface callbacks in the deck, drag/expand, actual synthetic
keyboard delivery after focus return, actual XDG close refusal followed by
bounded recovery, graceful close, and cancel/Back recovery. The supervisor
restarts the service and repeats those checks, then stops the service. It
requires two fresh run-token reports, a successful guest teardown status,
matching system closure identity, and a changed compositor PID. A boot prompt,
echoed command, stale result, missing check, timeout or unsupported compositor
cannot satisfy the result parser.

The evidence directory retains `manifest.json`, bounded `serial.log`, and
`result.json` only on successful completion. The manifest distinguishes an
explicit fixture image from the selected/default QEMU image. The guest report
identifies its actual kernel, system store path, compositor executable/PID and
unprivileged UID. Inspect and sanitize raw transcripts before committing them.

Narrow tooling checks:

```sh
python3 tests/test_qemu_card_shell_smoke.py
bash -n tools/qemu-k230.sh
```

The protocol tests are host tests, not proof of a guest boot. Record the actual
system-QEMU invocation and its output separately before claiming guest success.

## Remaining integration gate

A fixture pass completes only the smoke tooling portion of card task 5.1. After
its required board budgets pass, the coordinator still owns selection of the
reviewed component in the real system/QEMU configurations, a successful
`nix build .#nixosConfigurations.k230.config.system.build.toplevel`, and the
non-fixture `tools/qemu-k230.sh --card-shell-smoke` run. Keep task 5.1 unchecked
until those requirements are met. QEMU does not prove the K230 board boot chain,
RGB565 panel scanout, real touch, optical latency, power or performance budgets.

## Source checkpoint status

The coordinator continued the stopped agent snapshot in
`test/card-qemu-local-continuation` from `f660ada`. Six host protocol tests passed.
The default selected-image invocation correctly rejected missing integration;
fixture `--no-build` correctly rejected unrealized artifacts. The full explicit
fixture build was still compiling its pinned Linux 6.18.52 kernel when this
checkpoint was committed. No completed guest run is claimed.

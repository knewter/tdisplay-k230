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


## First completed boot attempt and console repair

The initial full build completed, but the guest verifier timed out at
2026-09-23 19:30:25 UTC without any runtime report. The guest started its card
fixture and reached userspace; its `/dev/ttyS0` device unit never activated,
so serial-getty did not provide a login. The kernel has 8250 console and OF
serial support built in; the precise device-unit cause remains unverified.
[The failed attempt](../evidence/card-shell/qemu-fixture/console-timeout/observations.json)
retains selected observations, original transcript hash and exact image
artifact identities. It is not a card interaction pass.

The explicit fixture now enables the standard `console-getty` on the existing
kernel console and masks `serial-getty@ttyS0`. The supervisor also flushes its
bounded transcript as it runs, so a stalled guest can be inspected before its
deadline. Six host protocol checks still pass. A fresh actual guest retry is
required; neither the console change nor host parsing tests prove that retry.


The console retry reached an automatic login and failed explicitly with
`runuser: may not be used by non-root users`; service teardown returned 71.
[Its observations](../evidence/card-shell/qemu-fixture/supervisor-login/observations.json)
preserve that failure. The installation-device profile selects `nixos`,
overriding the board's default root login. The fixture now explicitly selects
root for its supervisor; the compositor and all test clients still use the
separate unprivileged `card-smoke` account. Pinned Sway's `sway/server.c`
explicitly avoids `wayland-0` and selects from `wayland-1` onward; the isolated
fixture verifier now targets its first socket, `wayland-1`.


The next live guest produced two complete runtime reports with different
compositor PIDs and a zero teardown status, but the host rejected the first
report because the interactive shell prefixed it with `ESC[?2004l` (bracketed
paste disable). The [original prefix observation](../evidence/card-shell/qemu-fixture/report-prefix/observations.json)
records both reports and the failed host status. The parser now removes only
known leading bracketed-paste mode toggles; it still rejects markers embedded
in command echoes or arbitrary prefixes. Seven host tests pass, including that
captured failure pattern. Those protocol checks now run in CI too. A fresh
system guest run, not retrospective relabeling of the failed command, supplies
the final verifier result.

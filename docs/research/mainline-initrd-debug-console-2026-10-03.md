# Observe ordinary initrd coldplug without stage2 login

Evidence class: read-only host inspection of the exact archived initrd and
official systemd v261.2 source. No implementation, build, board or UART action.
This is a proposed bounded diagnostic within mainline task 5b.5; its readiness,
coldplug observations and recovery remain **UNVERIFIED** on the board.

Worktree `/home/jadams/tmp/k230-mainline-initrd-debug-console`, branch
`audit/mainline-initrd-debug-console`, base
`01dcca4601428b0872a11b3a54417bd70a9f0f35`. Own only this note; no board/build
reservation. Cached `python3 tools/work-status.py` start/handoff commands run
at idle priority.

## Exact artifacts and recommended comparison

Use the same bundle
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`,
system `9gdmsrh2igqla1qz0ll97czfw2x42icw-nixos-system-nixos-26.11.20260919.20b1ddd`,
kernel `9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
The exact compressed initrd remains SHA-256
`046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`.
Require the separately reviewed single-partition blkid trial's returned success
and protected normal return before this next comparison. The previous ordinary
failure and verified operator recovery are in the [physical packet](../evidence/mainline-system-trial/physical-2026-10-03/README.md).

Retain the complete bundle arguments, sole selected `init=`, both consoles and
the three qualified controls from the [ordinary-init plan](mainline-init-touch-gates-2026-10-02.md).
Append exactly:

```text
rd.systemd.unit=basic.target rd.systemd.debug_shell=ttyS0
```

Use only the existing volatile U-Boot argument path with exact printed-argument
comparison. No `rdinit`, clock-ignore, persistent environment/profile change or
new kernel/initrd build is required by the inspected artifacts. This keeps
ordinary systemd as PID1, runs its early coldplug transaction, and selects a
target before the root activation chain. It is a qualified initrd diagnostic,
not ordinary-root acceptance or a fix for the prior timeout.

## Why these controls are supported

A read-only `zstd -dc`/newc walk confirmed the debug generator, debug-shell unit,
`/bin/sh`, `systemctl`, `journalctl`, `timeout`, `readlink` and `udevadm` are
archived. Units resolve to systemd
`srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2`'s
`example/systemd/system` directory. Its recorded source store path is absent
locally; implementation semantics below use official v261.2 tagged source,
while actual compiled unit substitutions were checked in the archive.

- [PID1 selection, core/main.c:299–307](https://github.com/systemd/systemd/blob/v261.2/src/core/main.c#L299-L307)
  accepts `rd.systemd.unit` in the initrd. The
  [debug generator:170–191,230–278,372–394](https://github.com/systemd/systemd/blob/v261.2/src/debug-generator/debug-generator.c#L170-L191)
  parses initrd-prefixed options, adds the shell to the selected target's Wants,
  and generates its `TTYPath=/dev/ttyS0` override, clearing the default tty9
  existence condition. `rd.systemd.default_debug_tty=ttyS0` alone does not enable
  the shell; the recommended single shell option supplies both choices.
- Archived `debug-shell.service` uses `/bin/sh`, `DefaultDependencies=no`,
  `StandardInput=tty`, `TTYReset=yes`, `TTYVHangup=yes` and `Restart=always`.
  It does not wait for sysinit/coldplug completion. Inheritable tty input preserves
  stdout inheritance in [service.c:1033–1055](https://github.com/systemd/systemd/blob/v261.2/src/core/service.c#L1033-L1055),
  so this unit is an interactive terminal shell, not merely journal output.
- Archived `basic.target` requires sysinit. Its sysinit Wants contain
  `systemd-udev-trigger.service` and `systemd-udevd.service`. Archived
  `initrd.target` separately wants the root/device/filesystem targets and requires
  closure lookup; switch-root requires NixOS activation. These root requirements
  are not attached to basic.target in this archive. The
  [fstab generator:994–1025](https://github.com/systemd/systemd/blob/v261.2/src/fstab-generator/fstab-generator.c#L994-L1025)
  connects `/sysroot` to `initrd-root-fs.target`, rather than `local-fs.target`.
  This static graph supports the proposed boundary; still require a live check
  that `/sysroot` is unmounted before accepting any diagnostic state.

Archived debug-shell unit SHA-256:
`edc8fe166b94d3c9e76879662780679b6092944f88e9966a27a41f0aa2767a81`;
basic target `7d97dda25769ba30dff93d7aa2818151d968c843281767b720b3eabf09563f0b`;
sysinit target `4d7fdd6b1a2f15647d69d886519c7809ed3adc493e8bd5bb3f88d360dda965eb`.

## Console conflicts and readiness gates

The bundle includes `console=ttyS0,115200n8`. Debug-shell deliberately owns that
same reserved UART; ordinary kernel/status output can still interleave. Its
terminal reset restores software termios flags and flushes pending input;
[terminal-util.c:906–975](https://github.com/systemd/systemd/blob/v261.2/src/basic/terminal-util.c#L906-L975)
does not change the baud selection. This is source behavior, not a physical
serial-readiness proof. Send no input during boot/terminal reset. Require a fresh
candidate boot banner, expected early-shell startup and a completed primary
shell prompt; reject continuation prompts, stale echoes and truncated frames.

Do not combine this with `rd.systemd.break=pre-udev`, `pre-mount` or
`pre-switch-root`: the archived breakpoint shells use `StandardInput=tty-force`
on the default console and can compete for the same UART. Pre-mount also waits
after basic, so it may never arrive if coldplug is the stopping point.
Debug-shell alone, without the basic target selection, could continue through
root activation/switch-root. Do not enable a second getty, exit the shell
(Restart=always), start/isolate initrd.target, or run prepare-root manually.
Emergency/password-console units are further possible contenders; their
activation is a failed comparison, not permission to answer a guessed prompt.

Before observations, a new controller must obtain a fresh nonce receipt and
independently verify: UID0; fresh private boot ID; expected kernel release;
`/proc/1/exe` resolves to the archived systemd binary; `/etc/initrd-release`
exists; the interactive shell PID equals debug-shell's live `ExecMainPID` and
has PPID1; debug-shell is running with `TTYPath=/dev/ttyS0`; exact sole selected
`init=` and exactly the two diagnostic tokens with no `rdinit`/clock-ignore;
proc/sysfs/cgroup mounts are present; no `/sysroot` mount; root activation and
switch-root units are inactive and have no pending jobs. Recheck boot identity
and this boundary before recovery. Stage2 `/run/booted-system` and selected
root-profile checks cannot replace these guards because root is not activated.

## One bounded snapshot sequence

The following are exact helper paths/arguments, to be individually fresh-framed
by a reviewed controller. Redirect detailed output into a proven unique private
volatile initramfs directory; print only fixed RC/guard/state summaries. Retain
raw logs privately. The initrd bin environment supplies the absolute paths;
candidate Python and `ps` are not required.

```sh
/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager --plain --no-legend list-jobs
/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager show systemd-udev-trigger.service systemd-udevd.service basic.target sysinit.target --property=Id,ActiveState,SubState,Result,ExecMainPID,ControlPID,ExecMainStatus,ControlGroup
/bin/timeout --signal=TERM --kill-after=2s 5s /bin/udevadm control --ping --timeout=3
/bin/timeout --signal=TERM --kill-after=2s 5s /bin/journalctl --no-pager --boot --lines=80 --output=short-monotonic --unit=systemd-udev-trigger.service --unit=systemd-udevd.service
```

For at most 16 PIDs obtained from the two verified udev units' cgroups, read only
those cgroups' `cgroup.procs` and those PIDs' `/proc/<pid>/comm`, `status` and
`wchan`, validating numeric IDs and membership immediately. Keep only name,
state and wait-symbol fields; account for process disappearance. This can
identify a live trigger/worker and a sleeping or uninterruptible wait without
dumping command lines, addresses, environments or every process. A zero/unavailable
wchan is inconclusive. Do not read arbitrary registers or `/proc/interrupts`.
The tagged manager creates workers named `(udev-worker)` at
[udev-manager.c:523](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-manager.c#L523).
The [control parser:135–154](https://github.com/systemd/systemd/blob/v261.2/src/udev/udevadm-control.c#L135-L154)
supports ping/timeout. Ping proves daemon responsiveness only; it is not settle
and does not prove that queued device processing completed.

Choose one overall observation deadline, e.g. 90 seconds from shell readiness,
and a ten-second host marker deadline for each five-second child. Missing final
markers, broken identity or terminal ownership, duplicate/truncated receipts or
a blocked child mean unknown: no retries, Ctrl-C, follow-up snapshots or reboot
input. TERM/KILL cannot guarantee return from a kernel D-state wait. Preserve
evidence and require the proven operator-reset/protected-normal procedure.
Known complete nonzero commands are diagnostic failures, not proof of a driver
cause; end the sequence and recover only through a separately acknowledged
healthy protocol.

With every guard still proven and `/sysroot` unmounted, one fresh acknowledged
`/bin/reboot -ff` uses the existing direct kernel-reboot path rather than starting
a potentially blocked unit-stop transaction. This systemd-PID1 diagnostic's
automatic return is still unproved: require kernel restart, SPL, new protected
normal boot ID, exact profile/kernel/services and all eight hashes. Never claim
the host deadline itself guarantees recovery.

## Supported logging alternative, separate comparison

Prefer quiet boot plus the bounded journal snapshot above. If shell readiness
fails, these supported initrd-only logging tokens are a separately qualified
passive alternative: `rd.udev.log_level=debug`,
`rd.systemd.log_level=debug rd.systemd.log_target=console`, and
`rd.systemd.journald.forward_to_console=1 rd.systemd.journald.max_level_console=debug`.
The [udev parser:62–80](https://github.com/systemd/systemd/blob/v261.2/src/udev/udev-config.c#L62-L80),
[common log parser:1288–1303](https://github.com/systemd/systemd/blob/v261.2/src/basic/log.c#L1288-L1303)
and [journal parser:206–231](https://github.com/systemd/systemd/blob/v261.2/src/journal/journald-config.c#L206-L231)
support those choices. Journal forwarding defaults to `/dev/console`; it can
perturb timing and flood/interleave UART output. It is not the first quiet-shell
proposal. `rd.udev.log_target=console` remains unsupported. Worker-count and
event-timeout controls would change execution behavior and are not part of this
first state observation.

Host validation: `openspec validate the-board-runs-a-mainline-kernel --strict`
and staged `git diff --check`. Implementation needs meaningful host tests for
exact argument selection, initrd versus stage2/PID1-shell guards, terminal/PID
ownership, snapshot bounds/private output, stale/interleaved/truncated receipts
and zero further input after unknown. Physical proof and 5b.5 remain open.

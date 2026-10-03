# Autonomous UART observer: source/native host preparation

Evidence class: native host compilation/tests and offline Nix evaluation.
Worktree `/home/jadams/tmp/k230-mainline-uart-observer`, branch
`mainline-uart-observer`, base `9854479615d2800d53e79cf14939397a93e3fe1f`.
No board/UART or cross-build reservation. Root owns matching cross-build and
physical use; ordinary root/touch task 5b.5 remains open. Matching RISC-V helper,
archived artifact inspection, UART observation and protected automatic return
remain **UNVERIFIED** by this host work.

The fixed [protocol](uart-observer-protocol-2026-10-03.md) landed separately for
parallel controller work. The source plan is
[the terminal/RX audit](../../research/mainline-debug-tty-rx-2026-10-03.md).
This implementation adds one separately named initrd configuration/package/
boot bundle, using the existing optional DRM kernel and DT source. It changes
no existing controller, kernel, default system/image, protected card file or
profile. Its debug-shell drop-in retains upstream TTY policy but replaces
ExecStart with the helper and disables restart to prevent an unbounded retry.

The helper checks exact volatile nonce/from/init, sole immutable init, five
qualified controls and absence of other rd./systemd./udev./fsck controls. It
checks systemd PID1, fresh boot, kernel, main-process root UID/PPID1/executable,
actual ttyS0 descriptor, initrd marker, volatile mounts, no sysroot, live unit
ownership and all five inactive/no-job root-chain units. Queries use bounded
child groups and /dev/null stdin/stderr, preventing receipt consumption.
Initial and renewed guard/getter children have absolute monotonic deadlines;
clock failure also stops unknown. A blocked kernel syscall cannot be made
recoverable by these userspace bounds.

After initial guards/snapshot it forks the observer and execs the original shell
in the main PID. The observer never reads, opens, flushes or configures the TTY.
It snapshots termios, line discipline, cached RX/error counters and cached
Linux IRQ plus only that IRQ's aggregate table count; verified UART ancestry
bounds the optional runtime-PM read. Missing optional IRQ/status is explicit,
not a fabricated zero measurement. Snapshot IO is isolated in bounded children.

Fresh length/CRC32/nonce/sequence records go to /dev/kmsg as KERN_INFO with an
explicit preceding newline. The bounded payload is at most 384 bytes and whole
record below 900; overlimit/partial write is failure, never truncated success.
This uses the kernel-console output path discussed in the audit, avoiding a
required TTY buffered write. Output accepted by the kernel is not proof of
host reception or of kernel progress.

After 12s, the observer emits its after snapshot without needing inbound input,
renews all guards and emits one return acknowledgement before an attempted
`/bin/reboot -ff`. Reboot stdio is /dev/null, so it cannot consume the receipt or
depend on buffered TTY output. Missing host receipt is separately a diagnostic
failure even if autonomous snapshots and protected return complete. Unknown
child/output/guard stops without a reboot; acknowledgement is not hardware
restart proof. No unconditional timer, kernel/clock workaround, root mount,
root activation or trace instrumentation was added.

## Commands and results

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror \
  -o "$HOME/tmp/k230-uart-observer-native" nix/mainline-uart-observer/observer.c
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s tests -p test_mainline_uart_observer.py -v
nix-instantiate --parse flake.nix > /dev/null
nix-instantiate --parse nix/mainline-uart-observer/module.nix > /dev/null
nix-instantiate --parse nix/mainline-uart-observer/bundle.nix > /dev/null
nix eval --offline --raw \
  '.#nixosConfigurations.k230-mainline-uart-observer.config.boot.initrd.systemd.units."debug-shell.service".text'
nix eval --offline --raw .#packages.x86_64-linux.kernelMainlineUartObserverBootFiles.drvPath
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

Native compilation passed with warnings as errors. The 18 tests passed in 4.765s:
actual native parsers reject wrong/duplicate/missing identities, unsafe controls,
wrong mounts and pending target/closure jobs; native IRQ fixtures retain only
one exact row and reject malformed/duplicate/overflowed counts. Actual native
child execution proves completion/nonzero/overflow/timeouts, and injected clock
failures end unknown. A host PTY test proves query-child EOF while the parent's
queued receipt and termios remain unchanged. Native frame tests prove CRC/length,
leading newline and overlimit rejection. Observer-operation fixtures prove
collection without a receipt, one guarded reboot request, and no request after
snapshot/renewed-guard/output failure. They do not execute hardware getters or
reboot: these are explicit test seams, not a physical UART/IRQ proof.

Nix parse/evaluation passed; the rendered unit contains only a nonce condition,
public locale/timezone paths, ExecStart reset+immutable helper and Restart=no.
The original archived debug-shell TTYReset/TTYVHangup/StandardInput remain
upstream settings; the existing generator provides the ttyS0 override. The
helper has no test CLI; native production invocation with missing context
returns 2 before opening /dev/kmsg. Exact native/script behavior is not a
cross-built RISC-V artifact proof.

Offline base-relative evaluation also matched three derivations exactly:
vendor kernel `2ygsvl6i74s65iqhm9dwcnfcva7h6f5m`, default system
`6sps480wbkii38z2rjnrjg5sl38d4sgp`, console-only mainline kernel
`hy8ng8p1mja4mzmfd83dhbpcb0g9n0pm` (all `.drv` paths). Both old DRM and new
observer configurations resolve kernel `9vdk79pa4pm38mlmbflkqh4i4sc9kha0`;
the baseline bundle remains `5yqilsfyj35jzrcqjjqilkr6sd47qlms`. These are
evaluated derivation identities, not newly realized artifacts. The comparison
used the same expression for this worktree and the bounded base URL:

```sh
nix eval --offline --json --impure --expr '
let f = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-uart-observer";
in { defaultKernel=f.packages.x86_64-linux.kernel.drvPath;
     defaultSystem=f.nixosConfigurations.k230.config.system.build.toplevel.drvPath;
     consoleKernel=f.packages.x86_64-linux.kernelMainline.drvPath; }'
# Repeat with the getFlake URL ending ?rev=9854479615d2800d53e79cf14939397a93e3fe1f
# in the canonical repository; compare all three returned fields exactly.
nix eval --offline --raw .#nixosConfigurations.k230-mainline-uart-observer.config.boot.kernelPackages.kernel.outPath
nix eval --offline --raw .#packages.x86_64-linux.kernelMainlineDrmTrialBootFiles.outPath
```

Read-only peer review by the controller agent found no blocking source/Nix
correction and confirmed the stages/fields match its committed controller;
that review did not run a cross-build or physical trial.

Cached work-status start passed at idle priority; an initial attempt before
sparse worktree materialization reported a missing tools file and was rerun.
Handoff scan session97318 was started at idle priority, output
`/home/jadams/tmp/mainline-uart-observer-handoff-status.txt`; a slow scan must not
hold an otherwise ready source commit.

## Matching artifact and physical gates

The coordinator's next build, under its exclusive build slot:

```sh
flock /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartObserverBootFiles --no-link --print-out-paths \
  --max-jobs 1 --cores 16
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-trial-inspect.py <observer-bundle>
```

The new bundle compares kernel identity/Image with the existing baseline and
normalized sorted DTBs after deleting only /chosen/bootargs; it fails before
metadata on any other difference. observer.json records helper/source/DT hashes,
base identity and selected system/init, covered by SHA256SUMS. The independently
reviewed new host controller must repeat actual artifact comparisons and inspect
the selected initrd archive for helper ELF64/RISC-V bytes, marker, exact drop-in
and preserved upstream unit policy before opening serial. Its selected-system
sole-init and printed volatile arguments, per-artifact SHA/size/CRC/load-range
and protected normal pre/postflight gates still apply. A metadata boolean is not
sufficient artifact proof.

Source review/landing, matching cross-build/archive inspection, reviewed host
controller and one reserved physical trial remain. The operator command belongs
to that separate controller handoff. Require actual complete fresh frames,
receipt classified independently, kernel restart/SPL, and fresh exact protected
normal identity/services/eight hashes before any physical recovery claim.

## First wrapper build failure and correction

The coordinator reports a cross-build from merged `5d09128c` under its exclusive
build slot: helper, initrd, system and underlying trial artifacts built, but
`/nix/store/wap6rfwd24rmc6naj6qsh2axgbrs6dlb-k230-mainline-uart-observer-boot-files.drv`
failed while creating `observer.json` with permission denied. `cp -a
${trial}/. $out/` preserved the source directory's read-only permissions;
making only `SHA256SUMS` writable left the output directory unwritable.
The wrapper now runs `chmod u+w $out` immediately after the copy, before adding
metadata. This is a source correction, not a successful wrapper rebuild or
artifact inspection. Physical staging stayed paused on protected normal.
Nix parse, strict OpenSpec validation and diff checks are the bounded checks;
the coordinator still owns the rebuild and all later physical gates.

## Closure-inventory preflight rejection and correction

The coordinator's wrapper rebuild from `0e5436de` produced
`/nix/store/hg1yq5qvam1jh07ibz591r0v4g6qzq4b-k230-mainline-uart-observer-boot-files`.
Standard artifact checks and exact archived helper/unit inspection passed, but
the full controller preparation rejected `observer closure lacks selected
helper/system/kernel`: system and kernel were inventoried, while helper
`7n4rdzx19xxk8r0n4h16gf9s8qsnq85k` was absent from the system-derived store-paths.
Compressed initrd inclusion alone did not retain its package as a runtime
reference. No UART was opened and the private export was not staged.

The optional module now adds the same helper to `system.extraDependencies`,
keeping it in the registered/staged system closure as well as the initrd.
The controller guard and inventory format remain unchanged. An offline Nix
assertion checks that the evaluated dependencies contain the exact selected
helper; only a new cross-build and actual store-paths/controller inspection can
prove the realized closure correction. The coordinator owns those gates;
physical observation/recovery remain UNVERIFIED.

The dependency/unit membership check is:

```sh
nix eval --offline --impure --json --expr '
let f=builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-uart-observer";
    cfg=f.nixosConfigurations.k230-mainline-uart-observer.config;
    helper=f.packages.x86_64-linux.mainline-uart-observer;
    dependencies=map toString cfg.system.extraDependencies;
in assert builtins.elem (toString helper) dependencies;
   assert builtins.elem "ExecStart=${helper}/bin/k230-uart-observer"
     (f.inputs.nixpkgs.lib.splitString "\n" cfg.boot.initrd.systemd.units."debug-shell.service".text);
   { inherit dependencies; selectedHelper=toString helper; }'
```

The dependency-only assertion passed with exact helper
`7n4rdzx19xxk8r0n4h16gf9s8qsnq85k` present. The additional unit-line assertion
and repeat of the three default/console identities were still pending in
evaluation session86830 at handoff; prior identity proof remains recorded above.
Nix parse, strict OpenSpec validation and staged diff checks passed. No native test rerun,
cross-build or board operation was performed for this dependency-list edit.

# Same-image Bash PID1 comparison: host preparation

Evidence class: source inspection, host artifact inspection, scripted transport
and isolated host shell fixtures. Physical Bash readiness, UART reception and
automatic protected return for this comparison are **UNVERIFIED**. Ordinary
NixOS root, panel/glass touch and task 5b.5 remain open.

Branch `mainline-shell-pid1-comparison`, base
`358b63241659f90e48b7249b913bfd7f71ac7d08`, worktree
`/home/jadams/tmp/k230-mainline-shell-pid1-comparison`. Owned changes are the
initrd shell controller, `tests/test_mainline_shell_pid1_comparison.py` and this
note. No board, UART, camera, build slot or network server was used. Existing
kernel/system/bundle derivations and historical controller defaults are unchanged.

## Exact comparison

Explicit `--same-image-shell-pid1` is allowed only with `--mode minimal`,
without clock-ignore, boot-debug or runtime-shutdown tracing. Before any serial
access, preparation validates the original immutable bundle, manifest, selected
system, hashes/sizes/CRCs, protected normal report and actual load ranges through
the existing helpers. It then requires the exact original serial-only SBI-only
artifact arguments, removes both trace-enable tokens and adds the three
qualified controls plus `initramfs_async=0` and sole `rdinit=/bin/sh`.

Compared with the preceding marker-free ordinary trial, only the initial PID1
program choice changes. The selected system's sole `init=` remains present for
identity qualification; Bash does not activate that system or switch root.
The literal volatile command is fully qualified and checked below 512 bytes
before opening UART. Actual printed arguments must match exactly. No persistent
environment, profile or boot-file selector is changed.

Actual host preparation passed for:

- Bundle `/nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files`.
- System `/nix/store/g74hzn6yr07il4r00r5iv3v8baw6q2cf-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Kernel `/nix/store/am9cxlangrklamgs5lb0y31q028jbabq-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/Image`, checked against the manifest Image digest.
- Selected initrd `/nix/store/2kz73105y2km2q0w9c37wi8ngrfxvkkd-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`, SHA-256 `d37496953bbf47aca5d016c7ac38064a78694e170568873a6dfa220fcaa7d6d3`.

The actual wrapper's complete header/data CRCs, RISC-V ramdisk fields, length
and payload match that selected initrd. A bounded newc walk verifies archived
executable RISC-V ELF files rather than substituting host store symlinks.
`/init` resolves to systemd 261.2; `/bin/sh` resolves to
`/nix/store/89hsc9vrrk2vr18yp9yrzs365fz490wv-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/bash`.
Both ELF `PT_INTERP` fields resolve to the same archived loader:
`/nix/store/syg6xw4x296w82267qnvrd3nn0cp6j31-glibc-riscv64-unknown-linux-gnu-2.42-84/lib/ld-linux-riscv64-lp64d.so.1`,
SHA-256 `19835521e0d42cf163f139040c5c4497edb893153c68997db327bb4a6713f904`.
Readlink, true, mkdir, mount, cat and reboot are also archived executable
RISC-V ELF files. Selected Zstandard inspection requires host Python 3.14;
an unavailable decoder fails before serial access.

## Runtime gates and limits

The existing fresh Linux → `Run /bin/sh as init process` → primary prompt gate
precedes receipt, true, proc setup and uptime. Only afterward does the opt-in
guard check outer-shell PID1, PPID0, UID0, Bash version/executable, kernel
release, exact selected cmdline, fresh non-normal boot ID, initrd release and
an in-memory root with no `/sysroot` mount or populated store. The exact same
candidate boot identity is renewed immediately before one existing acknowledged
`/bin/reboot -ff` request. Guards print fixed RC/match fields and the private
boot UUID, not raw proc/cmdline contents. Each command is below 3072 bytes;
the actual initial guard is 1804 bytes. These bounds do not establish a
wall-clock deadline for a blocked child/kernel operation.

Each guard requires one exact fresh BEGIN/END pair, no intervening unknown
text, no additional malformed/other-phase frames for that nonce, and the
returned exact primary prompt. Missing/truncated/duplicate/unknown frames stop
input; a completed failed guard also stops without requesting reboot. The raw
private log is preserved unchanged. No signal, exit, recovery command or child
retry is sent to an unknown candidate. The existing readiness (90 seconds),
receipt (at most eight fresh attempts), probe (30 seconds per completion) and
normal-return (180 seconds) bounds remain; recovery is not guaranteed if Linux
or a child blocks.

Both uploaded normal phase helpers actually assert that registration is absent,
including a dangling symlink. Existing protected normal identity/profile/kernel,
three services, eight hashes and fresh-boot checks remain. Results explicitly
record `ordinary_init=NOT_ATTEMPTED`, `usable_root=UNVERIFIED`, and
`touch=UNVERIFIED`; the probe has its own `k230-initrd-shell-pid1-v1` schema.
Success would prove Bash/common-loader userspace and qualified UART progress,
not ordinary systemd root or a cause of the previous silence. Silence cannot
distinguish exec failure, return-to-user work, scheduling or console output loss.

## Host proof

Commands run from the owned worktree:

```sh
python3 -B -m unittest discover -s tests -p test_mainline_shell_pid1_comparison.py
python3 -B -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

The focused 14 tests pass. The existing 100 initrd-controller tests pass.
Strict validation passes; all 56 OpenSpec items pass; whitespace checks pass.
The focused fixtures exercise actual safe literal transport, parser hostility,
typed CLI conflicts/default preservation, actual newc/ELF/wrapper inspection,
missing prerequisites, fresh/renewed guards, unknown-no-input persistence and
single-reboot protected-phase wiring. Generated guards execute under host
`sh`/`bash` against isolated identity/mount-table fixtures, including a false
final entry, a missing table, persistent root and `/sysroot`. Simulated identity
and prompt fields are fixtures; no host mount or real serial operation occurs.
The actual production normal registration assertion is separately executed
against absent, regular and dangling-symlink fixture paths.

Actual preparation command (private inputs are not printed or committed):

```sh
python3 -B - <<'PY'
import importlib.util
from pathlib import Path
s = importlib.util.spec_from_file_location('trial', 'tools/mainline-drm-initrd-shell-trial.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
p = m.prepare_trial(
    Path('/home/jadams/tmp/k230-mainline-shell-pid1-board/candidate-manifest.json'),
    Path('/nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files'),
    Path('/home/jadams/tmp/k230-mainline-shell-pid1-board/normal-report.json'))
p = m.prepare_shell_comparison(p)
assert len(p['transport'].encode()) == 332
assert p['bootargs'].split().count('rdinit=/bin/sh') == 1
assert p['bootargs'].split().count('initramfs_async=0') == 1
assert not any(v.partition('=')[0] in ('k230.boot_trace', 'k230.boot_trace_sbi_only')
               for v in p['bootargs'].split())
print('host preparation PASS; serial not opened')
PY
```

This passed. Its 332-byte command is the preceding 317-byte marker-free
ordinary command plus exactly ` rdinit=/bin/sh`. No Nix build was required.

## Remaining operator gate

After review/landing and independently verified protected normal recovery,
only the board operator may run the fresh private comparison:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --same-image-shell-pid1 \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest /home/jadams/tmp/k230-mainline-shell-pid1-board/candidate-manifest.json \
  --normal-report /home/jadams/tmp/k230-mainline-shell-pid1-board/normal-report.json \
  --log /home/jadams/tmp/k230-mainline-shell-pid1-board/trial.private.log \
  --result /home/jadams/tmp/k230-mainline-shell-pid1-board/result.private.json
```

Use new paths if either output already exists. Physical execution, candidate
guard facts and protected automatic return are UNVERIFIED by this host note.

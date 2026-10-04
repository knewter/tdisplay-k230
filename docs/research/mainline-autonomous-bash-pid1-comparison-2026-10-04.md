# Fixed autonomous Bash-PID1 comparison scout

Evidence class: read-only source/archive/ELF inspection, source-derived parser
models and host Bash syntax. Native exact Hush/parser execution and all physical
results for this candidate remain **UNVERIFIED**. The coordinator reports the
same-p2 nohz-off capture produced no UMK; final physical publication is pending.
This agent did not operate hardware or reproduce that observation.

The proposed next discriminator uses the existing p2 Image/initrd/DT/system,
retains async0 and the three qualified fsck/root-growth/registration controls,
removes every progress/Memory/Printk/boot-trace/nohz/nohlt gate, and appends only
a fixed post-`--` argv for `rdinit=/bin/sh`. It requires a separately reviewed
typed selector; no arbitrary script option or general quoting relaxation.

## Fixed candidate and exact lengths

The following nonce is a harmless 32-character placeholder. A future controller
must substitute exactly 32 fresh lowercase hex characters generated for that
one boot. All other bytes must equal the reviewed reconstruction.

154-byte script, with **two literal backslashes** before each `n`:

```sh
n=0123456789abcdef0123456789abcdef;test $$ = 1&&test $EUID = 0&&printf \\nK230_BP1:%s:B\\n $n&&/bin/sleep 5&&printf \\nK230_BP1:%s:E\\n $n;exec /bin/sh -i
```

477-byte raw kernel argument string, excluding newline:

```text
consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4 lsm=landlock,yama,bpf loglevel=7 init=/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd/init fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service initramfs_async=0 rdinit=/bin/sh -- -c "n=0123456789abcdef0123456789abcdef;test $$ = 1&&test $EUID = 0&&printf \\nK230_BP1:%s:B\\n $n&&/bin/sleep 5&&printf \\nK230_BP1:%s:E\\n $n;exec /bin/sh -i"
```

One 503-byte U-Boot command, with **four literal backslashes** before each `n`:

```text
setenv bootargs 'consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4 lsm=landlock,yama,bpf loglevel=7 init=/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd/init fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service initramfs_async=0 rdinit=/bin/sh -- -c "n=0123456789abcdef0123456789abcdef;test $$ = 1&&test $EUID = 0&&printf \\\\nK230_BP1:%s:B\\\\n $n&&/bin/sleep 5&&printf \\\\nK230_BP1:%s:E\\\\n $n;exec /bin/sh -i"'
```

The complete transmitted command plus one CR is 504 bytes. It stays below the
controller's existing strict 512-byte bound. The qualified prefix is 314 bytes;
the post-`--` arguments are `-c` and the complete fixed 154-byte script. The
format emits a leading newline and exactly `K230_BP1:<nonce>:B` or
`K230_BP1:<nonce>:E`, each followed by newline. Builtin PID1/UID0 tests gate begin;
`&&` gates the one absolute `/bin/sleep 5` and end on prior successful returns.
The final `exec /bin/sh -i` is outside that chain, so a known test/sleep failure
still attempts to enter the interactive shell rather than deliberately exiting
PID1. There is no input/read command, loop, reboot, exit, mount or persistent edit.
Runtime exec failure, EOF or output blockage still cannot be ruled out by source.

## Actual artifacts and kernel argv semantics

Existing bundle:
`/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files`.
Its selected system is the yk44 path in the exact arguments above. Kernel xna7
and dev24h identities/config/Image hashes are retained in the
[actual exact/full host proof](../evidence/mainline-uart-progress-memory-printk/exact-full-host/README.md).
No new kernel/initrd/DT build is needed for this candidate.

Selected source is
`/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`.
`lib/cmdline.c:233–284` supports surrounding double quotes but explicitly cannot
escape embedded double quotes. The script therefore contains no double quote;
only Linux's two outer script delimiters are present. `init/main.c:490–509`
repairs any split assignment inside the argument and appends it to argv.
`577–604` clears prior argv during init/rdinit setup, while `1029–1036` parses
post-`--` argv afterward. `1572–1583` uses that argv for kernel_execve;
`1693–1696` tries rdinit first and returns on successful exec. Access failure
(`1795–1807`) or exec failure can fall back, so no ordinary `/init` acceptance
is inferred from the preserved original sole `init=` token.

With all reporter gates absent, the selected worker's init returns before
creating either reporter thread (`drivers/soc/canaan/k230-uart-progress.c:224–228`).
This is a different observation than waiting for a kernel observer summary.
Regular kernel logging and all other kernel activity remain unchanged.

The actual p2 archive contains executable ELF64 little-endian RISC-V programs:

| Archived alias | Resolved path | SHA-256 |
| --- | --- | --- |
| /bin/sh | `/nix/store/89hsc9vrrk2vr18yp9yrzs365fz490wv-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/bash` | `8494a422916b769311e43f2ae463e3e93f520c8657b6c0c98c138a313af124d9` |
| /bin/sleep | `/nix/store/3m27x1rrl0wk30lz5fih10cf1dpqbaa6-coreutils-riscv64-unknown-linux-gnu-9.11/bin/coreutils` | `0f990f00e98050939fedeee9d3c0449c5b42669d2bc0443a7a3bb95bc2376adc` |

The actual Bash ELF exports `printf_builtin`, `test_builtin`, `exec_builtin` and
its builtin table; no archived `/bin/printf` dependency is introduced. Archive
presence/symbols do not establish successful execution or sleep on the board.

## U-Boot quoting and mandatory native proof

Read [official U-Boot v2022.10 Hush source](https://github.com/u-boot/u-boot/blob/v2022.10/common/cli_hush.c),
retained privately as `~/tmp/k230-autonomous-bash-scout/cli_hush-v2022.10.c`:
95597 bytes, SHA-256
`954771b8638977d12955c4da3c540a3929d47e4431a092c079192155b2d60011`.
The SDK overlay/project patches do not replace this parser. Inspected host
U-Boot outputs r55379… and 3fs5… select HUSH_PARSER=y, SYS_CBSIZE=1024 and
SYS_MAXARGS=16 in their actual `.config` files. These nearby host builds/source
are not a fresh installed-U-Boot byte identity proof; the original upstream
source tarball is currently absent locally.

Hush `cli_hush.c:2950–2952,3009–3025` treats single quotes specially even within
its double-quote path. A POSIX-style outer-double/inner-single-printf transport
is therefore unsuitable. The fixed command instead surrounds the complete
bootargs value with **single quotes**, contains no single quote inside that value,
and leaves raw dollars literal. Its single-quote branch copies bytes without
variable expansion (`3009–3016`); `done_word` removes one backslash layer
(`2498–2501`). Doubling every script backslash in the transport compensates for
that exact behavior. The resulting kernel string retains its Linux doublequote
pair and intended Bash backslashes. No U-Boot variable interpolation or script
execution is intended: setenv receives one complete data argument.

The source-derived Hush model produced the exact intended 477-byte string;
the selected Linux next_arg model produced exactly two argv entries and the
complete script. Host `bash -n` passed. These are **SOURCE MODELS and syntax
checks**, not native Hush execution, target Bash execution or physical proof.
Before hardware, native exact lexer/variable/quote/command-execution fixtures
must establish one setenv call, exact resulting bytes, zero expansion/extra
command execution and unchanged persistent environment. Selected Linux
next_arg/repair/set_init_arg argv execution proof is mandatory too; a standard
shlex/POSIX shell surrogate is insufficient. Malformed nonce, altered script,
metacharacter insertion, quote/backslash damage, extra init args, gates or length
must fail before UART. Existing controllers must retain their prior policy.

## Record and recovery limits

Use fresh exact printed and received argument proof plus a qualified new Linux
phase and `/bin/sh` entry before accepting records. Reject echoed/kernel-cmdline
text, stale nonce, duplicate/truncated/interleaved or malformed frames; do not
strip arbitrary kernel text. Missing begin/end is incomplete evidence, not a
cause. Neither record authorizes a serial command. Capture remains zero-input
after the boot command for its full bounded window; protected normal output can
qualify its existing independent postflight only after the normal-return gates.

Begin establishes only the builtin PID1/UID0 tests and autonomous output attempt;
it does not provide a proc/kernel/initrd full identity guard. End implies the
prior printf and the sleep child returned successfully; its own output return
remains unproved. A later fresh interactive prompt adds progression through that
printf return and exec. Missing end leaves first output return, child scheduling/
sleep and later TTY output unresolved. This changes userspace execution/output
and suppresses reporter threads, so it cannot isolate one IRQ or timer fault.
No RX, ordinary root, touch or automatic recovery acceptance follows. Root owns
fresh protected preparation, hardware reservation and independent recovery;
no unconditional candidate reboot is part of this fixed probe.

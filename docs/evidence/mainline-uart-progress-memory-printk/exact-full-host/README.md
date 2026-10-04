# MemoryPrintk exact objects and full matching artifacts

Evidence class: actual coordinator full build and exact selected-header GCC
RISC-V objects, followed by read-only artifact inspection. No hardware, UART,
controller preparation or runtime output proof was performed here. Tasks 5l.2–3
are proved; remaining controller/physical/recovery gates and 5b.5 stay open.

The coordinator built the matching bundle/dev from frozen revision
`1c59f8565ce6baab1e97ffad23e55556961af308`, returning 0 on 2026-10-04 at
07:13:14 UTC. The exact-object check used worktree
`/home/jadams/tmp/k230-mainline-uart-progress-memory-printk`, branch
`mainline-uart-progress-memory-printk`, source revision
`bd092485f88223da7777379cfdd432ac8a722335` (base `e2a02cb0`). Only this evidence
and task 5l.2–3 proof notes are owned by this increment. The root revision includes
reviewed source/controller integration; these are distinct build revisions.
The nonblocking shared build lock was acquired only after the coordinator's
successful receipt and released after the narrow object command. No full rebuild
or fetch was selected.

| Actual artifact | Immutable path |
| --- | --- |
| bundle | `/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files` |
| selected kernel | `/nix/store/xna7x12lh4lmzwgmwq51cyc9wf86504p-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| matching dev | `/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| selected system | `/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd` |
| selected source | `/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src` |
| exact objects | `/nix/store/ndlvakw2vxgkbsdwzw477r44wz8rpyg6-k230-mainline-uart-progress-exact-objects` |

## Actual commands and results

The coordinator command and its timestamps/output paths are preserved in
[full-build-receipt.json](full-build-receipt.json). The object command returned 0
in 9.81 seconds; its [receipt](object-build-receipt.json) and
[dry run](object-dry-run.txt) show only the named exact-object derivation.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressMemoryPrintkExactObjects --offline --no-link \
  --print-out-paths --max-jobs 1 --cores 2
python3 docs/evidence/mainline-uart-progress-memory-printk/exact-full-host/verify-host.py \
  /nix/store/ndlvakw2vxgkbsdwzw477r44wz8rpyg6-k230-mainline-uart-progress-exact-objects \
  docs/evidence/mainline-uart-progress-memory-printk/exact-full-host/full-build-receipt.json \
  docs/evidence/mainline-uart-progress-memory-printk/exact-full-host
```

The exact build uses the actual selected kernel.dev installed config/autoconf,
with no forced CONFIG overlay, and the actual three patched sources. The
installed `/source` symlink is a build skeleton; the selected full source is
independently pinned above and in the object output. The verifier asserts source
layering over Memory, source SHA, same kernel/dev derivation, all target objects,
format bytes and source dependencies. It returned 0. No failed proof invocation
occurred in this exact/full check.

The actual applied worker SHA is
`30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2`.
Installed config SHA is
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`;
autoconf SHA is
`99f44d781b246202edab1d5ef8c4836b15ae99c590999ff268541dfd673865d0`.
Both files equal the actual Memory parent dev byte-for-byte, with no effective
CONFIG difference. PRINTK, PRINTK_TIME, PRINTK_EXECUTION_CTX, SERIAL_8250_CONSOLE,
SERIAL_8250_DW and K230_UART_PROGRESS are built in; PRINTK_CALLER is explicitly
unset. That qualifies the reviewed timestamp-only parser policy, not future
output delivery.

All three objects are ELF64 little-endian RISC-V relocatables built with GCC
15.3.0. Readelf excerpts retain complete header/section tables and relevant symbol
rows. Observer, worker, getter functions, flags, packed state and completion have
ordinary lifetimes. Only setup/init routines are init sections. Inherited four
records remain exact, aligned 64, no larger than 64 bytes and page-contained;
inherited two summary buffers remain 256-byte BSS objects aligned 256. The
KERN_INFO-prefixed leading-newline UMK format occurs once in ordinary rodata.
The target observer has one acquire fence, completion wait and ordinary `_printk`
call; worker release fences and completion are present. The selected printk arm
jumps to the observer return after its call. The legacy SBI arm remains compiled
for unchanged modes. Source/native checks prove the selected arm returns with no
DBCN fallback; a global absence of the SBI symbol would be an incorrect claim.
See [memory-api-disassembly.txt](memory-api-disassembly.txt) and [proof.json](proof.json).

The preserved compile log contains a pahole-version warning (kernel 131,
object environment 0). It contains no C warning. This is an object/API/layout
proof, not a claim that all complete-kernel build tooling was duplicated.

## Complete artifact inspection and limits

The existing trial inspector passes Image/candidate equality, system/kernel
selection, sole executable system init, initrd payload equality, uImage CRC,
manifest digests and 629-path closure inventory. Original bundle boot parameters
remain exact, serial-only and with the original two trace flags; no runtime
MemoryPrintk/progress/async/rdinit/nohlt/earlycon/keep_bootcon selection is baked
into this bundle. The typed controller owns the reviewed volatile transformation.
All expected inherited Image literals and the unique new format/setup key are
linked. Hardware DT equals the actual Memory parent bundle after removing only
`/chosen/bootargs` from temporary copies and comparing complete sorted dtc output.
Canonical DTS SHA is
`c36085249e61fc1ed6f8f586b1ccbf11f22a4e27428a3e7e23b046384268fc02`.
Full digests/sizes are in [proof.json](proof.json), with original inspector output.

These checks establish compiled source/config/API/artifact coherence. They do
not establish kthread execution, timer dispatch, console ownership progress,
printk return, UART RX, ordinary root or touch. The one ordinary output call can
block or fail; a future received UMK frame would describe the coherent pre-call
snapshot, not prove the call returned or identify the cause of earlier silence.
Missing output remains inconclusive. Root owns actual controller qualification,
protected preflight, physical capture and independent normal recovery. No
operator command was run by this host verifier.

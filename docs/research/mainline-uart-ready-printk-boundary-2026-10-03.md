# Mainline UART READY / printk return boundary

Evidence class: read-only source audit and host string-width calculation.
Physical comparison and cause attribution are **UNVERIFIED**. This continues
mainline task 5b.5; it changes no helper, controller, kernel, default image,
protected card file or profile.

Audit base: `667d45388ee1b5599278fdeb18e36528473a6b74`, branch
`audit/mainline-uart-printk-boundary`, worktree
`/home/jadams/tmp/k230-mainline-uart-printk-audit`. Sole owned path is this note.
The coordinator reserves hardware and the build slot; this audit used neither.

## Observed boundary and exact sources

The committed [physical packet](../evidence/mainline-system-trial/uart-observer-physical-2026-10-03/README.md)
records source `11d49eb0f72d28c0f9cdc070fea4662410451c10`, selected bundle
`/nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files`
and system
`/nix/store/k1zjqdn4ks7b5dd7b3py6cavhf85g6j6-nixos-system-nixos-26.11.20260919.20b1ddd`.
There was one complete CRC-checked sequence 0 READY record, then no `before`,
`after`, `return` or primary prompt. Zero host receipts were sent; the full
180-second passive normal-return window expired. Operator reset recovery was
pending in that packet. No physical counter values were obtained.

Helper source is [observer.c](../../nix/mainline-uart-observer/observer.c), SHA256
`e137753bf0f9decb763599df4b7c101fb276841310f1a2219d101b3ac244ee74`.
Kernel is
`/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`;
exact patched source is
`/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`
(upstream pin `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`, with the already
reviewed optional DRM/restart/SD1 clock changes). Configuration is
`/nix/store/7vxby0h1nz78r9qzbqfjjs9vw4x7gpl0-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5`:
`CONFIG_PRINTK`, `VT`, `FRAMEBUFFER_CONSOLE`, `DRM_FBDEV_EMULATION` and
`DRM_CANAAN` are enabled; `PREEMPT_RT` is disabled. Line references below are
to this exact source, not a newer upstream kernel.

## Helper bounds and native exit possibilities

`observer.c:480–485` emits READY, constructs the already-collected initial
sample and emits `before`. There is no intervening getter, guard, wait,
fork or external utility. READY follows successful initial guard/getter work
and the observer fork; it does not establish that its `write()` returned.

`sample_payload()` at lines 447–458 formats bounded numeric values and one
fixed runtime string. An intentionally conservative host calculation used:
four 8-digit flag fields; two maximum unsigned-32 speed codes; `INT_MIN`
line discipline; seven maximum unsigned-32 counters; maximum accepted IRQ
1048576; IRQ availability 1; maximum unsigned-64 total; and `suspended`.
The `before` payload is **335 bytes**, below `PAYLOAD_MAX=384`; its full record
including `<6>\n`, nonce, framing, hex payload and newline is **743 bytes**,
below `FRAME_MAX=900`. The recorded initial snapshot uses zero-initialization
and fixed, terminated runtime strings (`take_sample()`, lines 336–359).
Thus a valid initial sample cannot hit either size rejection. This is a host
width proof, not execution of the physical sample.

`emit()` at lines 429–440 performs one `write()` and rejects errors or short
writes without retry. The observer returns silently if READY or `before`
emission fails; no `failed` frame can establish a failed output path itself.
A second-write error, a signal/process-lifetime problem, or a write that never
returns remain distinct possibilities. None is observed directly. Parent
`execv("/bin/sh", ...)` runs independently after the fork (lines 501–521), so
the missing prompt alone cannot choose among these paths.

The fresh `/dev/kmsg` file has its own default rate-limit state
(`kernel/printk/printk.c:920–947`), with burst 10 / interval five seconds
(`include/linux/ratelimit_types.h:9–10`). Only READY and `before` are attempted
before the 12-second wait. Ordinary exhaustion of that fresh burst is therefore
not a source-supported explanation for losing the second record. The write
path can nevertheless return a full byte count while dropping a disabled or
rate-limited message (`printk.c:752–760`); a successful write is not wire proof.

## UART visibility can precede a completed write

`devkmsg_write()` calls `devkmsg_emit()` synchronously before returning
(`kernel/printk/printk.c:739–799`, `726–734`). Its path reaches `vprintk_emit()`;
`O_NONBLOCK` does not bypass or impose a deadline on console flushing here.
The helper's bounded child guards do not bound this output syscall.

The 8250 UART console declares `CON_NBCON`
(`drivers/tty/serial/8250/8250_core.c:523–529`). The VT console uses
`vt_console_print()` and `CON_PRINTBUFFER`, without `CON_NBCON`
(`drivers/tty/vt/vt.c:3535–3543`). At normal priority, the flush policy can
choose nbcon atomic/threaded UART output and direct legacy output together
(`kernel/printk/internal.h:194–215`). With non-RT configuration, ordinary
userspace printk need not defer the legacy path
(`kernel/printk/printk_safe.c:59–72`).

`vprintk_emit()` first stores the record, flushes/wakes nbcon output, then may
call `console_trylock_spinning()` and `console_unlock()` in the same calling
context (`printk.c:2455–2481`). The legacy loop skips independently serviced
nbcon consoles but calls the legacy emitter for VT
(`printk.c:3244–3269`). Consequently UART can show a complete READY record
while the emitting observer is still in that first write's legacy flush.
This is a feasible ordering, not a stack trace or proof of a stuck console.

If VT actually uses fbcon, `vt_console_print()` calls console glyph/cursor
and scrolling operations (`vt.c:3448–3521`, `602–616`, `1477–1483`);
`fbcon_putcs()` dispatches framebuffer bit operations
(`drivers/video/fbdev/core/fbcon.c:1391–1403`). Actual framebuffer adoption
cannot be inferred from the build options or the panel photograph:
`drivers/gpu/drm/canaan/canaan_drv.c:275–278` deliberately leaves fbdev unset
when `/chosen/canaan,stage1-splash` is present, otherwise it sets up the DRM
client. U-Boot can insert that property depending on splash readiness
([the existing fixup](../../nix/patches/uboot-k230/0005-k230-stage1-splash-readiness.patch)).
READY reports no property/fbcon state. Do not claim a framebuffer callback,
DRM lock or UART IRQ is the cause.

## Bounded next comparison

After operator reset and complete protected normal verification, a reviewed
controller option `--serial-console-only` can remove **exactly** the one
`console=tty0` token from the verified original artifact bootargs. Keep
`consoleblank=0`, `console=ttyS0,115200n8`, the selected sole `init=`, all five
qualified diagnostic controls and all three fresh observer identities. Do not
add `rdinit`, `clk_ignore_unused`, extra systemd controls or a persistent
`saveenv`. Keep bundle, Image, DT hardware, initrd and helper unchanged.
`register_console()` only enables matching preferred consoles when an
explicit preferred console exists (`printk.c:4095–4138`); removing the VT
console selection narrows printk fan-out while leaving DRM probing enabled.

The controller must still validate the untouched artifact bootargs/DT,
allow only this single volatile token removal, verify the exact resulting
`printenv bootargs`, and retain preparation, fresh identities, receipt gates,
raw private framing and normal postflight. The helper's existing strict
control parser does not require `console=tty0` (`observer.c:111–141`). Host
tests must reject missing/duplicate/wrong original console tokens and any
other mutation. No physical run was performed by this audit.

Useful outcomes are complete before/after/return frames plus protected return,
or the same READY-only boundary. A recovered run without a host receipt is
still a failed RX diagnostic. Any improvement establishes dependence on this
console selection in this comparison; it does not identify an fbcon function
or prove ordinary usable-root/touch acceptance. Missing/invalid frames remain
unknown: no further input, no reboot retry, full passive return deadline and
operator recovery as required. A userspace timer cannot guarantee recovery
from a blocked kernel output syscall.

## Narrow validation

Read exact installed source/config with `sed`, `rg` and line-numbered excerpts;
run a host Python string calculation of the maximum values above (335/743);
`git diff --check` passed;
`openspec validate the-board-runs-a-mainline-kernel --strict` passed with
`Change 'the-board-runs-a-mainline-kernel' is valid`.
No native compilation, Nix evaluation/build, serial access, board observation
or kernel/controller source edit was performed. Review, coordinator landing
and the separately reviewed physical comparison remain required.

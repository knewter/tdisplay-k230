# Optional RVV pixel correctness trial

The [physical context trial](../../kernel-rvv/board-trial/README.md) establishes
usable standard vectors and representative signal/scheduling preservation.
This next diagnostic checks actual Pixman output before any card performance
comparison. The normal image and renderer remain unchanged.

## Package and dispatch observation

`nix build .#pixman-rvv-pixel-probe --max-jobs 1 --cores 4 --no-link --print-out-paths`
builds the scalar-entry diagnostic against the actual optional Pixman 0.46.4
library. [build.json](build.json) identifies the source, library and binary;
[staging.json](staging.json) records the two-path export imported on the board.
The transfer SHA256 matched, Nix import succeeded, and a separate GC root pins
the diagnostic. Runtime credentials are not part of that export.

The diagnostic uses the pinned upstream private test API and header from the
same source tarball. Upstream's implementation order is general → fast →
optional RVV → noop (`pixman-implementation.c` and `pixman-riscv.c`). It refuses
an unexpected version or chain length. With runtime-selected RVV enabled, it
copies that implementation's fast-path table and wraps its callbacks and
integer combiners. Each wrapper counts a call and invokes the original callback
with unchanged arguments; no pixel arithmetic is replaced. With
`PIXMAN_DISABLE=rvv`, the three-entry fallback chain remains untouched.
Both modes first require the scalar kernel hwprobe V gate.

These counters establish executed RVV callbacks, including fallback cases where
none execute. They add overhead and must **not** be used as card cost data.
The private ABI dependency is confined to this diagnostic, not the compositor.

## Declared cases

There are 192 cases: three source formats (RGB565, premultiplied ARGB8888,
XRGB8888), two target formats (RGB565, ARGB8888), four operations (copy, OVER,
nearest scaling, bilinear scaling), and eight widths (1, 7, 15, 16, 17, 31, 64,
568). Inputs are deterministic; alpha spans the source data. Strides have extra
padding, target coordinates are offset, and the target has a clip and exterior
pixels. Each comparison checks the complete output byte array, including
padding and pixels outside the operation; hashes in the report are provenance,
not a substitute for the actual byte comparison.

A third vector run deliberately flips exactly one output byte in the first
case. The checker must reject precisely that case and record one differing
byte. Missing/duplicate cases, unexpected dispatch, truncated files and mode
mismatches fail the comparison. These cases do not exhaustively cover masks,
all transforms, floating-point operators, colorspaces or the full Pixman API.

## Emulated diagnostic proof

```sh
python3 tools/pixman-rvv-compare.py --qemu /usr/bin/qemu-riscv64-static \
  --package /nix/store/1sc1733sagi7ifx4bxw4dz0yg3hw3amj-k230-pixman-rvv-pixel-probe-riscv64-unknown-linux-gnu-0.1 \
  --output NEW_QEMU_OUTPUT
```

[qemu-result.json](qemu-result.json) passes all 192 byte comparisons, with 56
RVV fast-path calls and 864 RVV integer-combiner calls versus zero in scalar
mode. The deliberate one-byte control is detected. This is QEMU **user**
execution of a pixel diagnostic, not kernel context or physical board proof.
The earlier user-emulation signal limitation remains separately documented.

## Physical invocation

After a matching one-time trial boot, reserve the board and run:

```sh
python3 tools/pixman-rvv-compare.py --board \
  --package /nix/store/1sc1733sagi7ifx4bxw4dz0yg3hw3amj-k230-pixman-rvv-pixel-probe-riscv64-unknown-linux-gnu-0.1 \
  --output NEW_BOARD_OUTPUT
```

The host owns the serial lock, transfers the checker with verified content,
and accepts only a fresh token-tagged report. The board requires the exact
matching trial system/model and repeats the physical context probe before
running pixels. Each run uses a temporary directory removed afterward. A
normal-system recovery check is required after the trial.

## Physical result and recovery

[board/result.json](board/result.json) and [the emitted serial report](board/report.serial.log)
pass all **192** physical comparisons with zero differing cases. The vector
run observes 56 fast-path and 864 integer-combiner calls, versus zero in the
scalar run. The deliberate corruption differs in precisely one byte of the
first case and is rejected. The fresh context probe passes both 2,000-check
processes; the parent records 2,002 signals and 528 involuntary switches.
The trial boot ID is `998e3c70-84bd-48a6-9659-119f6a85e631`; the actual
second bootloader trial is [boot2.json](boot2.json).

Some operations legitimately retain fallback. For example, ARGB-to-RGB565
nearest scaling at width 568 records no RVV callback, while the same bilinear
case records nine vector combiner calls and OVER records one vector fast-path
call. The evidence records this per case rather than claiming every operation
uses vectors.

An ordinary reboot returned to the normal system without physical intervention.
[normal-recovery.json](normal-recovery.json) and [its serial report](normal-recovery.serial.log)
pass: fresh normal boot, matching system selection, preserved firmware/boot
hashes and root layout, active shell/seatd, successful no-op growth service,
protected credential permissions, and Wi-Fi HTTPS. No full-image reflash or
readback was used.

## Optional card package, not a measured speedup

`nix build .#card-shell-rvv --max-jobs 1 --cores 4 --no-link --print-out-paths`
passes. [card-package.json](card-package.json) records its exact store path and
104-path closure. Nixpkgs' `replaceDependencies` substitutes the ABI-identical
Pixman build recursively through dependent store references, avoiding two
competing Pixman SONAME providers and retaining the exact card source. The
result has exactly one Pixman provider: the library checked above. Sway and
wlroots `.text` dumps are byte-identical to their original counterparts; the
reference rewrites affect their dependency paths.

This is an explicitly optional diagnostic package, not a default-image change.
A future default promotion requires a fully rebuilt and reviewed dependency
graph. The pixel diagnostic's callback instrumentation is not included in the
card package. Runtime library selection and the paired card workload still
require physical measurements on the same trial kernel with RVV on/off.

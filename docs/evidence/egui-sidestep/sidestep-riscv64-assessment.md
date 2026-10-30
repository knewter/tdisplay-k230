# Sidestep on the K230: riscv64 port assessment and measurements

**Subject:** Sidestep, `https://github.com/bitemyapp/sidestep` at commit
`626422b1fa52fc14af13976c5c90b4efd657b1d7` (2026-10-08, "Scroll tiles, animator
drawing and toplevel geometry"). Rust edition 2024, MIT or Apache-2.0. About
239,000 lines of Rust in its crates. Wayland only, CPU rendering with tiny-skia.

**Evidence classes in this file** (kept apart on purpose):

- *Source reading:* the inventory and the go/no-go.
- *Host build:* `cargo check` and a cross-build for `riscv64gc-unknown-linux-gnu`
  on the x86_64 build host, outside Nix (see "Limits").
- *QEMU user mode:* riscv64 instructions executed by `qemu-riscv64-static` on the
  host. Proves instruction-level behaviour of the assembly and the ABI layout; it
  proves nothing about speed or about the board.
- *Board, no display:* command-line benches run as transient systemd units on the
  K230 under the board lock, with the normal session untouched.
- *Board, window:* Sidestep demo apps started in the normal Sway session, captured
  with `grim` (`captures/sidestep-*.png`, `sidestep-board/window-*.txt`).

## Verdict

**Go: the riscv64 port was bounded, was done, and passes its conformance suite
apart from one missing optimisation.** About 500 added lines of Rust and
assembly plus a one-line patch to a third-party crate. All the Objective-C
runtime semantics (classes, messaging through `objc_msg_lookup`, ARC, blocks,
NSInvocation, forwarding, proxies) pass their conformance tests under QEMU user
mode. The real obstacle is not the port but the speed: see the measurements.

## Where the architecture lives

Hand-written assembly and calling-convention code exists only for aarch64 and
x86_64. Counted at `626422b`, items gated on `target_arch`:

| File | aarch64 lines | x86_64 lines | What it is | riscv64 treatment |
| --- | ---: | ---: | --- | --- |
| `sidestep-runtime/src/trampoline.rs` | 61 | 71 | register-saving frame shared by `objc_msgSend` and forwarding | new macro arm (85 lines incl. docs) |
| `sidestep-runtime/src/call.rs` | 197 | 211 | argument layout for `NSInvocation`/forwarding, `sidestep_invoke` asm | new `Registers`, LP64D `Layout`, asm, a test (282 lines) |
| `sidestep-runtime/src/forward.rs` | 34 | 33 | forwarding trampoline entries | three entries (46 lines) |
| `sidestep-runtime/src/msgsend.rs` | 37 | 133 | `objc_msgSend` with an assembly cache probe | slow-path-only `objc_msgSend` and `objc_msgSend_stret` (47 lines) |
| `sidestep-runtime/src/block_imp.rs` | 35 | 24 | executable stubs for `imp_implementationWithBlock` | 5-instruction stub (plain and stret), instruction-cache flush (51 lines) |
| `sidestep-runtime/src/arc.rs` | 60 | 52 | autorelease return-value handoff | **not ported**: the existing portable fallback is used |
| `sidestep-runtime/src/message.rs` | 0 | 7 | struct-return selector shift | one cfg (4 lines) |
| `sidestep-foundation/src/cf/bundle.rs`, `sidestep-appkit/src/workspace.rs` | 1 each | | an Apple constant | untouched |

`objc2` sends every message through `objc_msg_lookup` (portable Rust), so the
common path never touches assembly. What the assembly serves is C callers of
`objc_msgSend`, `NSInvocation` and message forwarding, blocks used as methods,
and a speed-up for autoreleased return values.

One more obstacle was outside Sidestep: the third-party crate `objc2-encode`
4.1.0 has no arm for the size of `long double` on riscv64 (16 bytes, IEEE
quad), so nothing compiles. A one-line patch through `[patch.crates-io]` fixes
it: `nix/sidestep-riscv64/objc2-encode-4.1.0-riscv64.patch`.

The port itself is `nix/sidestep-riscv64/sidestep-riscv64.patch` (526 added,
21 changed lines, nine files, runtime plus conformance-test cfgs).

### ABI details the port had to get right (LP64D)

- Arguments in a0-a7 and fa0-fa7; a `float` in an `fa` register must be
  NaN-boxed (upper 32 bits all ones) or the callee reads a NaN. The register
  save area stores `fa` registers with `fsd` and the layout code boxes floats.
- A struct of one or two floating-point members, or one floating-point and one
  integer member, travels in `fa`/`a` registers; anything else of 16 bytes or
  less in one or two integer registers (a pair on an even register when 16-byte
  aligned, or split between the last register and the stack); larger by
  address. A struct returned in memory takes a0, so the receiver and selector
  arrive one register late, as on x86_64; hence `objc_msgSend_stret`.
- 32-bit unsigned integers are sign-extended in registers.
- A module-level `global_asm!` is assembled for the default target features, so
  the double-precision instructions need `.option arch, +d`; without it a release
  build fails with "instruction requires the following: 'D'".

## Results

### Conformance (QEMU user mode, riscv64)

Command and environment: `nix/sidestep-riscv64/README.md`. Logs:
`sidestep-conformance-riscv64-qemu-user.txt` (final run, 2026-10-30) and
`sidestep-conformance-x86_64-control.txt` (x86_64 control for the failing files).

Final run of the whole conformance crate: **610 tests passed, 3 reported
failures**, plus four AppKit binaries (`appkit_autolayout`, `appkit_split`,
`appkit_stack`, `appkit_views`) that abort on a layout rounding assertion.

| Failure | Cause | Port-related? |
| --- | --- | --- |
| `autorelease::claimed_return_is_handed_over` | the return-value handoff is not ported | **Yes**, a known gap (below) |
| `appkit_autolayout`, `appkit_split`, `appkit_stack`, `appkit_views` | layout rounding differs by fractions of a point | No: the same four fail identically on the x86_64 control in the same environment |
| `coregraphics::fonts`, `services::home_temporary_and_user` | the test needs system fonts / the real HOME; the run used a 3-font directory in a user namespace | No: same two fail on the x86_64 control |
| `rich_text::rtf_default_font` | `Helvetica` and `Times` stand-ins resolve to the same font in the 3-font directory | Probably not; it passed on the x86_64 control, whose font lookup can load the host's fontconfig, which a riscv64 process under QEMU cannot. **Not isolated.** |

An earlier run of the same suite failed in four more places, each a real port
bug that was fixed and re-run: the stack-argument offset in the forwarding
frame (`invocation`), a missing `objc_msgSend_stret` entry (`msgsend`,
`proxy`), and a missing struct-return stub kind for blocks (`block_imp`).

### Known gaps in the port

- `objc_msgSend` takes the slow path on every call (it looks the method up in
  Rust instead of probing the cache in assembly). Correct, slower than the other
  architectures. `objc_msgSend_fpret` and `class_getMethodImplementation_stret`
  do not exist on riscv64.
- No autorelease return-value handoff. The fallback `autorelease`s each returned
  object into the current pool. Correct, but **a loop that receives autoreleased
  objects inside one long-lived pool grows without bound until the pool drains**.
  `msgbench`'s "autoreleased return, retained by the caller" case (10 million
  iterations inside one pool) was killed by a 380 MB memory limit on the board
  (`sidestep-board/msgbench-short.txt` ends there). Event-loop apps drain the pool
  once per pass, so ordinary apps are less exposed than that bench.
- No RVV vectorisation: the Rust target is plain `riscv64gc`. tiny-skia's
  portable code paths are used.
- Not packaged in Nix: Sidestep's `tools/objc2-overlay` downloads and patches
  crates at build time. The binaries here come from a host cargo build, linked
  with the K230 cross closure's compiler wrapper and glibc 2.42-84 (the same glibc
  the board runs, so the binaries run unchanged), stripped. They are test
  artifacts, not pinned deliverables.

### Board measurements (no display), K230, 2026-10-30

Single C908 core online at 1.6 GHz class clock (`cpu_freq` was not exposed), under
the board lock, on the normal booted system with the shell running. Raw outputs
are in `sidestep-board/`. Medians of seven runs as printed by each bench. These
are from the same `msgbench`, `eventbench`, `controlbench` and `drawing-gallery`
sources the Sidestep project publishes for macOS and Linux comparisons; no x86
or Apple numbers are quoted here because none were measured on this board.

| Case | K230 riscv64 |
| --- | ---: |
| baseline: indirect call to a Rust function | 7.3 ns |
| `msg_send!` instance method | 23.4 ns |
| `msg_send!` class method | 23.1 ns |
| generated binding `-[NSObject hash]` | 27.8 ns |
| retain + release | 38.8 ns |
| `objc_msgSend` called directly (slow path) | 59.9 ns |
| forwarded message (`forwardingTargetForSelector:`) | 115 ns |
| forwarded message (`forwardInvocation:`) | 2,930 ns |
| `NSInvocation` invoke, one object argument | 755 ns |
| alloc + init + release `NSObject` | 187 ns |
| alloc + init + release, class with ivars | 354 ns |
| autorelease pool push/pop, one object | 162 ns |
| autoreleased return not kept, own pool | 209 ns |
| `NSString from_str("hello")` + release | 520 ns |
| weak load + release | 98 ns |
| weak reference create + destroy | 437 ns |
| view frame change, unobserved (`eventbench`) | 3.1 us |
| view frame change, observed | 4.7 us |
| post and take an event | 1.6 us |
| key event to first responder | 0.45 us |
| idle run-loop pass | 3.7 us |
| pointer move reaching a tracking loop | 12.7 us |
| label made and sized (`controlbench`) | 28-55 us |
| button made | 24.6 us |
| label `setStringValue` + intrinsic size, new text | 11.2 us |
| `drawing-gallery` bench frame (2,000 rounded fills, 1,000 strokes, 300 images) into a bitmap, 1x | **888 ms** |
| same at 2x | 2,005 ms |

Further `msgbench` cases: associated object get 142 ns, set+get+remove 1,054 ns,
four threads reading associated objects 624 ns each. "Autoreleased return,
retained by the caller" run at 100,000 iterations (the memory-bounded setting):
532 ns median (379 ns best), against the unbounded 10 million that was killed.

`textbench` (an 11 MB, 200,000-line `NSTextView`) did not complete a single case:
it grew to its 380 MB memory limit on a 927 MB board and was stopped by hand
after about 17 minutes (the `EXIT 0` in its output file is systemd's code for
that stop, not completion). That workload is out of reach on this hardware as
configured.

### Board, window: the demo apps run

Both `controls-gallery` and `drawing-gallery` mapped a 1232x568 window in the normal
session (unit stopped afterwards; compositor, system closure and sway PID unchanged)
and drew correctly through tiny-skia into shared memory (`captures/`). In the
controls gallery the **button and label text did not render** (blank controls); the
cause was not investigated (fonts or text path). Resident memory 24 MB (controls) and
20 MB (drawing), proportional 19 and 17 MB. Over 20 idle seconds the drawing gallery
used 0 CPU ticks, but the controls gallery used 3.2 s of a core, **16% of the
core while showing static controls** (it animates spinners and progress bars; Sway
used 1.4 s over the same period). Startup time was not recorded (the window poll was
1 s and its timer failed).

Reading these: the runtime itself is fast enough for UI work (tens to hundreds
of nanoseconds per message, microseconds per event or property change). What
is slow is drawing: one bench frame of 3,300 operations took 888 ms. A real
app draws far less per frame (the scene in the egui and Qt trials is a few
dozen rounded rectangles and glyph runs), so per-frame cost at that scale is
**not measured here**; the scene-matched Sidestep client (task 4.1) was not
written, so there is no Sidestep number to put next to egui's or Qt's.

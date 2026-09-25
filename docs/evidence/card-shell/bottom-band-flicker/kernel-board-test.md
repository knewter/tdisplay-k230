# Board test: kernel VO vblank-latch fix

Branch `fix/drm-vblank-latch-and-idle-redraws`, based on `origin/master`.
This is a **kernel change**: it needs a full image build, a flash, and a
reboot to take effect -- there is no lighter "push a file" path for a
kernel/DTB change (unlike a userspace package). I have not touched the
board; every command below is either a host build or something the
coordinator runs on the board/serial console.

## 1. Build (host)

```sh
nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths   # narrow proof the patch applies and compiles
nix build .#sdImage --max-jobs 1 --cores 6 --no-link --print-out-paths  # the full image, same kernel, for flashing
```

`.#sdImage` already resolves to `self.k230Kernel.kernel`, i.e. the same
`nix/kernel.nix` this patch modifies (`flake.nix`'s `sdImage` /
`k230Kernel` definitions) -- there is no separate "kernel-only" flake
output to build here, only the two commands above (one narrow, one the
real image).

## 2. Flash (primary path: over USB, board stays assembled)

Per `docs/uboot-ums.md` (already hardware-proven,
`docs/evidence/uboot-ums-write.txt`/`uboot-ums-enumerate.txt`): connect a
USB cable from the host to **J3** (the data USB-C -- not J2, the charging
one with the two CDC-ACM console ports), interrupt the 5s `bootdelay` at
the U-Boot prompt over the console (`/dev/ttyACM0`), and type:

```
ums 0 mmc 1
```

Then, on the host:

```sh
./tools/flash-latest.sh --ums
```

This builds (pure) and flashes exactly the image from step 1 -- it snapshots
`/dev/disk/by-id/` before `ums 0 mmc 1`'s new USB disk appears, hands that
by-id path to `tools/flash.sh`, and `flash.sh` refuses anything that is not
an explicit by-id path. `reset` (or power-cycle) the board afterward to
boot the new kernel.

Board/serial-port reservation rules apply throughout (`AGENTS.md`): this
is real `/dev/ttyACM0` access, one operator at a time.

## 3. Fallback: card reader (always works)

If `ums` is unavailable for any reason (per `docs/uboot-ums.md` this has
occasionally taken several sessions to enumerate), the floor path always
works because the TF card is this board's only boot medium: power off,
remove the card, write it in a reader with the same image:

```sh
./tools/flash-latest.sh /dev/disk/by-id/<reader-target>
```

`flash.sh` prints the target and image and asks for confirmation before
writing; it refuses anything other than an explicit `/dev/disk/by-id/`
path. Re-seat the card and power on.

## 4. Confirm the new kernel is actually running

Before judging the fix, confirm the board booted the patched kernel, not a
stale one:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "uname -a"
```

Cross-check the reported kernel build against this branch's commit (the
kernel's `KBUILD_BUILD_VERSION`/version string, or simplest: confirm the
image just flashed was the one just built, by store path / hash, per
`tools/flash.sh`'s own pre-flash print).

## 5. Reproduce the gesture and compare

With the patched kernel booted, repeat exactly the same test the original
board diagnostic used:

- **Camera**: real bottom-edge finger gestures, recorded, split into
  strips along the panel's long axis as before, checking specifically the
  two strips nearest the bottom for frame-to-frame brightness alternation.
- **`SWAY_K230_CARD_BOTTOM_STRIP_DEBUG=1`** (this repo's other new
  diagnostic, `diag/bottom-strip-frame-debug`, if that branch's compositor
  changes are also on this image -- if not, at minimum use
  `tools/card-shell-benchmark.py --board` bracketed around the gesture via
  `card_shell benchmark physical` / `benchmark-stop`, per `nix/card-shell/
  README.md`) to re-check `tracking_present_interval_ms` and
  `frame_update_cpu_ms` against the same budgets as before -- the render/
  present timing story should be materially unchanged by this kernel
  patch (it does not touch render cost or scheduling), so this is mainly
  a sanity check that nothing regressed.

**What a result means:**

- Band gone or clearly reduced on the same real-finger gesture that
  reliably reproduced it before -> supports the driver-side latch-timing
  hypothesis; this patch is a real fix (for at least part of the effect).
- Band unchanged -> the VO hardware's own internal latching was already
  safe regardless of when `VO_REG_LOAD_CTL` is written (i.e. this driver-
  side gap was real but harmless), and the panel-side TE/free-running-scan
  gap (`docs/evidence/flicker-after-headroom-revert.md`) is the dominant
  or sole cause -- that remains open `display/panel` work (consuming the
  RM69A10's TE line), not something this patch can reach.
- Either way, `uname`/console access already proves the kernel booted;
  a normal login and the existing `test_card_shell_state.py`/QEMU suites
  passing (unaffected -- this patch is display-pipeline-only, changes no
  userspace code) rule out this patch having broken anything else on the
  image.

## Narrow proof commands already run (host only, no board access)

- `nix build .#kernel --max-jobs 1 --cores 6`: succeeds (this branch).
- The patch applies cleanly to the pristine pinned kernel source and was
  verified against a byte-identical re-diff before being committed (see
  `docs/evidence/card-shell/bottom-band-flicker/kernel-vblank-latch.md`).

## Why

`a-riscv-nixos-closure-cross-builds` gets an image to a prompt under emulation.
That proves the closure builds; it proves nothing about the board, because
QEMU's `k230` machine loads a kernel directly and the real hardware does not.
On the board a vendored chain runs first — BootROM, U-Boot SPL with its DDR
training blob, U-Boot, then OpenSBI — and only then is anything of ours
loaded.

Until our own image boots on the actual device, every plan after this one is
speculative. This is the change where the project stops being a build exercise.

## What Changes

- **A bootable SD image**, laying our kernel, initrd and rootfs alongside the
  vendored stage 1 so the board's existing chain finds and loads them.
- **The vendored stage-1 firmware is pinned as an artifact**, with its origin
  and how it was obtained recorded. The seam declared in the previous change
  gets filled with something specific.
- **The board reaches a console prompt over `/dev/ttyACM0`**, and the
  transcript is committed. That transcript is the evidence for every hardware
  claim this repository makes afterwards.
- **A flashing procedure that names the target device unambiguously.** The
  development machine has four 8 TB RAID members on `/dev/sd[a-d]`; a `dd` to
  the wrong node is unrecoverable. The procedure uses `/dev/disk/by-id`.
- **The difference between the QEMU boot and the hardware boot is written
  down**, because that gap is where the next failure will live.

- **A kernel that can boot this SoC.** Added after proposing, because the
  plan assumed one already existed. It does not: mainline Linux ships no
  K230 device tree and no `SOC_CANAAN_K230`, so the kernel from the previous
  change has nothing to boot with on this board. We build the Xuantie tree
  Canaan's own Linux SDK pins, from source — not as a vendored binary.

**Non-goals.** The panel, touch, or backlight — the board can boot headless and
the screen is `the-screen-comes-up-under-linux`. Either radio. Building stage 1
from source; it stays vendored. Booting from anything but an SD card.

## Capabilities

### New Capabilities

- `image/boot-chain`: what runs before our kernel, what is vendored, and how
  our kernel is handed control.
- `image/sd-layout`: what is written to the card, where, and how the card is
  produced without endangering the host.
- `system/console`: how a person talks to this board, on hardware.

### Modified Capabilities

- `system/nixos-config`: the system's boot requirement currently speaks only of
  emulation. It gains a hardware obligation, and its stage-1 requirement is
  grounded against a real vendored artifact rather than a boot log from the
  shipped firmware.

## Impact

Adds an SD image derivation and a vendored stage-1 input to the flake. Adds a
flashing script under `tools/`.

**Destroys the contents of the target SD card.** The card currently in use was
previously an EverDrive 64 cartridge card; the procedure this change
establishes must make the target impossible to mistake.

Requires physical access to the board and a **known-good USB-C data cable** —
`docs/findings.md` records that a charge-only cable produces total silence and
a marginal one produces `error -71`, and that both look like a dead board.

## Why

Nobody can say what this board runs. The chain that executes before our kernel
is 570 KB of committed binary, and the honest answer to "what is in it?" is
currently "U-Boot, probably, plus something that trains the memory". A person
who wants to change how the board boots — to get NixOS generations back at the
boot menu, to raise a memory timing, to put a splash on the panel before Linux
starts — cannot, because the thing that would have to change is not a file they
can edit. A person who wants to know what unauditable code runs on their device
cannot be told, because nobody has counted.

Worse, the build that produced those binaries **executed a stripped vendor
executable** to do it. We ran an unreadable 110 KB program from Canaan and
shipped what came out.

Both are fixable, and most of the way more cheaply than anyone assumed. What is
*not* fixable has to be named, once, in a place a future reader can check,
because a blob nobody remembers is indistinguishable from a blob nobody chose.

## What Changes

- **Stage 1 stops being a committed binary and becomes a Nix derivation.** The
  sources are already on disk: U-Boot 2022.10 upstream plus Canaan's rsync
  overlay from `kendryte/k230_linux_sdk`, both open. **BREAKING** against
  `image/boot-chain`, which today requires the opposite.
- **The vendor `k230_priv_gzip` executable leaves the build.** It is GNU gzip
  1.6 with the version string filed off, and nixpkgs `gzip` produces
  byte-identical output; this was measured, not assumed.
- **`docs/blob-inventory.md` lands as a standing artifact**: every opaque
  binary this project ships, executes, or is one defconfig line from pulling
  in, with its sha256, what would make it go away, and whether it is a property
  of this chip, this vendor, this board, or of the industry.
- **A blob that is not in the inventory fails the build.** Flagging that
  depends on someone remembering is not flagging.
- **The DDR PMU training firmware is named as permanent.** It is 32 KiB of
  Synopsys PHY microcode living inside the SPL at offset `0x1fc74`, and
  building U-Boot from source does not remove it — it only means we compile it
  ourselves. The current spec language implies stage 1 is opaque *because* it is
  vendored. It is the other way round: almost all of it is open, and one small
  part of it will never be.

**Non-goals.** Removing the DDR PMU firmware, which is a person-years research
project nobody has completed for any Synopsys PHY. Building the Linux kernel,
the NPU stack, or any radio firmware — those blobs get inventoried, not
excised. Changing the SD layout or the boot command; stage 1 is rebuilt to do
exactly what the committed one does. Reviving RT-Smart. Packaging the Xuantie
toolchain for Nix — the point is to stop needing it.

**Hardware.** Most of this needs no board. Building stage 1 in Nix, proving
gzip equivalence, reproducing the packaging, and the inventory check are all
laptop work, and the first three are already done or nearly so. Exactly one
task needs the board: booting a stage 1 that we compiled, which cannot be
proven any other way because the DDR training runs before there is a console.

## Capabilities

### New Capabilities

- `image/vendor-blobs`: what opaque binaries an image carries or its build
  executes, which of them are unavoidable and why, and how a new one is
  prevented from arriving unnoticed.

### Modified Capabilities

- `image/boot-chain`: its first requirement currently reads "Stage 1 is a
  pinned vendored artifact" and states that stage 1 SHALL NOT be built from
  source by this project. That reverses. The capability also gains the
  obligation to name what stays opaque inside the stage 1 we build.

## Impact

Adds a U-Boot derivation and an OpenSBI derivation to the flake and removes
`firmware/stage1/*.bin` and `firmware/stage1/env.env` from the repository.
Rewrites `nix/stage1.nix`, whose `vendored = true` / `builtFromSource = false`
contract is exactly what this change inverts, and retires `tools/gen-stage1.sh`
and its Docker dependency. Adds `tools/blob-scan.py` and wires it into
`./scripts/build_site.py`.

**This lands on top of `the-board-boots-what-we-built`, which is in flight and
owns `image/boot-chain`.** That capability is not yet in `openspec/specs/`;
the delta here is written against the requirement text in
`openspec/changes/the-board-boots-what-we-built/specs/image/boot-chain/spec.md`
and assumes that change archives first. If it does not, the two must be merged
by hand rather than both applied.

**One correction to something already committed.** `tools/gen-stage1.sh`
reproduces the SDK's `gen_uboot_bin()` but omits the `sed -i -e
"1s/\x08/\x09/"` that `post-image.sh` applies immediately after compression.
That byte is how the SPL is told to use the SoC's hardware decompressor, and
the committed `fn_ug_u-boot.bin` does not carry it, so the board will take the
software path instead. It should still boot. It is not what the vendor ships,
and it was an accident rather than a decision.

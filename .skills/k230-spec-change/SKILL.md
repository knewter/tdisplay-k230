---
name: k230-spec-change
description: House rules for planning work on the T-Display-K230 with OpenSpec — the capability taxonomy, what may ground a requirement on hardware, how QEMU proof differs from hardware proof, and which command proves a task group. Use when proposing, applying, or archiving a change here, when adding a capability, or when deciding what to run before ticking a box.
license: MIT
metadata:
  version: "0.1.0"
---

# Planning a change on this board

All planning happens through OpenSpec. `openspec` is on PATH.

```
openspec/specs/<group>/<capability>/spec.md   what this board does today
openspec/changes/<id>/                        one in-flight change
```

Change ids read as sentences — `the-screen-comes-up-under-linux`, not
`add-panel-driver`. The id says what becomes true.

## The capability taxonomy

Six groups. A change may add a capability inside a group; adding a group is
itself a decision that belongs in a proposal.

| Group | Capabilities | What it covers |
| --- | --- | --- |
| `image/` | `boot-chain`, `sd-layout`, `cross-build` | How an image is produced and what the board loads |
| `system/` | `nixos-config`, `kernel`, `console` | The NixOS closure and getting a prompt |
| `display/` | `panel`, `touch`, `backlight` | Anything a person looks at or presses |
| `radio/` | `wifi`, `lora` | Getting packets off the board |
| `runtime/` | `atomvm`, `dozer-core`, `shell` | What we run on top once it boots |
| `docs/` | `spec-site` | How these specs reach a reader |

Pick by what a person observes, not by which layer changes. A change to how
the panel is reset is `display/panel` even though the work is a device tree
edit. One change may carry deltas for several capabilities.

Never hand-edit `openspec/specs/`. `openspec archive` writes it.

## What grounds a requirement

In this order, and the order is binding:

1. **An observation on the board.** A boot log, a console transcript, a
   photograph of the screen. This project's whole difficulty is that the
   hardware disagrees with the documentation, so what the board did outranks
   what anything says it should do.
2. **Vendor source that has been read.** A driver, a defconfig, a device
   tree — cited by path. `Set_WLAN_Power_On()` being an empty stub is
   grounding; "the RTL8189 is supported" is not.
3. **Nothing else.** Mark it `<!-- UNVERIFIED -->` and move on.

**A datasheet is not grounding.** The RTL8189FTV datasheet says the radio
does 802.11b/g/n; the radio on this board transmitted nothing, because its
enable line is never driven. Marketing pages are worse: one described this
board's Wi-Fi as an ESP32-S3 co-processor, which the schematic contradicts.

Say which side owns it. A requirement met by vendored stage 1 is not a
requirement on the system.

## Proving a task group

Two different claims, and they are not interchangeable.

*Does it build and boot at all?* is answered under QEMU, on a laptop, in a
loop, with no hardware.

*Does it work on the board?* is answered only on the board, and only with the
console output to show for it.

Write the real invocation into `tasks.md`, and say which claim it makes.

| What the group touched | What proves it |
| --- | --- |
| A Nix derivation | `nix build .#<attr>` |
| The system closure cross-builds | `nix build .#nixosConfigurations.k230.config.system.build.toplevel` |
| The image boots at all | `qemu-system-riscv64 -machine k230 ...` — **QEMU proof** |
| The image boots on the board | a console transcript from `/dev/ttyACM0` — **hardware proof** |
| A running board's state | `./tools/msh.py /dev/ttyACM0 --wait=3 "<cmd>"` |
| The panel or touch | a photograph, plus the console log of the probe |
| OpenSpec documents | `openspec validate --all` |

A QEMU boot never proves the panel, the touch controller, the radio, or the
SD layout, because QEMU's `k230` machine models none of them. A task that
claims any of those and cites a QEMU run is wrong.

## Evidence lives in the repo

A boot log pasted into a terminal is gone at the next reflash. Commit it
under `docs/` and cite the path from the requirement. `docs/rtsmart-boot-log.txt`
is the pattern: it is what grounds every claim about the shipped firmware.

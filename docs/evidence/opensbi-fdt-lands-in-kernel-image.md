# OpenSBI copies our device tree into the kernel's .BTF section

2026-09-22. Found while reviewing the `every-blob-is-built-from-source-or-named`
reproduction of the vendor stage 1; proven on the running board.

## The chain, from the files that are actually on the card

U-Boot's `blinux` (`firmware/stage1/tdisplay.env`, identical to the SDK
`default.env`) loads the kernel Image to `0x200000`, our DTB to `0x8400000`,
the initrd to `0x9000000`, and OpenSBI's `fw_jump_add_uboot_head.bin` to
`0x8000000`, then runs `bootm 0x8000000 0x9000000 0x8400000`. The thing
`bootm` boots as "the kernel" is therefore OpenSBI: its legacy uImage header
reads load `0x0`, entry `0x0`, type kernel, name `linux`.

OpenSBI is built for the generic platform with `FW_TEXT_START=0`.
`platform/generic/objects.mk:35` then sets, unconditionally,

    FW_JUMP_FDT_ADDR = FW_TEXT_START + 0x2200000  ->  0x2200000

and `firmware/fw_jump.S:46-52` makes `fw_next_arg1` return that constant
instead of the `a1` U-Boot passed in. `firmware/fw_base.S:391-396`
(`_fdt_reloc_again`) copies the FDT there before jumping to the kernel at
`0x200000`.

`0x2200000` is 32 MiB into a 57 MiB kernel Image. From the running kernel's
System.map (`_start` = Image+0), Image+`0x2000000` is `__stop_notes+0x3875c`,
between `__start_BTF` (Image+`0x1fc78a4`) and `__stop_BTF` (Image+`0x30fef04`):
the `.BTF` section.

## Proof on the board

`/sys/kernel/btf/vmlinux` exposes that section from memory. If the copy
happens, the bytes `0x2000000 - 0x1fc78a4 = 0x3875c` into it must be a
flattened-device-tree header. They are:

    $ dd if=/sys/kernel/btf/vmlinux bs=1 skip=$((0x3875c)) count=16 | od -An -tx1
     d0 0d fe ed 00 01 24 a0 00 00 00 48 00 00 ff 98
                ^^^^^^^^^^^ totalsize 0x124a0 = 74912

74 912 bytes, not the 71 038 of `k230-tdisplay.dtb` on the card, because
`bootm` grows the FDT (chosen/bootargs, alignment) before handing it on.
The BTF blob itself is otherwise intact (magic `9f eb 01 00`, 18 052 704 bytes).

## Why the board boots anyway, and why that is luck

`.BTF` is never read during boot. It is consumed later, for eBPF CO-RE, via
`/sys/kernel/btf/vmlinux` -- and the only visible symptom is the line the
board has been printing every boot:

    Kernel module BTF mismatch detected, BTF debug info may be unavailable for some modules

That is exactly what a vmlinux BTF with 74 KB of device tree in the middle
of it produces. It has been dismissed as noise since the first boot.

The overwrite lands in `.BTF` only because this kernel's `.BTF` happens to
span Image+`0x1fc78a4`..`0x30fef04`. A kernel with smaller text or without
BTF puts `.data` or `.rodata` there instead, and the failure becomes a
crash in an unrelated subsystem with no connection to firmware. The vendor
shipped this layout; nothing in Canaan's SDK acknowledges it.

## The fix belongs in the from-source OpenSBI

Make `fw_next_arg1` pass `a1` through: build with `FW_JUMP_FDT_ADDR`
**undefined** at compile time, so `fw_jump.S` takes its `#else` branch
(`add a0, a1, zero`) and the FDT stays where `bootm` put it, which is
outside every image `bootm` knows about. Verification is a disassembly of
`fw_next_arg1` in the built `fw_jump.elf`, not a boot: the boot proves
nothing here, since it boots either way. A second check is the same `dd`
above returning BTF bytes rather than `d00dfeed` after the change lands.

This is scoped into `every-blob-is-built-from-source-or-named` as a task
because that change owns `nix/opensbi-k230.nix`; it is impossible to fix
against the vendor blob.

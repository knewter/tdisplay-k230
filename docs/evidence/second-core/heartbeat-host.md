# Physical CPU0 heartbeat: host preparation only

Prepared 2026-09-26 America/Chicago; no board release was run for this file.
The working tree was `impl/small-core-heartbeat-20260926` at base
`ba23c967`. `bash tools/test-small-core-heartbeat.sh` passed on the host. With
`SMALL_CORE_OUTPUT_DIR=/tmp/k230-small-core-heartbeat-host`, the generated
80-byte `heartbeat.bin` had SHA-256
`11d675ac6a4993c5ea820603a59778993487a478d07b1e30d3e9545ae22ba133`.
The temporary output is a host artifact, not a committed firmware image.

## Source-backed physical path

The pinned `k230_linux_sdk` revision is
`1104236db4d1e47873bd68924f912747b820228c` (`nix/k230-sdk-src.nix`).
`nix/uboot-k230.nix` copies that U-Boot overlay and uses
`k230_canmv_v3_defconfig`. In its `board/canaan/common/sdk_autoconf.h:16`,
`CONFIG_LINUX_RUN_CORE_ID` is 1. `k230_spl.c:150` loads U-Boot;
`k230_img.c:276-285` releases physical CPU1 into that U-Boot image and parks
physical CPU0 in `wfi`. Thus the normal U-Boot prompt is on physical CPU1,
supported by source and the later RVV/256 KiB L2 Linux observation.

The same overlay's `arch/riscv/cpu/k230/cpu.c:125-166` defines
`boot_baremetal 0`, which writes physical CPU0's vector at `0x91102100`,
asserts/deasserts `CPU0_RST_CTL` at `0x91101004`, and flushes the specified
image range. The built U-Boot ELF in
`/nix/store/zzz867rp8drrwkhibj0rlqc04sk9g7f8-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10`
contains that command (`nm` and a string search). The vendor default
environment and this project's `firmware/stage1/tdisplay.env:29` load a
physical CPU0 bare-metal image at `0x07000000` before that command. This
grounds the scratch load address, not a claim that the new payload has run.

The 80-byte program loads at `0x07000000`. It writes CPU0's read-only
`mhartid` and `misa` CSRs at `0x07002008` and `0x07002010`, and emits the same
monotonic 64-bit counter at `0x07002000`, `0x07003000`, and `0x07004000`.
Those three output pages lie within the vendor's CPU0 bare-metal scratch
range and outside the actual 80-byte file. The program issues `fence rw,rw`
and Canaan U-Boot's documented `l2cache.ciall` encoding (`cache.c:158-161`,
`0x0170000b`) after each update. Each output page is read **once** from the
CPU1 U-Boot prompt, separated in time, to avoid relying on a second read of
a line CPU1 may retain in its own cache. This is a bounded diagnostic
protocol, not a demonstrated CPU-to-CPU coherency contract.

`llvm-objdump` and `readelf` confirmed entry `0x07000000`, the output symbol
at `0x07002000`, scalar RV64 ELF attributes without V, CSR reads, the three
stores, and the L2 maintenance word. The host check proves only layout and
instruction selection. It does not prove that CPU0 starts, that its L2 flush
publishes to CPU1, or that the board's U-Boot reads those pages freshly.

The live Linux memory snapshot collected by the coordinator at
`2026-09-27T03:34:24Z` (`/tmp/k230-core-memory-result.txt`) describes 1 GiB
at `0x00000000..0x3fffffff`, with `0x10000000..0x103fffff` reserved for the
framebuffer and no second-core reservation. It does not reserve these probe
pages for Linux; this first test stays at the U-Boot prompt and ends in a
reset. A Linux-coexistence candidate must use a separate DT reservation and
read-only observer before it can boot.

`python3 -m unittest discover -s tests -p test_ums_target.py` passed 16 host
tests. It proves the UMS helper's refusal guards, not that a disposable card
or a recovery rehearsal was available during this preparation.

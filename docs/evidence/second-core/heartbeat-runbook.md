# Disposable-card physical CPU0 heartbeat runbook

This is a proposed operator procedure. No command below has been executed on
the board for this change. The board operator must hold `/dev/ttyACM0`, have a
separate disposable rollback card, and record the same-session recovery
rehearsal before `boot_baremetal 0`. Keep the known-good card intact. See
`heartbeat-host.md` for source, payload hash, cache limits and memory map.

1. Build the payload on the host and check its hash:

   ```sh
   SMALL_CORE_OUTPUT_DIR=/tmp/k230-small-core-heartbeat-host bash tools/test-small-core-heartbeat.sh
   ```

2. Put that exact `heartbeat.bin` on the disposable card's boot partition as
   `/small-core-heartbeat.bin`. Record its SHA-256 and the card identity. At
   the CPU1 U-Boot prompt, inspect `bdinfo` and confirm the address interval
   `0x07000000..0x07004fff` is free of U-Boot relocation, stack, malloc,
   framebuffer, and currently loaded boot files. Stop if it is not.

3. Rehearse the known-good one-shot or UMS/card-reader recovery route and
   record the recovered boot and hashes in this board session. Then load the
   test image. `ext4load` must report 80 bytes and `fileaddr=0x7000000`:

   ```text
   ext4load mmc 1:1 0x7000000 /small-core-heartbeat.bin
   printenv fileaddr filesize
   ```

   The board's active boot partition may differ from `mmc 1:1`; verify it
   from the current `mmc_boot_dev_num` and partition table before running.
   Never run the release if the size/hash or memory check differs.

4. With the console transcript running, release physical CPU0 using the
   pinned command and read each separate output page once, at least one
   second apart:

   ```text
   boot_baremetal 0 0x7000000 0x5000
   md.l 0x7002000 6
   md.l 0x7003000 2
   md.l 0x7004000 2
   echo CPU1_UBOOT_PROMPT_ALIVE
   ```

   The first page holds counter, `mhartid`, and `misa` as three little-endian
   64-bit words. Decode two 32-bit `md.l` cells per word. Require three
   strictly increasing counter values and a responsive prompt; any static
   value, fault, reset or hang fails this probe. The `mhartid` value directly
   tests the published report that both physical cores report zero.

5. End the bare-metal test with a board reset and restore the normal card or
   rehearsed image. Do **not** run U-Boot `boot` while CPU0 executes from
   `0x07000000`: the normal boot command loads `/bootargs.txt` at that same
   address, overwriting the running payload. Capture the restored Linux CPU
   mask and normal UI/console result separately from the probe result.

This proves at most physical CPU0 execution while physical CPU1 runs U-Boot.
The separate Linux-coexistence stage in
`openspec/changes/the-small-core-runs-a-recoverable-heartbeat/tasks.md`
remains unverified until an experimental SPL/DT and board transcript exist.

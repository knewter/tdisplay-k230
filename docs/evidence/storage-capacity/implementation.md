# Guarded root growth: host and disposable guest proof

The helper derives the mounted root from `findmnt` and sysfs, checks the actual
DOS/512-byte partition table, requires the fixed boot/root starts and boot size,
exactly two Linux partitions, matching kernel/table geometry and the expected
ext4 labels/identities. Its installed CLI has no target-device override.
Read-only preflight is the default; `--apply` owns a runtime lock and gates both
`growpart` and `resize2fs`. A changed identity, failed command or incomplete
postcondition is a failure, not a successful expansion.

The Nix service is wanted by multi-user, after local filesystems and before the
shell, without making shell startup require growth success. It bounds the
operation at 180 seconds and stops its entire control group. Independent stock
partition/filesystem auto-growth is prohibited so it cannot bypass the guard.
The board and RVV configurations include it; the unrelated netboot guest does
not. `configuration.json` records the successful actual Nix evaluation.

```sh
python3 tests/test_root_growth.py
nix build .#root-growth --max-jobs 1 --cores 8 --no-link --print-out-paths
python3 tools/check-root-growth-config.py
```

All 13 host checks pass. They cover refused layouts before writes, tool failures,
post-partition identity changes before filesystem mutation, false success,
interrupted growth/retry, repeat no-op and 1 KiB ext4 page alignment. These are
policy tests, not filesystem or boot proof. The narrow cross-build produces
`/nix/store/6sca423wcjlq1v9ynjpbv4ai48jf53l9-k230-root-growth`.

The package uses only the unmodified `growpart` script from pinned cloud-utils
0.33, with its declared DOS-layout utilities. The first packaging attempt was
stopped because building cloud-utils' split guest output also built unused
QEMU/CD-image tools from its sibling output. The final closure excludes those
tools. Relative to the current board system, the growth helper adds four paths
and approximately 197 KB of NAR data; the integrated system adds about 1.19 MB.
No store deletion is required to stage this system.

## Actual filesystem tests in a RISC-V guest

```sh
python3 tools/test-root-growth.py --qemu --output /tmp/new-root-growth-proof
```

The fixture boots a real RISC-V Linux 6.18.52 kernel with the cross-built helper
and pinned utilities. Its only writable QEMU disk is a new 512 MiB regular file;
no host block device can be supplied. The guest refuses to run outside marked
PID 1. It mounts an actual ext4 test root and invokes the production discovery,
guard and growth logic against that mountpoint.

`qemu/result.json`, `manifest.json`, `serial.log` and `provenance.json` retain the
exact artifacts, fresh run identity, commands, helper hash, comparisons and
limits. Seven cases pass: growth plus repeat, already-full disk, wrong root
label, a later partition, unsupported filesystem, a partition-tool failure,
and retry after partition growth followed by an injected pre-filesystem failure.
The entire firmware gap after the MBR and the complete 112 MiB boot partition
retain their hashes. Root sentinel contents and identities survive. Negative
cases retain the original partition table and complete root-filesystem hash.
The first successful growth increases a 128 MiB filesystem to 393196 KiB;
repeat runs leave the layout unchanged.

The first guest attempt correctly failed its overly strict postcondition: pinned
`resize2fs` rounds the default target down to a system page when filesystem
blocks are smaller. e2fsprogs 1.47.4 `resize/main.c`, the `sys_page_size` and
`new_size` calculation, establishes that rule. A 1 KiB filesystem can therefore
leave 3584 bytes unused on this test partition. The corrected check uses the
larger of page and filesystem block size. Pinned cloud-utils also reserves 33
trailing sectors even for DOS, which the partition postcondition explicitly
allows. `qemu/previous-failure.json` preserves the failed attempt and original
transcript hash; it is not relabeled as passing.

The fixture exercises a mounted disposable filesystem, not production `/` or
NixOS service startup. Failure injection occurs before the named utility runs;
it does not simulate power loss during a metadata write. A normal exit of its
PID 1 produces the expected final kernel panic after the complete report; the
host requires the fresh complete report and every assertion, not that panic.
Physical K230 boot, live root expansion, Wi-Fi/shell recovery, and a second
physical reboot remain unverified. Tasks 1.1, 1.2 and 2.1 are complete. The matching system and compact image
also cross-build successfully; `image-build.json` records artifact hashes,
unchanged initial partition offsets, exact kernel/initrd payloads, valid U-Boot
CRCs and the matching system in bootargs, completing task 2.2. Physical
first/repeat boots, live capacity and recovery remain separate gates.

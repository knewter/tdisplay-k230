# Mainline initrd exec-path audit

Read-only artifact/source audit following the 2026-10-02 `rdinit=/bin/sh`
attempt. No kernel or initrd was rebuilt, and no board or serial port was
used for this audit.

The exact trial artifact remains the mainline DRM bundle
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`
and initrd
`/nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`.
Its kernel source is pinned at upstream Linux
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` in
[`nix/kernel-mainline-src.nix`](../../../../nix/kernel-mainline-src.nix).
Host inspection was run 2026-10-02 06:49 UTC. The compressed initrd is
27,314,033 bytes with SHA-256
`87ac614be6150897f2823990f3439ab8c9cb0ebfecb19af38be1501a17dfb897`.

The archived initrd's `/bin` and `/sbin` resolve through the matching initrd
binary environment. Bash's `sh`, coreutils (`mkdir`, `cat`, `ls`, `sleep`),
util-linux `mount`, e2fsprogs `e2label`/`tune2fs`, and systemd `reboot` are
present there. I checked the exact RISC-V ELF interpreter and each executable's direct `DT_NEEDED`
shared-library name against each executable's embedded RUNPATH and the CPIO
archive: all were present. Thus this artifact audit found no missing dynamic
loader or shared library that explains a child executable failing to start.
The snippet checks direct dependencies, not recursive library dependencies or successful runtime execution. The initrd does not include `blkid` in this binary environment.

This read-only host snippet checks the same executable set against the
archive. It requires `zstd`, `cpio`, `readelf`, and Python 3 and writes no
files:

```sh
python3 - <<'PY'
import os, re, subprocess

initrd = "/nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd"
listing = subprocess.run(
    ["bash", "-lc", 'zstd -dc "$1" | cpio -it 2>/dev/null', "_", initrd],
    check=True, capture_output=True, text=True,
).stdout.splitlines()
members = set(listing)
executables = {
    "bash": "/nix/store/89hsc9vrrk2vr18yp9yrzs365fz490wv-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/bash",
    "coreutils": "/nix/store/3m27x1rrl0wk30lz5fih10cf1dpqbaa6-coreutils-riscv64-unknown-linux-gnu-9.11/bin/coreutils",
    "mount": "/nix/store/wj2ib2qm1znrpv2i8b433v69m07m86ll-util-linux-minimal-riscv64-unknown-linux-gnu-2.42.3-mount/bin/mount",
    "e2label/tune2fs": "/nix/store/8mzskyv8clj8a83y8xkgpaf5x9pmgj09-e2fsprogs-riscv64-unknown-linux-gnu-1.47.4-bin/bin/tune2fs",
    "systemctl/reboot": "/nix/store/srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/bin/systemctl",
}
for name, executable in executables.items():
    missing = [] if executable.lstrip("/") in members else ["executable"]
    dynamic = subprocess.run(["readelf", "-d", executable], check=True,
                             capture_output=True, text=True).stdout
    needed = re.findall(r"Shared library: \[(.*?)\]", dynamic)
    runpath = re.search(r"Library runpath: \[(.*?)\]", dynamic).group(1).split(":")
    missing.extend(soname for soname in needed
                   if not any(os.path.realpath(f"{directory}/{soname}").lstrip("/") in members
                              for directory in runpath))
    program = subprocess.run(["readelf", "-l", executable], check=True,
                             capture_output=True, text=True).stdout
    interpreter = re.search(r"Requesting program interpreter: (.*?)\]", program).group(1)
    if os.path.realpath(interpreter).lstrip("/") not in members:
        missing.append("ELF interpreter: " + interpreter)
    print(name + ": " + ("complete" if not missing else "missing " + ", ".join(missing)))
PY
```

The sanitized physical milestone supplied for the corrected attempt is limited
to: the Linux 7.3-rc5 banner and a standalone `K230_PROC` marker appeared; the
strict fresh RC marker and later probe markers did not. No full command echo,
shell prompt, or observed reboot marker was available. `K230_PROC` is emitted
immediately before the first external `cat` of `/proc/uptime`,
`/proc/interrupts`, `/proc/cmdline`, `/proc/partitions`, and `/proc/mounts`.
The preceding `mkdir`, mount and `test` commands can set the probe's failure
status and still continue to that marker. It therefore proves neither that the
mount checks passed nor that `cat` returned. Without later markers, incomplete
serial input, a child/output issue, or a proc read remain unresolved; this is
not evidence of an IRQ hang.

The smallest useful discriminator for a future authorized retry is a short
fresh-token command bracketed by Bash builtins: emit `PRE`, execute absolute
`/bin/true`, emit its return code, then execute `/bin/cat /proc/uptime` with
its data redirected away from the serial console and emit that return code
and a final token marker. This separates command reception, an external child
exec/return, and the first proc read without reading `/proc/interrupts` or
enumerating devices. It has not been run.

There is also a probe policy issue independent of the observed stall. The
current loop runs `e2label` on every `/dev/mmcblk*p*` and makes any nonzero
result fail the aggregate probe, even when another ext filesystem label is
read successfully. `e2label` is an ext filesystem tool; an unrelated FAT or
other non-ext partition would create a false probe failure. The project image
defines both boot and root filesystems as ext4 (`nix/sd-image.nix:160-172`,
`nix/hardware.nix:143-153`), and U-Boot reads the boot partition with
`ext4load`, but that does not classify every live MMC partition. Treat failed
per-partition label reads as unsupported/unreadable, retain the requirement
for at least one successful ext label read, and report whether any successful
read equals `NIXOS_SD`. The current source has not been changed here.

This audit makes no claim about the physical partition table, whether the
`NIXOS_SD` label is present, whether the corrected shell completed, or whether
the original systemd initrd stall is caused by userspace, storage, interrupts,
or serial output.

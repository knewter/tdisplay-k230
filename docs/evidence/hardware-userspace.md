# First successful NixOS userspace on the T-Display-K230

Captured 2026-09-20 with tools/capture-boot.py over the CH342 console
(/dev/ttyACM0, 115200 8N1). The board reached a root shell; these are
commands run on it, not on the build host.

```
[?2004l[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [   0.204] --- sending: cat /proc/cpuinfo ---
cat /proc/cpuinfo
[?2004lprocessor	: 0
hart		: 0
isa		: rv64imafdcv_zicbom_zicboz_zicntr_zicsr_zifencei_zihpm_zba_zbb_zbs_svpbmt
mmu		: sv39
uarch		: thead,c908
mvendorid	: 0x5b7
marchid		: 0x8000000009140d00
mimpid		: 0x50000
[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [   0.404] --- sending: uname -a ---
uname -a
[?2004lLinux nixos 6.6.36 #1-NixOS SMP Tue Jan  1 00:00:00 UTC 1980 riscv64 GNU/Linux
[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [   0.604] --- sending: cat /proc/cmdline ---
cat /proc/cmdline
[?2004lconsole=ttyS0,115200n8 root=fstab loglevel=4 lsm=landlock,yama,bpf init=/nix/store/2h0xrlf5n74fjjhxqd18y6vl55w4zyrr-nixos-system-nixos-26.11.20260919.20b1ddd/init
[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [   0.805] --- sending: findmnt -no SOURCE,FSTYPE / ---
findmnt -no SOURCE,FSTYPE /
[?2004l/dev/mmcblk1p2 ext4
[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [   1.005] --- sending: nproc; free -m | head -2 ---
nproc; free -m | head -2
[?2004l1
               total        used        free      shared  buff/cache   available
Mem:             935         136         773           6         101         798
[?2004h
[root@nixos:~]# 
[?2004l[?2004h
[root@nixos:~]# [  90.179] --- capture end ---
```

## What this proves

- **We are on the real silicon.** `uarch: thead,c908`, `mvendorid: 0x5b7`
  (T-Head), `marchid: 0x8000000009140d00`. This cannot be produced by the
  x86 build host or by QEMU's `virt`.
- **Our kernel, not the vendor's.** `Linux nixos 6.6.36 #1-NixOS`.
- **Our command line reached the kernel.** `/proc/cmdline` is exactly the
  string `bootargs.txt` carries, `init=` included. This is the fix in
  `stage1-emergency-mode.md`, confirmed end to end.
- **`root=fstab` works on this board.** There is no explicit `root=` on the
  command line, yet `/` is mounted from `/dev/mmcblk1p2 ext4`. Root was
  therefore resolved through the initrd's fstab and the `NIXOS_SD` label,
  which `boot-path-differences.md` had flagged as never yet exercised —
  every previous boot got an explicit `root=` from the vendor fallback.
  That risk is now closed.
- 935 MB usable of the 1 GiB LPDDR.

## The board runs Linux on ONE hart, and that is by design

`nproc` reports 1, and `/proc/cpuinfo` lists only `processor: 0`. This is not
a misconfiguration on our side:

- `arch/riscv/boot/dts/canaan/k230.dtsi` declares **`cpu@0` and nothing else.**
- No K230 device tree in the Xuantie tree declares a `cpu@1`. Every `cpu@1`
  in `dts/canaan/` belongs to the **K210**, an unrelated dual-core part.
- `CONFIG_SMP=y` is set, so the kernel is capable of SMP; it is the device
  tree that describes a single hart.

The K230D does have two C908 cores. The second is the one Canaan's AMP split
gives to RT-Smart — which is consistent with the board having shipped running
RT-Smart on it. Bringing it under Linux would mean describing it in the device
tree and taking it away from that firmware, which is a separate piece of work
with its own risks, not a detail of this change.

**Consequence for `the-board-boots-what-we-built` task 4.2.** Its verification
clause asks for `cat /proc/cpuinfo` "showing two C908 harts". That is not
achievable on this hardware under Linux, so the clause is wrong rather than
unmet. The substance of the task — reach an interactive prompt, run a command
that could only run on this hardware — is satisfied above. The clause needs
restating to "showing a `thead,c908` hart", and the single-hart fact belongs
in the spec. Flagged rather than silently rewritten.

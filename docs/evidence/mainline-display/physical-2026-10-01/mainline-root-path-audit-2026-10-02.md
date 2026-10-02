# Mainline root-path source and artifact audit

Read-only audit on 2026-10-02, completed against repository base
`c5254075e531487af82841b3ae76582e5535f0fb` in
`/home/jadams/tmp/k230-mainline-root-path`, branch `audit/mainline-root-path`.
The only owned path is this note. No board, serial port, build slot, staging,
flash, reboot or kernel build was used. Evidence class: existing committed
physical observations plus new host artifact/source inspection. Mainline
root login and the cause of its absence remain **UNVERIFIED**.

The next useful root discriminator, after the corrected minimal protocol
passes, is one direct ext4-label read from the already observed SD root
partition. This separates late SD/superblock access from systemd/udev label
discovery without repeating the broad proc/device survey. A source-backed
unused-clock hypothesis also merits a controlled comparison if that read
fails or times out; it does not justify an IRQ diagnosis or a source fix yet.

## Exact artifacts and observed boundary

The audited bundle is
`/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-k230-mainline-drm-trial-boot-files`,
system
`/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd`,
and kernel
`/nix/store/i77i3ppi72k9hw0v2xmnhilc3q7rvv50-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
The upstream kernel pin is `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`;
the vendor comparison pin is `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`
([mainline source pin](../../../../nix/kernel-mainline-src.nix),
[vendor source pin](../../../../nix/kernel-src.nix)).

Host SHA-256 inspection at 2026-10-02T15:39:51Z matched the bundle inventory:

| Artifact | SHA-256 |
| --- | --- |
| Kernel `Image` / bundle `Image-mainline-drm` | `befebfd67ea9aa829ace3bfd97d12ced42068ab412b9789221d90028a1328426` |
| Bundle `k230-tdisplay-mainline-drm.dtb` | `91f5d6d7feecdfd28e142040dc8e23807d01001cc456d60b4cb436f617fabba2` |
| Compressed initrd `wpc38h8vcriymblrw07qzg8prd8dp541…/initrd` | `87ac614be6150897f2823990f3439ab8c9cb0ebfecb19af38be1501a17dfb897` |

In [the original serial boot](serial-boot.txt), `mmc1` detects an SDXC card
at 1.986875 seconds, `mmcblk1` at 1.995010, and partitions `p1 p2` at
2.003688. Unused clocks are disabled at 3.241747; `/init` starts at
4.020123. Systemd requests `/dev/disk/by-label/NIXOS_SD` at 5.991894,
and the capture ends after udev starts, around the last timestamp 7.222042.
[The debug boot](serial-diagnostic-boot.txt) also enumerates the card and
partitions before clock cleanup and `/init`, then ends in a partial early
systemd debug message. Neither capture shows a successful root label link,
root ext4 mount, closure activation, switch-root or mainline login.

Those observations establish some SD command/data activity and partition
enumeration, not sustained reads or a usable SD driver. The original result
reports ext4/`NIXOS_SD` and closure-validity checks while staging under the
normal vendor system ([result.json](result.json)); they do not establish
that mainline can later read that filesystem.

The [minimal physical run](minimal-probe-2026-10-02/README.md) from
`d209a062f6826877173a7d2669d99b18c82c6416` received a fresh shell marker
and `/bin/true` returned 0. `/proc/uptime` returned 1 because `/proc` had
not been mounted. The `systemctl` reboot alias refused the request as a
chroot; a reboot receipt marker did not prove a reset. The earlier corrected
survey emitted `K230_PROC` but no complete fresh final RC marker
([exec-path audit](initrd-exec-audit-2026-10-02.md)); its first proc read,
command completion and device results remain unresolved. The first
PATH-broken survey's `NIXOS_SD=false` is invalid device evidence.

The later proc-setup correction has only host proof. Normal recovery is
independently proved by the [latest protected postflight](minimal-probe-recovery-2026-10-02/README.md),
boot ID `64898774-34da-4206-afc6-34508a03258d`, normal vendor 6.6.36,
all eight protected hashes and three active shell services. This audit adds
no physical observation and does not convert any failed diagnostic to a pass.

## Initrd root sequence and utility identity

The exact compressed initrd is
`/nix/store/wpc38h8vcriymblrw07qzg8prd8dp541-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`.
A read-only newc CPIO walk of `zstd -dc` output found its fstab at
`nix/store/74smkncxhwn59qjyk6s75rn9qjvw30kf-initrd-fstab`:

```text
/dev/disk/by-label/NIXOS_SD / ext4 x-initrd.mount 0 1
```

The archived `initrd-find-nixos-closure.service` has
`RequiresMountsFor=/sysroot/nix/store`. Its exact start script
`14ryr1zz8qc76fixhpvf91xjra7vwp6h…/bin/initrd-find-nixos-closure-start`
reads `init=` from `/proc/cmdline`, resolves it inside `/sysroot`, and checks
the closure's `prepare-root`. Activation precedes the switch-root service,
whose override calls `systemctl --no-block switch-root /sysroot "${NEW_INIT}"`.
The bootargs retain `root=fstab` and the exact candidate system's `init=`;
there is no guessed `root=/dev/mmcblk0p2` override.

The archive's `60-persistent-storage.rules` imports `blkid` as a **udev
builtin**, then creates by-label links from `ID_FS_LABEL_ENC`. Absence of a
standalone `/bin/blkid` is therefore not evidence that these rules cannot
discover the root label. Conversely, a direct `rdinit=/bin/sh` boot starts
neither the normal systemd jobs nor udev, so missing by-label links there
would be expected unless a separate udev action was performed.

Use absolute `/bin/...` names in a proposed diagnostic, and set volatile
`PATH=/bin:/sbin`; the bare PID 1 shell does not supply the normal service
environment. The exact archive resolves `/bin` to
`/nix/store/fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env/bin`
and `/sbin` to its `sbin` sibling:

| Entry | Exact utility root / final executable |
| --- | --- |
| `/bin/sh` | `89hsc9vrrk2vr18yp9yrzs365fz490wv-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/sh` → `bash` |
| `/bin/true`, `/bin/cat`, `/bin/mkdir` | `3m27x1rrl0wk30lz5fih10cf1dpqbaa6-coreutils-riscv64-unknown-linux-gnu-9.11/bin/…` |
| `/bin/e2label` | `8mzskyv8clj8a83y8xkgpaf5x9pmgj09-e2fsprogs-riscv64-unknown-linux-gnu-1.47.4-bin/bin/e2label` → `tune2fs` |
| `/bin/mount` | `w5kjkysdcdn9g9q2sb8kznvzyvqhbjj2-util-linux-minimal-riscv64-unknown-linux-gnu-2.42.3-bin/bin/mount` → `/nix/store/wj2ib2qm1znrpv2i8b433v69m07m86ll-util-linux-minimal-riscv64-unknown-linux-gnu-2.42.3-mount/bin/mount` |
| `/bin/udevadm`, `/bin/reboot` | `srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/bin/…` |

Each abbreviated utility root above is under `/nix/store/`. These are archive
identities, not proof of runtime execution beyond the observed `/bin/true`.
The [previous ELF audit](initrd-exec-audit-2026-10-02.md) checked direct
loader/library dependencies. A newly built bundle must have its own initrd,
symlinks and utility membership re-inspected rather than inherit these roots.

The separate kernel dev/config store outputs are absent on this host now.
The exact `Image` nevertheless contains an embedded gzip `.config`, bracketed
by `IKCFG_ST` (byte offset 21133232) and `IKCFG_ED`. Reading that section
without executing or rebuilding the kernel confirms:

```text
CONFIG_MMC=y
CONFIG_MMC_BLOCK=y
CONFIG_MMC_SDHCI=y
CONFIG_MMC_SDHCI_PLTFM=y
CONFIG_MMC_SDHCI_OF_DWCMSHC_KENDRYTE=y
CONFIG_EXT4_FS=y
CONFIG_JBD2=y
CONFIG_RISCV_DMA_NONCOHERENT=y
CONFIG_RISCV_ISA_ZICBOM=y
CONFIG_ERRATA_THEAD_CMO=y
```

Missing ext4/MMC initrd modules are not a supported explanation for this exact
image: the relevant drivers are built in. These selections do not prove
filesystem or DMA correctness on the board.

## DT, driver and clock comparison

The vendor source read locally is
`/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source`, at the repository's
vendor pin. Its `drivers/mmc/host/sdhci-of-kendryte.c` differs from the
[local forward port](../../../../nix/patches/mainline/sdhci-of-kendryte.c)
only in removal of obsolete `sdhci_pltfm_free()` calls/error labels and the
`.remove` callback's return type. PHY choice, ADMA splitting, SD clock
calculation, fixed controller writes and successful probe path are retained.
The mainline generic MMC/SDHCI core is a different version; this comparison
does not establish equivalent runtime behavior.

`fdtget` of the exact trial DTB confirms SD1 address `0x91581000`, interrupt
144 level-high, four-bit bus, 50 MHz maximum, `no-1-8-v`,
`cap-sd-highspeed`, and `dma-noncoherent`, matching the vendor SD1 node and
the shipped board overrides. Both SoC DTs describe the same PLIC base
`0xf00000000`, 208 sources, two interrupt cells, and hart-0 machine/supervisor
external contexts 11 and 9. See the pinned
[mainline SoC DTS](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/boot/dts/canaan/k230.dtsi)
and vendor `arch/riscv/boot/dts/canaan/k230.dtsi`. Linux's allocated virtual
IRQ numbers printed by drivers need not equal DT source IDs. This audit
finds no DT address/source/context mismatch for SD1 and does not prove the
entire interrupt path works.

Clock ownership differs materially. Vendor SD1 consumes two fixed 100 MHz
`dummy_sd` clocks. The [mainline board source](../../../../nix/dts/k230-tdisplay-mainline.dts)
consumes real `K230_HS_SD1_BASE_GATE` (ID 31) as `core` and
`K230_HS_SD1_AHB_GATE` (ID 13) as `bus`. In pinned
[mainline `drivers/clk/clk-k230.c`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/clk/clk-k230.c),
the separate SD1 AXI, card and timer gates use ordinary `clk_gate_ops` and
flags 0, with neither `CLK_IGNORE_UNUSED` nor `CLK_IS_CRITICAL`. All are
registered. Those three gates have no consumer in this trial DT/ported SD
driver. Vendor `k230_clock_provider.dtsi` maps the corresponding SD1 gates
at clock-register offset `0x18`: AHB bit 3, AXI bit 17, base bit 18, card
bit 19 and timer bit 20, matching mainline's gate definitions.

The vendor clock driver additionally calls `clk_prepare_enable(hw->clk)`
from `k230_clk_composite_init()` when the hardware gate was already enabled
(`drivers/clk/clk-k230.c:538-547`), adopting firmware state into software
enable counts. Mainline's ordinary gate definitions have no equivalent
adoption. Thus a firmware-enabled, unconsumed SD gate can become eligible
for mainline unused-clock cleanup after enumeration. The physical logs place
that cleanup between partition detection and `/init`. **Inference only:**
missing clock consumers could break later SD I/O. No gate state, disable
event for a particular gate, or failing late SD request was measured.
Display slowness or missing UART lines do not supply that proof.

## Ranked bounded probes, not performed

All steps below require an exclusive board operator, fresh protected-normal
preflight, exact bundle load counts/CRCs and the unchanged normal recovery
selection. They are successive gates, not one long command. A fresh token
must bracket each child with builtin `printf` receipt and RC lines; echoed,
stale, duplicate or partial markers are not results. Preserve raw UART only
in the designated mode-0700 private directory and publish safe token/RC/
match fields. Do not dump cmdline, all interrupts, mount contents or labels
from unrelated partitions.

1. **Corrected minimal protocol.** Run the existing prepared operator command
   `python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal` only after
   the coordinator has reviewed its recovery path. It mounts `/proc` with
   separately accepted mkdir/mount RCs before `/bin/cat /proc/uptime`, and
   checks `/bin/true`. Successful proc mount and uptime return distinguish
   the prior missing-proc defect from a repeatable child/proc failure. The
   current correction has not been physically run. If it fails, stop here;
   a label result would not be interpretable. The existing minimal mode then
   attempts recovery; a future label mode must reuse these gates within its
   own trial before adding the label child, rather than send a label command
   after the minimal controller has exited.
2. **One direct label read.** After minimal success, create/mount `/dev`
   as devtmpfs with separately accepted RCs if it is not already mounted,
   then use builtin `test -b /dev/mmcblk1p2` before one
   `/bin/e2label /dev/mmcblk1p2`. This device is selected from the committed
   candidate enumeration and staged root layout, not guessed enumeration.
   Publish `RC` and an exact-equality boolean for `NIXOS_SD`, suppressing
   the label and stderr from public output. RC 0 plus a match establishes a
   direct root-superblock read at that instant, bypassing udev. A returned
   nonmatch directs attention to root identity; a nonzero RC needs its
   privately inspected error to distinguish metadata/tool/I/O failures.
   A timeout locates the boundary at device access without identifying
   clocks, DMA or IRQs. Missing devtmpfs/node is a distinct result. Do not
   invoke e2label with a second argument: that would change the label.
3. **Conditional unused-clock comparison.** If the minimal protocol passes
   but the direct label read fails or times out, compare that same payload
   with exactly one additional volatile boot argument, `clk_ignore_unused`.
   Keep the kernel/DTB/initrd/system and all other arguments identical within
   the pair. No kernel rebuild or register access is needed for this switch.
   A repeated transition from failed late read to successful label read
   supports an unused-clock dependency, but the global switch cannot identify
   the particular gate and also affects other clocks. No improvement does
   not exclude a different clock/driver problem. This is a diagnostic option,
   not a proposed permanent boot policy. If a restart port changes the
   bundle first, establish both sides with that new exact bundle rather
   than treat this original run as its control.
4. **Read-only root mount, then one closure path.** If direct label reading
   succeeds, separately create an empty `/sysroot` and run
   `/bin/mount -t ext4 -o ro,noload /dev/mmcblk1p2 /sysroot`, with a fresh
   return marker. `noload` avoids journal replay; a dirty filesystem can make
   this diagnostic mount incomplete, so preserve the exact error and limits.
   On success, use builtin `test -x` on the exact candidate's
   `/sysroot/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd/init`
   and `prepare-root`, with separate markers. This distinguishes direct
   filesystem/closure lookup from the earlier udev label step. It does not
   exercise NixOS activation or switch-root and cannot prove login. If these
   pass but normal `/init` still fails, the next scope is a bounded
   systemd/udev/activation discriminator, not further low-level SD guesses.

For a controller's proposed label payload, after independently accepted
devtmpfs/node gates, the shell fragment is:

```sh
export PATH=/bin:/sbin
printf 'K230_LABEL_PRE FRESH_TOKEN\n'
_k230_label=$(/bin/e2label /dev/mmcblk1p2 2>/dev/null)
_k230_rc=$?; _k230_match=0
test "$_k230_label" = NIXOS_SD && _k230_match=1
printf 'K230_LABEL_END FRESH_TOKEN RC=%s MATCH=%s\n' "$_k230_rc" "$_k230_match"
```

This is a reviewable unrun payload, not an implemented `--mode label` command.
For a new bundle, replace the selected closure path and recheck its initrd
utilities. Retain the external controller's 60-second marker bound and at
most its established receipt retries; do not retry child commands after a
missing final marker. A host timeout stops observation, not a blocked kernel
I/O request. Do not send more survey input or exit the PID 1 shell after
that boundary. Recovery must keep the board reservation until a real reset
and protected postflight prove a new normal boot. The original mainline
bundle's reset path is independently unresolved
([restart audit](mainline-restart-source-audit-2026-10-02.md)); mounted proc
only clears the userspace chroot guard. Physical power-cycle availability or
a separately reviewed and physically proved restart mechanism is required
before depending on automatic recovery. The normal-login recovery deadline
must remain bounded at 180 seconds, followed by explicit failed/pending
recovery status rather than a success inferred from a reboot marker.

## Host checks and remaining gate

The read-only checks were: `sha256sum` for the exact Image/DTB/initrd;
`fdtget` for SD1/PLIC properties; a Python newc walk of `zstd -dc` output
for fstab, units, rules and utility symlinks; a Python gzip decode of the
Image's `IKCFG_ST`/`IKCFG_ED` section; and `diff -u` of the pinned vendor SD
driver against the local forward port (expected difference, exit 1).
Pinned mainline SoC/clock/binding files were read directly from upstream
at the exact commit. These commands passed their stated artifact/source
checks and produced no new runtime evidence. No private UART log was read
or copied for this audit.

The novel embedded-config check is reproducible without a kernel dev output:

```sh
python3 - <<'PY'
import gzip
from pathlib import Path
p = Path('/nix/store/i77i3ppi72k9hw0v2xmnhilc3q7rvv50-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/Image')
d = p.read_bytes()
start = d.index(b'IKCFG_ST') + 8
end = d.index(b'IKCFG_ED', start)
c = gzip.decompress(d[start:end]).decode()
keys = ('MMC', 'MMC_BLOCK', 'MMC_SDHCI', 'MMC_SDHCI_PLTFM',
        'MMC_SDHCI_OF_DWCMSHC_KENDRYTE', 'EXT4_FS', 'JBD2',
        'RISCV_DMA_NONCOHERENT', 'RISCV_ISA_ZICBOM', 'ERRATA_THEAD_CMO')
for key in keys:
    line = next(x for x in c.splitlines() if x.startswith('CONFIG_' + key + '='))
    assert line.endswith('=y'), line
    print(line)
PY
```

`python3 tools/work-status.py` was run at start and again before handoff;
it only reads cached Git state. The document's final narrow checks are
`git diff --check` and `openspec validate the-board-runs-a-mainline-kernel --strict`;
both passed. All relative evidence/source links resolve on the host.
Root login, deliberate glass touch, and the next diagnostic's complete
markers plus normal restoration remain physical gates. Task 5b.5 remains
open. Review, merge and push of this note belong to the coordinator; no
deployment, archive or board acceptance is claimed here.

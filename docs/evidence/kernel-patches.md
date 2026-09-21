# What this project carries on top of the pinned kernel

Required by the `system/kernel` requirement: *"every patch this project
carries on top SHALL be recorded with what it does and why it is needed"*, and
*"so a later kernel bump can tell whether it is still required"*.

**Pin:** `ruyisdk/linux-xuantie-kernel` at
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` (6.6.36), `k230_defconfig`. This is
the revision and defconfig `k230_canmv_v3_defconfig` builds in
`kendryte/k230_linux_sdk`. Why not mainline: `docs/evidence/why-xuantie-kernel.txt`.

Everything below lives in `nix/kernel.nix`. All of it is applied through
`applyPatches` on `src`, **not** through the derivation's `postPatch` —
`buildLinux` does not forward `postPatch`, so setting it there is a silent
no-op that returns the same store path with none of the changes applied. That
cost a debugging cycle and was only caught because the derivation hash did not
change.

## 1. Three device trees the vendor Makefile omits

| Added to `arch/riscv/boot/dts/canaan/Makefile` | Why |
| --- | --- |
| `k230-canmv-v3.dtb` | The reference board's DTB. The vendor Makefile genuinely does not list it, so the tree cannot build the board its own defconfig is named after. |
| `k230-canmv-v3-lcd.dtb` | The reference board's LCD variant, kept as the comparison point for our divergence record. |
| `k230-tdisplay.dtb` | This board. |

**Drop when:** upstream lists the first two itself. The third is ours forever.

## 2. This board's device tree

`nix/dts/k230-tdisplay.dts` and `nix/dts/display-rm69a10-568x1232.dtsi`,
copied into `arch/riscv/boot/dts/canaan/`.

Configuration rather than a code patch: `panel-canaan-universal` is already in
the pinned tree and is driven entirely from the device tree, so the RM69A10 is
described rather than coded. Divergences from the `k230-canmv-v3-lcd`
reference — which describes a different panel, an ST7701 at 480x800 — are
recorded in `docs/evidence/dts-divergence.md`.

**Drop when:** never, unless the board is upstreamed.

## 3. `goodix_berlin`, backported from v6.12

Source in `nix/patches/goodix-berlin/`, copied into
`drivers/input/touchscreen/`, with a Kconfig and Makefile stanza appended.

The pinned 6.6 tree has only the older GT9xx `goodix.c`, which does not speak
the Berlin protocol at all. **This driver does not match the GT9895 upstream
either** — see `gt9895-touch.md`; mainline has no GT9895 support at any
version. The device tree therefore declares `"goodix,gt9895", "goodix,gt9916"`
so the backport can attach via the fallback. Whether a GT9895 answers the
Berlin protocol is an open experiment, not an established fact.

One edit to the backported source:

```
sed -i 's|#include <linux/unaligned.h>|#include <asm/unaligned.h>|'
```

v6.12 moved `asm/unaligned.h` to `linux/unaligned.h`; 6.6 predates the move.

**Drop when:** the pinned kernel reaches a version that carries
`goodix_berlin` itself (v6.12+). The `unaligned.h` sed drops at the same time.
If the experiment fails, this whole item is replaced by a port of LilyGO's
RT-Smart `gt9895.c` instead.

## 4. `autoModules = false`

Not a patch, but it changes what is built and belongs in this record.

nixpkgs defaults `autoModules` to true, which enables every module it can on
top of the defconfig. Against a vendor tree that is actively harmful: it turns
on drivers the vendor never compiles and whose bugs have therefore never been
hit. The first build died in `drivers/rpmsg/th1520_rpmsg.c` with `redefinition
of init_module` — a driver for the **TH1520**, an unrelated SoC that
`k230_defconfig` does not enable. Greybus was compiling too.

`RPMSG_TH1520` is additionally forced off with `lib.mkForce no`.

**Drop when:** never, while building against a vendor tree.

## 5. Config that NixOS needs and a vendor defconfig does not set

`DEVTMPFS`, `DEVTMPFS_MOUNT`, `CGROUPS`, `INOTIFY_USER`, `SIGNALFD`,
`TIMERFD`, `EPOLL`, `NET`, `SYSFS`, `PROC_FS`, `FHANDLE`,
`CRYPTO_USER_API_HASH`, `CRYPTO_HMAC`, `CRYPTO_SHA256`, `TMPFS`,
`TMPFS_POSIX_ACL`, `SECCOMP`, `BLK_DEV_INITRD`, `RD_GZIP`, `RD_ZSTD`.

systemd refuses to boot without most of these, and the failure mode is an
initrd panic that says nothing about the real cause.

`TOUCHSCREEN_GOODIX_BERLIN_CORE` and `..._I2C` turn on item 3.

**Drop when:** never, while running NixOS.

## Not carried, and worth knowing

- **No patch for the panel driver.** `panel-canaan-universal` is stock.
- **No patch for thermal.** `canaan_thermal` is stock and built in, and its
  limitation — a tripless zone, so temperature is readable but nothing acts
  on it — is a property of the vendor driver, not of anything we changed.
  See `docs/thermal.md`.
- **No SMP patch.** Linux runs on one hart here because no K230 device tree
  declares a `cpu@1`. See `hardware-userspace.md`.

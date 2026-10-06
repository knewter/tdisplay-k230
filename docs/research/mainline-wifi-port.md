# Making Wi-Fi possible under the mainline kernel (task 6.1)

openspec/changes/the-mainline-shell-reaches-parity, task 6.1: "Enable
`mmc_sd0` SDIO with owned clocks in the mainline DT and build the RTL8189FTV
module against the mainline kernel. Host proof: `nix build` of the module
for the mainline kernel, or a committed failure log with a successor task."

Worktree `~/tmp/k230-mainline-wifi`, branch `feat/mainline-wifi`, base
`change/mainline-shell-parity` (`5fc50df8`). No board, `/dev/ttyACM0` or
`/tmp/k230-nix-build.lock`/`/tmp/k230-board.lock` access was used; no full
kernel or system `nix build` was run. No Wi-Fi SSID, password or other
credential appears anywhere in this change.

**Follow-up (cfg80211_ops port):** worktree `~/tmp/k230-mainline-wifi-cfg80211`,
branch `feat/mainline-wifi-cfg80211`, base `change/mainline-shell-parity`
(`9f8459b4`, the merge that landed the work below). Same exclusions apply
(no board/`ttyACM0`/build-lock access, no credential of any kind). This
follow-up completes the `cfg80211_ops` port and the strncpy closure flagged
as remaining work in section 3 below.

## What landed

### 1. `&mmc_sd0` SDIO enablement in the mainline DT(s)

`nix/dts/k230-tdisplay-mainline.dts`:

- `&mmc_sd0`'s base node: `status = "okay"` (was `"disabled"`), plus the
  vendor board's own SDIO tuning (`no-1-8-v`, `rx_delay_line = <0x0d>`,
  `tx_delay_line = <0xc0>`, byte-identical to `nix/dts/k230-tdisplay.dts`'s
  own `&mmc_sd0` override, grounding tier 2: vendor source read directly).
  Only the two clocks this node already named (`core`/`bus` ->
  `K230_HS_SD0_BASE_GATE`/`K230_HS_SD0_AHB_GATE`) are claimed at this level,
  mirroring how `&mmc_sd1` is enabled in this same file with only its own
  two base clocks.
- Three standard mmc-core properties NOT present in the vendor source --
  `non-removable`, `cap-sdio-irq`, `keep-power-in-suspend` -- added because
  this board wires no card-detect or Wi-Fi power/reset GPIO for this
  function (grep-confirmed absent from `nix/dts/k230-tdisplay.dts`), and
  mainline's generic SDHCI/mmc core (unlike the vendor's own driver) will
  otherwise expect a card-detect line for a non-fixed slot. UNVERIFIED
  against a booted board.
- The `mmc0 = &mmc_sd0;` alias comment updated from "not enabled by this
  file" to reflect the new status.

`nix/dts/k230-tdisplay-mainline-drm.dts`:

- A new `&mmc_sd0` override claiming the three extra clocks
  (`K230_HS_SD0_AXI_GATE`, `K230_HS_SD0_CARD_GATE`, `K230_HS_SD0_TIMER_GATE`)
  with `clock-names = "core", "bus", "axi", "block", "timer"`, an exact
  mirror of the existing `&mmc_sd1` five-clock override already in this
  file. This is deliberately **only** in the DRM DTS, not the console one,
  because `nix/patches/mainline/k230-sdhci-clocks.patch`'s
  `dwcmshc_probe()`/`devm_clk_bulk_get()` path -- confirmed instance-generic,
  not SD1-specific, by reading the patch itself -- is only applied to the
  kernel these DRM-DT Image+DTB pairs boot
  (`nix/kernel-mainline-drm.nix`'s own `patches` list); the plain console
  kernel's unpatched driver only ever calls `devm_clk_get()` for
  `"core"`/`"bus"`, so giving `&mmc_sd0` five clock entries there would add
  three phandle references the driver never requests -- harmless, but not
  the pattern this file follows for SD1 either.

Validated by preprocessing + compiling both DTS files with `cpp`+`dtc`
against the pinned mainline v7.3-rc5 research source's own
`scripts/dtc/include-prefixes` (same method as
`docs/evidence/mainline-audio-port/dtc-validate.json`; exact commands and
resolved clock-ID numeric checks in
`docs/evidence/mainline-wifi-port/dtc-validate.json`). Both DTBs round-trip
(`dtc -I dtb -O dts` succeeds) and the resolved `&mmc_sd0` clock cells match
`K230_HS_SD0_{BASE,AHB,AXI,CARD,TIMER}_GATE` = 30/12/28/25/34 exactly, the
same IDs this project's own prior research
(`docs/research/k230-clock-gates-vendor-vs-mainline.md`,
`docs/research/mainline-sd1-clock-consumers-2026-10-02.md`) already recorded
for the parallel SD1 gates. `nix build .#deviceTreeMainline`/
`.#deviceTreeMainlineDrm` was not run (not needed; host dtc+cpp already gave
a clean compile, same as the audio task's own note).

### 2. RTL8189FTV module compile attempt against the mainline kernel

Driver source: `nix/hardware.nix`'s `k230WifiDriver` already resolves to
`nix/k230-wifi-driver.nix`, which fetches
`jwrdegoede/rtl8189ES_linux@94cc959d56c1425fbca4f6e49e949cf58ec5dc8d` (no
`nix eval`/store inspection needed; the pin was already visible in that
file). Fetched the identical rev directly via `git clone --depth 1` for a
scratch out-of-tree build (network; this is a public, unauthenticated
GitHub clone, not a board or build-lock resource).

Built against `/nix/store/yz7s78rqdx216bk2kj27q8d9qsi2dap4-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`
(the same dev tree cited in this task's brief) with:

```
make \
  KSRC=<dev-tree>/lib/modules/7.3.0-rc5/build \
  ARCH=riscv \
  CROSS_COMPILE=<riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0>/bin/riscv64-unknown-linux-gnu-
```

(the driver's own top-level `modules` target, not a direct `-C <build>
M=<src> modules` call -- see
`docs/evidence/mainline-wifi-port/module-compile.json` for why the direct
form silently builds nothing).

Found and fixed four distinct, real v7.3-rc5 API-drift classes, each as a
small, clearly-commented change, collected in one patch file,
`nix/patches/mainline/rtl8189fs-mainline-v7.3-rc5.patch` (verified to apply
cleanly with `patch -p1` against a second, independent fresh clone of the
same pinned rev, and to reproduce the identical remaining error set --
same count, same classes):

1. **`Makefile`** -- mainline v7.3-rc5 removed `EXTRA_CFLAGS`/
   `EXTRA_LDFLAGS` support from `scripts/Makefile.build` entirely (grep
   confirms zero references at this pin). Added `ccflags-y +=
   $(EXTRA_CFLAGS)` / `ldflags-y += $(EXTRA_LDFLAGS)`, placed after every
   `*.mk` include (`hal/phydm/phydm.mk` adds its own `-I` flag there) and
   the full object list, so the fully-accumulated value is captured.
2. **`include/osdep_service_linux.h`** -- `from_timer()` and
   `del_timer_sync()` were renamed to `timer_container_of()` and
   `timer_delete_sync()` (confirmed directly against
   `include/linux/timer.h`; the old names do not exist anywhere in that
   tree's headers). Added two `#ifndef`-guarded compat macros, a no-op on
   any kernel that still has the old names.
3. **`core/rtw_br_ext.c`** -- mainline's `include/uapi/linux/if_pppox.h`
   restricts `struct pppoe_hdr`'s `tag[]` and `struct pppoe_tag`'s
   `tag_data[]` flexible-array members to userspace only (`#ifndef
   __KERNEL__`), so neither field exists when this file is compiled as a
   kernel module. Replaced all 8 call sites with pointer-one-past-the-fixed-header
   arithmetic (a flexible array member contributes 0 to `sizeof()`, so this
   is exactly equivalent, not a behavior change).
4. **`os_dep/linux/ioctl_linux.c`, `os_dep/linux/os_intfs.c`** --
   `strncpy()`'s declaration was dropped from `include/linux/string.h`
   entirely (no declaration, no `Module.symvers` export at this pin).
   Renamed to `strscpy()` with the same explicit size at the one call site
   in each file that was gating earlier progress.

**Not exhaustive**: `strncpy` is used at roughly 25 more call sites across
`hal/hal_com.c`, `hal/hal_com_phycfg.c`, `hal/hal_hci/hal_sdio.c`,
`hal/phydm/phydm_debug.c`, `core/rtw_debug.c`, `core/rtw_wlan_util.c`,
`os_dep/linux/rtw_cfgvendor.c`, `os_dep/linux/ioctl_cfg80211.c`, and one
more site each in the two files above. These are the same class of fix
(rename to `strscpy`) but were not closed one by one once the real blocker
below was confirmed independent of them -- fixing every remaining site
would not get the module further.

With that first patch applied, 51 of 57 translation units compiled cleanly;
6 failed (`hal/hal_com.o`, `hal/hal_com_phycfg.o`,
`os_dep/linux/ioctl_cfg80211.o`, `os_dep/linux/ioctl_linux.o`,
`os_dep/linux/os_intfs.o`, `os_dep/linux/rtw_cfgvendor.o`). The follow-up
below (section 3) closes all of these.

### 3. The cfg80211_ops port and remaining strncpy closures (follow-up, completed)

The original attempt stopped at two independent, well-identified problems
(per this task's own "stop and document if it needs deeper rework"
instruction): a `CONFIG_CFG80211` Kconfig gap, and a real `cfg80211_ops`
port (not a rename). This follow-up closes both, plus the remaining
error-causing `strncpy` sites, in the same one patch file.

**The Kconfig gap** was already staged as `CFG80211 = module;` in
`nix/kernel-mainline.nix`'s `structuredExtraConfig` by the original attempt
(still **UNVERIFIED** against an actual kernel build at the time this
section was written -- see "Compile verification" below for how this
follow-up closed that gap for the host build, independent of the live
coordinator kernel build).

**The `cfg80211_ops` port.** Working from the pinned mainline v7.3-rc5
research source's own `include/net/cfg80211.h` and `net/wireless/*.c`
(`/nix/store/79yd40jv8h4x866bm1vyw94cm948grax-linux-mainline-k230-init-exec-transition-src`,
read-only, never executed) rather than guessing from the driver's own
version-gated branches, each mismatch turned out to be one of three
distinct shapes, not a uniform "add wireless_dev" rule:

1. **`struct net_device *` -> `struct wireless_dev *` parameter**, with the
   callback's existing body re-pointed via a new
   `struct net_device *ndev = wdev->netdev;` local declared first, so the
   rest of each function (already written entirely in terms of `ndev`) is
   untouched. Applies to `add_key`, `get_key`, `del_key`,
   `set_default_mgmt_key`, `get_station`, `add_station`, `del_station`,
   `change_station`, `dump_station` (9 callbacks). Two call sites to
   `cfg80211_new_sta()`/`cfg80211_del_sta()` outside the ops table (in
   `rtw_cfg80211_indicate_sta_assoc()`/`_disassoc()`, and inside
   `cfg80211_rtw_add_station()`'s mesh branch) took the same first-argument
   change, using `padapter->rtw_wdev` (always valid, unlike the `pwdev`
   local that's only declared in one `#if` branch) or the now-available
   `wdev` parameter directly.
   - **Confirmed unchanged, explicitly checked and left alone**:
     `change_virtual_intf`, `set_default_key`, `connect`, `disconnect`,
     `join_ibss`, `leave_ibss`, `set_power_mgmt`, `set_pmksa`/`del_pmksa`/
     `flush_pmksa`, `change_bss`, `set_txq_params`, `set_monitor_channel`,
     all mesh/mpath ops, `update_ft_ies`, `tdls_oper`, `sched_scan_start`/
     `_stop` -- mainline's header still declares every one of these with
     `struct net_device *dev` at this pin; the driver's existing code for
     these was already correct and any "convert everything to wdev"
     shortcut would have broken them.
2. **A new leading/trailing parameter, no pointer-type change.**
   `set_wiphy_params` gained a leading `int radio_idx` ahead of `changed`;
   `set_tx_power` gained `int radio_idx` after `wdev`; `get_tx_power`
   gained `int radio_idx, unsigned int link_id` after `wdev` (all three are
   part of cfg80211's multi-radio-per-wiphy support). All three callback
   bodies are pre-existing `#if 0`'d-out stubs that return a fixed value,
   so the new parameters are simply added to the signature and never read
   -- nothing to wire up.
3. **`u64 *cookie` (driver-generated, out-parameter) -> `u64 cookie`
   (cfg80211-generated, in-parameter).** `remain_on_channel` and `mgmt_tx`
   both changed this way. Confirmed by reading
   `net/wireless/nl80211.c`'s `nl80211_tx_mgmt()` at this pin: it now calls
   `cfg80211_assign_cookie(rdev)` itself and passes the result down through
   `rdev_mgmt_tx()` to the driver's `ops->mgmt_tx()`, rather than asking the
   driver to mint one and hand it back. Fixed by deleting the driver's own
   cookie-generation line in each function (`pcfg80211_wdinfo->ro_ch_cookie_gen`
   atomic counter and `pwdev_priv->mgmt_tx_cookie` counter respectively --
   both struct fields are left in place but no longer read, since removing
   them from their owning structs is out of this patch's scope) and
   replacing every remaining `*cookie` read with plain `cookie`.
   `remain_on_channel` also gained a trailing `const u8 *rx_addr` parameter
   (RX-filtered remain-on-channel) that this driver doesn't use. This exact
   shape -- cookie ownership moving from driver to core -- is the same
   change rtl8xxxu and brcmfmac each went through at the equivalent point in
   their own histories; `cfg80211_mgmt_tx_status()`/`cfg80211_ready_on_channel()`
   (the notify-back calls) were already, and remain, by-value `u64 cookie`.

   `update_mgmt_frame_registrations` (`cfg80211_rtw_mgmt_frame_register()`)
   and `del_virtual_intf`/`add_virtual_intf`/`change_virtual_intf` were
   checked and found **already correct**: the driver's own
   `LINUX_VERSION_CODE >= KERNEL_VERSION(5, 8, 0)` branch already used
   `struct wireless_dev *wdev` and `struct mgmt_frame_regs *upd` -- a prior
   upstream driver maintainer had already carried these forward correctly;
   no patch needed.

**The strncpy closures.** Of the ~25 remaining call sites the original
attempt listed as known-but-unfixed, exactly 11 across 6 files were live
code reachable under this driver's default Kconfig and therefore real
compile errors (`hal/hal_com.c`, `hal/hal_com_phycfg.c` x3,
`hal/hal_hci/hal_sdio.c` x2, `hal/phydm/phydm_debug.c` x1,
`os_dep/linux/ioctl_cfg80211.c` x2, `os_dep/linux/ioctl_linux.c` x2 -- each
a straight `strncpy(dst, src, n)` -> `strscpy(dst, src, n)` rename, same
explicit-size, no return-value use at any site, same "strscpy always
NUL-terminates, never zero-pads" caveat as the two sites the original patch
already fixed). The rest were deliberately **left untouched** because they
are not errors or warnings under this exact build: one `phydm_debug.c` site
sits inside `#if 0` dead code; two `rtw_cfgvendor.c` sites sit behind
`#ifdef CONFIG_RTW_CFGVENDOR_WIFI_LOGGER`, not defined by this Kconfig; and
`core/rtw_debug.c`/`core/rtw_wlan_util.c` aren't compiled into this module
at all under this config (confirmed by their absence from the `CC [M]`
build log, not inferred).

### Compile verification

Two independent full rebuilds confirm the patch: once against a private
scratch copy of this task's own dev tree
(`/nix/store/yz7s78rqdx216bk2kj27q8d9qsi2dap4-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`,
copied writable to `/tmp` since the Nix store path itself is read-only, with
`CONFIG_CFG80211=m` added directly to that copy's `.config` and
`include/generated/autoconf.h` -- the dev tree's own self-referential
`lib/modules/<ver>/build/Makefile` had to be repointed from the original
store path to the scratch copy's own `source/` directory, or edits to the
copy were silently ignored), and once more from a second, fully independent
fresh clone of the pinned driver rev with the regenerated patch applied by
`patch -p1`. Both reproduce the identical result:

- **0 compile errors** (down from 6 failing objects before this follow-up).
- The combined patch's full object/module build reaches `LD [M] 8189fs.o`
  (a complete, linked, 5 MB RISC-V relocatable ELF object covering every
  translation unit in the module) before failing at `MODPOST`, with
  `ERROR: modpost: 8189fs.ko: symbol '<name>' undefined!` for ~28 genuine
  upstream `cfg80211`/`net/wireless` exports (`wiphy_register`,
  `cfg80211_ready_on_channel`, `cfg80211_ch_switch_notify`,
  `__cfg80211_get_bss`, `cfg80211_del_sta_sinfo`, and more -- full list in
  `docs/evidence/mainline-wifi-port/module-compile.json`).
  This is **expected and inherent to the scratch verification method, not a
  defect in the port**: this task's dev tree is a headers-only `-dev`
  output with no actual `net/wireless/cfg80211.ko` ever built into it, so
  its `Module.symvers` has no real cfg80211 exports to resolve against,
  regardless of how correct the calling code is. A kernel actually built
  with `CONFIG_CFG80211=m` live (the coordinator's parallel build, tracked
  at `~/tmp/k230-parity-build4/`, still in progress -- building vmlinux as
  of this writing) would supply those exports and is the authoritative
  check per this task's own instruction. **This section will be updated
  with that build's result once it completes**; until then, the "0 compile
  errors, port is syntactically and semantically complete against mainline
  v7.3-rc5's actual header declarations" result above is independently
  reproduced and not in question, but the final `.ko` producing a clean
  `modpost` pass against a real `cfg80211.ko` remains UNVERIFIED.
- 560 warnings in a full from-clean rebuild, all pre-existing classes
  (`-Wmissing-prototypes`, `-Waddress` on fixed-size array decay, and
  similar) already present before this follow-up touched anything; no new
  warning class was introduced by any of the changes above.

### 4. Nix wiring

- `nix/k230-wifi-driver.nix` gained an `extraPatches ? [ ]` parameter
  (applied via the derivation's `patches` attribute), defaulting to empty.
  The existing vendor-kernel call site (`flake.nix`'s `k230-wifi-driver`,
  built against `self.k230Kernel.kernel`) passes nothing and is therefore
  **byte-identical** to before this change -- the vendor kernel's own
  `EXTRA_CFLAGS`/timer/pppoe/`strncpy` APIs are unaffected by this task and
  do not need (and in the `EXTRA_CFLAGS` case would conflict with) the
  mainline patch.
- New flake output `k230-wifi-driver-mainline`: the same
  `nix/k230-wifi-driver.nix` function, `kernel =
  self.packages.${buildSystem}.kernelMainlineDrm` (the DRM kernel candidate,
  not plain `kernelMainline`, because only its patched sdhci driver claims
  `&mmc_sd0`'s five clocks), `extraPatches = [
  ./nix/patches/mainline/rtl8189fs-mainline-v7.3-rc5.patch ]`. This is the
  one true reproduction path for the completed `cfg80211_ops` port in
  section 3 above. `nix build .#k230-wifi-driver-mainline` was still **not
  run** by this follow-up either (it needs the full `kernelMainlineDrm`
  kernel build with `CFG80211 = module;` actually built in, which this
  task's own worktree/build-slot rules keep separate from the coordinator's
  parallel build at `~/tmp/k230-parity-build4/`) -- but per section 3's
  "Compile verification", the driver source itself is now proven to compile
  with zero errors against this exact kernel's real header declarations;
  the only remaining gap before `nix build .#k230-wifi-driver-mainline`
  should succeed is that live kernel build existing with real `cfg80211`
  symbols for `modpost` to resolve against.
- `nix/kernel-mainline.nix`: `CFG80211 = module;` added to
  `structuredExtraConfig`, documented above.
- `boot.extraModulePackages`/`k230-wifi` are **not** re-enabled for either
  mainline `nixosConfigurations` variant in this change -- the module does
  not build yet, so wiring it into a system closure would break those
  builds. That remains for the successor task once the cfg80211_ops port
  and a `CFG80211`-enabled kernel build both land.

## Successor task

Updated by the cfg80211_ops-port follow-up: (b) above is now **done** (see
section 3). What remains: (a) confirm `kernelMainlineDrm` actually builds
with `CFG80211 = module;` live without a Kconfig loop -- in progress at
`~/tmp/k230-parity-build4/` as of this writing, this follow-up's own private
scratch verification proves the *driver* side is ready but does not itself
build a real kernel; (a2, new) once that kernel exists, rerun
`nix/k230-wifi-driver.nix`'s `k230-wifi-driver-mainline` output (or the
equivalent manual cross-compile against that kernel's real `-dev` output) to
confirm `modpost` now resolves every `cfg80211`/`net/wireless` symbol
against the real `cfg80211.ko` and produces an actual `8189fs.ko` with zero
errors -- this is the one remaining gate before the module can be called
built; (c) once that `.ko` is confirmed, re-enable
`boot.extraModulePackages`/`systemd.services.k230-wifi` for
`k230-mainline-drm-shell` (mirroring `nix/hardware.nix`'s existing
vendor-kernel wiring, parameterized the same way `k230-wifi-driver-mainline`
already is); (d) task 6.2's board-side association/DHCP/reachability proof,
gated entirely behind (a2)-(c). Runtime risks to watch for once (a2)-(d) are
reachable, none of which this host-only port work can resolve: the SDIO
vendor/device ID table in `os_dep/linux/sdio_intf.c` must actually match the
RTL8189FTV's real SDIO IDs (not verified here -- this task never touched
`sdio_intf.c`); firmware blob path/name resolution via `request_firmware()`
needs the matching blob present in the mainline system closure's
`/lib/firmware` (not checked); and regulatory-domain/channel-set
initialization depends on CRDA/the kernel's built-in regulatory database
being reachable, which is a boot-time concern, not a compile-time one.

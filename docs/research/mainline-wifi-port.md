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

With the patch applied, 51 of 57 translation units compile cleanly; 6 fail
(`hal/hal_com.o`, `hal/hal_com_phycfg.o`, `os_dep/linux/ioctl_cfg80211.o`,
`os_dep/linux/ioctl_linux.o`, `os_dep/linux/os_intfs.o`,
`os_dep/linux/rtw_cfgvendor.o`). Exact command, per-fix rationale, and the
raw remaining error classes are in
`docs/evidence/mainline-wifi-port/module-compile.json`.

### 3. The remaining blocker (not a rename -- stopped per this task's own instruction)

Two independent, well-identified problems remain, neither closable by a
"rename" patch:

- **A Kconfig gap.** `struct net_device`'s `ieee80211_ptr` member is guarded
  by `#if IS_ENABLED(CONFIG_CFG80211)` in mainline's
  `include/linux/netdevice.h` (confirmed directly), and this dev tree's
  `.config` has `# CONFIG_CFG80211 is not set`. Read CFG80211's own Kconfig
  stanza from the pinned **read-only** mainline research source
  (`/nix/store/79yd40jv8h4x866bm1vyw94cm948grax-linux-mainline-k230-init-exec-transition-src/net/wireless/Kconfig`,
  since the dev tree ships headers only, no Kconfig files): it `select`s
  `FW_LOADER`, `CRC32`, and conditionally `CRYPTO_SHA256`; all three are
  already `y` in the built `.config` (grep-confirmed), so asking for
  `CFG80211` does not loop through an unsatisfied dependency. Added
  `CFG80211 = module;` to `nix/kernel-mainline.nix`'s
  `structuredExtraConfig`, as `module` (not `yes`) since this is the
  wireless configuration API, not a board driver, and every upstream board
  ships it as a module. **`MAC80211` is deliberately not requested**: the
  pinned driver implements its own softmac stack directly against cfg80211
  (grep of every `.c` file confirms no `mac80211.h` include or symbol use
  anywhere). This config addition itself is **UNVERIFIED** -- no kernel has
  been rebuilt with it; a full kernel build is out of scope for this task.
- **A real cfg80211_ops port, not a rename.** Independent of the config
  gap, `os_dep/linux/ioctl_cfg80211.c`'s `struct cfg80211_ops` initializer
  has roughly 13 callback signature mismatches against mainline's
  `net/cfg80211.h` at this pin: many ops moved their second parameter from
  `struct net_device *` to `struct wireless_dev *` across the
  mac80211/cfg80211 API's multi-year netdev-to-wdev migration
  (`change_virtual_intf`, `add_key`, `get_key`, `del_key`,
  `set_default_key`, `mgmt_tx`, `mgmt_tx_cancel_wait`, `set_tx_power`,
  `del_station`, and more -- full list in the raw compiler log embedded in
  the evidence JSON). `cfg80211_new_sta()`/`cfg80211_del_sta()` calls also
  now take a `wireless_dev *` first argument. Fixing this means re-plumbing
  a `wireless_dev *` (and deriving its `netdev` where the body still needs
  one) through every affected callback's signature and body -- a real
  driver-side port, not a find-and-replace rename. Per this task's own
  instruction ("stop and document if it needs deeper rework"), this was
  **not attempted**.

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
  one true reproduction path for whoever picks up the cfg80211_ops
  follow-up; `nix build .#k230-wifi-driver-mainline` was **not run** (would
  need the full `kernelMainlineDrm` kernel build, out of scope here) and is
  expected to fail identically to the manual build above until that port
  lands.
- `nix/kernel-mainline.nix`: `CFG80211 = module;` added to
  `structuredExtraConfig`, documented above.
- `boot.extraModulePackages`/`k230-wifi` are **not** re-enabled for either
  mainline `nixosConfigurations` variant in this change -- the module does
  not build yet, so wiring it into a system closure would break those
  builds. That remains for the successor task once the cfg80211_ops port
  and a `CFG80211`-enabled kernel build both land.

## Successor task

A follow-up change should: (a) build `kernelMainlineDrm` with `CFG80211 =
module;` live and confirm it actually builds without a Kconfig loop (this
change only checked the `select` dependencies are already `y`, it did not
build the kernel); (b) port `os_dep/linux/ioctl_cfg80211.c`'s
`cfg80211_ops` callbacks to the `wireless_dev *`-based signatures mainline
now expects; (c) once the module links, re-enable
`boot.extraModulePackages`/`systemd.services.k230-wifi` for
`k230-mainline-drm-shell` (mirroring `nix/hardware.nix`'s existing
vendor-kernel wiring, parameterized the same way `k230-wifi-driver-mainline`
already is); (d) task 6.2's board-side association/DHCP/reachability proof,
gated entirely behind (a)-(c).

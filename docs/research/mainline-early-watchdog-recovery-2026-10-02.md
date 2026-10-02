# Early watchdog recovery on the current K230 path

Source audit recorded `2026-10-02T18:31:14Z`. **There is no verified existing
candidate option that arms an autonomous watchdog before Linux.** A reviewed
early firmware watchdog could potentially recover a CPU software stall, but
reset routing, retained clocks and the complete return to normal boot remain
**UNVERIFIED**. This is host/source evidence only: no board, serial, MMIO,
build, card write or physical watchdog test was performed.

Worktree `/home/jadams/tmp/k230-mainline-early-watchdog`, branch
`audit/mainline-early-watchdog`, base
`b164aefa5435f803fe125d5f4a05bfdec6dc6ac8`. Only this research note is owned;
no board/build slot reserved. Start `tools/work-status.py` completed with exit
zero at idle I/O priority. No current mainline task status is changed.

## Exact candidate has no hardware-watchdog owner

The installed kernel/source/configuration and their hashes are pinned in
[the shutdown audit](../evidence/mainline-restart/shutdown-path-audit-2026-10-02.md):

- `/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`;
- `/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
  based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`;
- `/nix/store/5wfn6k1lm9fvbwny2qk52admhwm5q4rm-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev/lib/modules/7.3.0-rc5/build/.config`;
- bundle `/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files`.

The exact configuration has `WATCHDOG=y`, `WATCHDOG_CORE=y`,
`WATCHDOG_HANDLE_BOOT_ENABLED=y`, `WATCHDOG_OPEN_TIMEOUT=0`,
`WATCHDOG_NOWAYOUT=n`, and **`DW_WATCHDOG=n`**. Built-in Sunxi/StarFive
watchdog drivers do not substitute for the K230's DesignWare hardware.
Recursive inspection of all 50 bundle DTB nodes found no watchdog node or
`snps,dw-wdt` compatible; the mainline SoC/board source also has none.
`WATCHDOG=y` alone supplies no hardware timer, nor does the current K230
software restart callback rescue a stall before that callback is dispatched.

The pinned vendor [Linux DTS](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/arch/riscv/boot/dts/canaan/k230.dtsi#L495-L500)
does describe WDT1 at `0x91106800`, size `0x800`, `snps,dw-wdt`, interrupt
108/level-high, clock `wdt1`, absent status (available), and no reset phandle.
This describes the IP interface, not measured operation or the reset scope.
The hardware watchdog's output must still be shown to reset the executing
hart and enough of the boot chain to return to protected normal Linux; a
peripheral reset ID is not that proof.

## Bootloader and OpenSBI do not currently arm it

`nix/uboot-k230.nix` selects U-Boot 2022.10 with SDK overlay pin
`1104236db4d1e47873bd68924f912747b820228c`. The local immutable overlay at
`/nix/store/g58y0fnasf1gapxjnjmbdnmg6zs58yhs-source/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay`
has no watchdog DT node or K230 arm/feed implementation. Its `platform.h`
names WDT0/1 bases; address constants alone are not a recovery API.

The installed U-Boot outputs inspected were
`/nix/store/r55379zj8d5vwgq35ckzcr6m8xidsd9j-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10`
and
`/nix/store/3fs5wp1k32mpnd8k95hvbcg7mrznsrzy-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10`.
Both `.config` files disable `WDT`, `WATCHDOG`, `SPL_WDT` and
`SPL_WATCHDOG`; neither selects `CMD_WDT`. Their configuration SHA-256 values
are respectively `7d1c4b118812215978de90ebd573943e8bf91dcf4d1a351f302073cb04c6f479`
and `116316cd05599f67456ec646a1c02330eae39d216d37827900dfba85de362a78`.
These are inspected host builds, not a fresh readback of the card's raw U-Boot
slots. The repository's U-Boot fragment/patches add no watchdog support, and
the ordinary `blinux` environment does not arm one. No usable `wdt start`
command is established for the current bootloader.

Upstream [U-Boot 2022.10 DesignWare driver](https://github.com/u-boot/u-boot/blob/v2022.10/drivers/watchdog/designware_wdt.c)
can program/start/feed a timer in reset mode. Probe first stops it; driver
registration has no remove callback. A future port must supply a correct DT,
clock/reset resources and explicit lifecycle through K230's handoff. Merely
enabling generic driver symbols does not supply those board details. Generic
autostart/servicing policy is another independent choice; it is currently
disabled by the absent WDT subsystem.

The inspected OpenSBI output is
`/nix/store/7fmfx6dan9c2dsa55cs3jba3b5wx6w6p-opensbi-k230-riscv64-unknown-linux-gnu-1.4`,
configuration SHA-256
`4c25518e56a7253f909b7c9ab5f2a60a0e9c5083c8358f176a676e8cd736fdc3`.
Its v1.4 source `/nix/store/k6kih6q1vh5nashsgaz96ch012742s8z-source` plus the
same SDK's OpenSBI overlay contains no K230/DesignWare watchdog arm/feed/reset
driver. Enabled ATCWDT200 and Sunxi reset drivers match unrelated compatibles;
their reset-call support is not autonomous timeout protection. The T-Head
K230 override handles MAEE/PMU quirks, not watchdog lifecycle.

The current trial also requires its wrapped OpenSBI bytes/hash/CRC to equal
the protected normal wrapper (`tools/mainline-drm-initrd-shell-trial.py`,
`normal_expectation`). Therefore a modified early-arming OpenSBI wrapper is
not an existing accepted trial option. A new reviewed candidate identity and
controller gate would be required, while retaining all protected normal files.

## Why an early arm alone is insufficient

In the exact mainline source, `drivers/clk/clk-k230.c:1009–1018,1068–1092`
defines WDT0/1 APB gates (clock IDs 108/109), oscillator counter gates
(115/116) and counter dividers (171/172). Counter gates use `osc24m`, with
dividers 1–64. These gates have neither `CLK_IGNORE_UNUSED` nor a watchdog DT
consumer. `drivers/clk/clk.c:1539–1578` disables hardware-enabled gates with
no software enable count unless exempted. A firmware-armed timer may thus
lose its clock before userspace; this is source risk, not an observed clock
measurement. Global `clk_ignore_unused` would alter that cleanup but is not
proof of timeout/reset and is currently restricted to the separate label
diagnostic. No policy change or raw clock write is proposed here.

If a future candidate adds the Linux DW driver/node to own those clocks,
`drivers/watchdog/dw_wdt.c:637–654` recognizes already-running hardware and
registers it. The core then feeds it before userspace:
`watchdog_dev.c:63–74,204–225` makes an open timeout of zero an infinite
deadline. An initrd/root stall can therefore leave the watchdog fed while
the watchdog worker remains alive. A finite `watchdog.open_timeout` or
explicit no-feeding policy needs review and bounded timing; it does not arm
hardware itself or cover time before the driver probes. `nowayout` alone
does not establish either early arming or a finite recovery deadline.

The DW driver also calls `watchdog_stop_on_reboot`. The core's reboot
notifier (`watchdog_core.c:159–176`) can stop hardware **before**
`device_shutdown`; `SYS_RESTART` equals `SYS_DOWN` (`include/linux/reboot.h`).
With a reset resource, the DW stop method asserts/deasserts it; without one,
it leaves hardware running (`dw_wdt.c:285–297`). The inspected
[vendor DW driver](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/drivers/watchdog/dw_wdt.c#L266-L279)
has the same distinction. Neither branch alone guarantees protection during
the current pre-callback stall: clock retention and kernel feeding remain
separate. A watchdog restart handler that arms only at `machine_restart`
does not cover a preceding shutdown wait.

Timeout must be derived from the actual timer clock and implemented TOPs,
not a requested integer alone. As an illustrative calculation only, fixed
TOP `2^31` at undivided 24 MHz is about 89.48 seconds; changing the divider
changes it. Actual component parameters/divider, elapsed handoff time and
margin have not been read or proved. No timeout is recommended from this
calculation.

## Bounded path to a future autonomous recovery proof

The smallest useful future source deliverable would be an optional, isolated
early firmware arm plus explicit clock/reset/feeding lifecycle for one
candidate. A candidate OpenSBI path could avoid changing raw normal U-Boot,
but requires reviewed wrapper/controller identities. A U-Boot command port
instead needs a separately proved bootloader trial and its own recovery.
Neither is implemented or ready to run in this audit.

Before unattended candidate trials, the operator needs named physical proof
of: hardware reset routing and returned SPL/normal boot; a measured finite
expiry with no Linux/userspace feeding dependency; continued expiry across
clock cleanup and reboot preparation; clearing/disarming on recovery to avoid
a normal-boot reset loop; and fresh normal identity/services/eight protected
file hashes afterward. Early arming must occur after the one-shot candidate
selection and leave persistent `bootcmd`/environment and normal files intact,
so expiry cannot automatically select the same failing candidate again.
All are missing physical gates. There is no grounded existing operator arm
command to publish yet; guessed `mw`/`devmem` sequences would skip them.

## Read-only checks and limits

Commands were narrow `rg -n`/`sed -n` of exact installed configuration,
source and repository files; `fdtget`/recursive DTB compatible inspection;
`nix-store -q --deriver` and `nix derivation show` for source provenance;
Python SHA-256 reads; and version/pin-specific upstream source reads linked
above. The original U-Boot tarball and old vendor Linux source named by their
derivations were absent locally; upstream version/pin files supplied those
specific comparisons. No build/fetch realization was requested. Narrow
validation is `openspec validate the-board-runs-a-mainline-kernel --strict`
and `git diff --check`. No autonomous hardware recovery or mainline task
completion is claimed, and the coordinator's separate USB investigation is
outside this note.

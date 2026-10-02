# Optional SD1 clock-consumer correction, 2026-10-02

Recorded at `2026-10-02T19:54:43Z`. Evidence class: read-only host source
inspection and coordinator-reported physical comparison. No kernel/config
change, build, board input or serial access was performed here. A correction
without the diagnostic flag and specific-clock attribution remain **UNVERIFIED**.

Worktree `/home/jadams/tmp/k230-mainline-sd1-clock-consumers`, branch
`audit/mainline-sd1-clock-consumers`, base
`9cd4a3f870a62c01d63abae60dc07b309e054c52`. Only this note is owned; no board
or build slot was reserved. Start and handoff use cached `tools/work-status.py`
at idle priority, with output outside the repository.

## Observation and source boundary

The coordinator reports the same `asj7l4zj5jrjkgng4nrcx3y72p7jf7aa` trial
bundle, `4wkhxf55y1abg1kg2xd0acsfjqr64j0h` kernel and `v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk`
system, with volatile `clk_ignore_unused`, printed `clk: Not disabling unused
clocks`, advanced beyond the earlier MMC shutdown entry, printed
`reboot: Restarting system`, reached SPL and returned automatically to the
protected normal system. The controller exited 0; a fresh boot ID, profile,
kernel, services and all eight protected hashes passed. This supports dependence
on global unused-clock cleanup. It does not isolate SD1 or any particular gate.
The quiet baseline without the flag remains a failed automatic-return trial.
Physical provenance belongs to the coordinator's committed comparison packet;
no private capture was read for this note.

The inspected exact source is
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
Linux pin `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus optional K230 patches.
Vendor source is `/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source`, pin
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`. See the prior
[MMC boundary audit](mainline-mmc-shutdown-boundary-2026-10-02.md) and
[vendor/mainline clock comparison](../evidence/mainline-display/physical-2026-10-01/mainline-root-path-audit-2026-10-02.md).

## Why three additional consumers are the smallest supported set

Pinned upstream
[`snps,dwcmshc-sdhci.yaml:115`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/Documentation/devicetree/bindings/mmc/snps,dwcmshc-sdhci.yaml#L115)
requires five clocks for `canaan,k230-emmc` / `canaan,k230-sdio`, named
`core`, `bus`, `axi`, `block`, `timer`. Its
[`sdhci-of-dwcmshc.c:1947`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/mmc/host/sdhci-of-dwcmshc.c#L1947)
explicitly obtains/enables the three additional K230 clocks. The current
candidate uses the distinct vendor compatible `canaan,k230-dw-mshc` and copied
Kendryte driver; that driver only obtains core/bus (`:398–410`).

The vendor clock-provider source (`arch/riscv/boot/dts/canaan/k230_clock_provider.dtsi:465–538`)
describes separate SD base, AXI, card-TX and timer branches. Its SD1 definitions
at `:617,881,905,959,1081` agree with mainline's register offset/bit/parent
definitions in `drivers/clk/clk-k230.c:454,559,582,592,639`:

| DT name | Mainline ID | Vendor role; retained purpose |
| --- | --- | --- |
| `core` | `K230_HS_SD1_BASE_GATE` = 31 | Base clock; keep existing rate source for `sdhci_pltfm_clk_get_max_clock()` (`sdhci-pltfm.c:31`). |
| `bus` | `K230_HS_SD1_AHB_GATE` = 13 | Register-bus interface clock. |
| `axi` | `K230_HS_SD1_AXI_GATE` = 29 | AXI branch, distinct from the base branch despite their shared upstream source. Relevant to controller/data traffic; this trial does not prove it alone blocked shutdown. |
| `block` | `K230_HS_SD1_CARD_GATE` = 26 | Vendor card-TX branch from the SD card-clock source. This is the proposed semantic translation to the K230 binding's `block` name; no upstream board DTS at this pin supplies a concrete ID-26 example. |
| `timer` | `K230_HS_SD1_TIMER_GATE` = 35 | Separate oscillator-derived SD timer branch, not the Linux scheduler timer. Its necessity in the observed failure is unproved. |

All three extras currently have flags 0 and no consumer. Vendor clock init
adopts firmware-enabled gates (`drivers/clk/clk-k230.c:538–547`); mainline
ordinary gates do not. Claiming only AXI, card or timer would select a hypothesis
unsupported by the global comparison. Claiming the whole provider or marking
these clocks permanently critical would bypass device ownership. Five clocks
are the smallest source-supported host resource set, not a proven minimal
hardware subset.

## Concrete proposed patch, not applied

Keep the existing base forward port and console/default DT outputs untouched.
Add an optional DRM-only patch to the existing `applyPatches.patches` list in
[kernel-mainline-drm.nix](../../nix/kernel-mainline-drm.nix), applied to the
already-copied `drivers/mmc/host/sdhci-of-kendryte.c`. Add this override only to
[k230-tdisplay-mainline-drm.dts](../../nix/dts/k230-tdisplay-mainline-drm.dts):

```dts
&mmc_sd1 {
        clocks = <&sysclk K230_HS_SD1_BASE_GATE>,
                 <&sysclk K230_HS_SD1_AHB_GATE>,
                 <&sysclk K230_HS_SD1_AXI_GATE>,
                 <&sysclk K230_HS_SD1_CARD_GATE>,
                 <&sysclk K230_HS_SD1_TIMER_GATE>;
        clock-names = "core", "bus", "axi", "block", "timer";
};
```

Extend the private driver state and acquire the extras before enabling them:

```c
/* In struct dwcmshc_priv: */
struct clk_bulk_data other_clks[3];

/* In probe, after obtaining priv: */
priv->other_clks[0].id = "axi";
priv->other_clks[1].id = "block";
priv->other_clks[2].id = "timer";
err = devm_clk_bulk_get(&pdev->dev, ARRAY_SIZE(priv->other_clks),
                        priv->other_clks);
if (err)
        return dev_err_probe(&pdev->dev, err, "failed to get SD clocks\n");
/* After successful core/bus enable, before sdhci_add_host: */
err = clk_bulk_prepare_enable(ARRAY_SIZE(priv->other_clks), priv->other_clks);
if (err)
        goto disable_bus_clk;
```

Use mandatory lookup for all five resources in this matched optional candidate,
including checking bus lookup and enable errors. A missing resource or deferred
provider must fail probe cleanly, rather than quietly recreating the defect.
The upstream helper's optional lookup preserves other-platform compatibility;
the proposed candidate has a matching five-clock DT and no enabled SD0 host.
Keep existing max-frequency, clock-rate/divider programming, PHY choice, IRQ,
reset and DMA semantics. Do not swap the entire upstream host driver or change
compatible: the upstream K230 path also requires USB-PHY/regmap integration
and differs beyond resource ownership. The current legacy compatible is not
accepted by the upstream schema; five names alone do not make the full node
schema-valid.

| Lifecycle | Required ordering/error handling |
| --- | --- |
| Probe | Acquire resources with managed lifetime; enable core, bus, then bulk extras before registering the host. On later failure disable extras, bus, core. Failed bulk enable unwinds itself; do not disable that bulk twice. |
| Remove | `sdhci_remove_host()` completes first; then disable extras, bus, core. The host must retain resources while draining/removing requests. |
| Suspend | Call `sdhci_suspend_host()` first; on error retain clocks. Only on success disable extras, bus, core. |
| Resume | Enable core, bus, extras, then call `sdhci_resume_host()`. Every failed enable/host-resume step unwinds only successfully enabled resources in reverse order. Existing immediate bus-error return leaks a core enable; correct it as part of this lifecycle change. |
| Reboot | Add no clock-disabling `.shutdown`. MMC card shutdown precedes the platform host and can claim the host, issue SD commands and reset/power off the controller. Keep resources claimed through that sequence; existing platform driver has no shutdown callback. |

## Narrow build and physical proof plan, not run

This fits the existing mainline usable-root and bounded restart diagnosis;
no new capability or normative clock policy is proposed. After review, prepare
the exact patched source/config and compile only `drivers/mmc/host/sdhci-of-kendryte.o`
with the matching RISC-V kernel toolchain before a full build. Host object/API
proof, full kernel, DTB and matched trial bundle are separate gates:

```sh
nix build .#kernelMainlineDrm .#deviceTreeMainlineDrm --no-link
nix build .#kernelMainlineDrmTrialBootFiles --no-link
```

Check the built SD1 node's exact five IDs/names, absence of global clock flags,
new source/kernel/DTB/system pins and per-artifact SHA/size manifest. Compare
unchanged vendor/default and console derivation identities to the base. Review
lookup/enable failure unwind and suspend/resume paths; static fake clock tests
alone are not physical ownership proof.

The exclusive operator then stages only the reviewed matching optional bundle
and runs the same quiet minimal/runtime-trace controller with explicit `--bundle`
and `--normal-report`, **without** `--ignore-unused-clocks`. Require readiness,
minimal/runtime-Y gates, `clk: Disabling unused clocks`, real reboot, SPL,
fresh protected normal boot identity and all postflight checks within the same
180-second deadline. Any unknown child/return means stop input and preserve
manual recovery. A passing result tests this targeted correction, not per-gate
attribution. Only after baseline automatic recovery works proceed separately to
the returned read-only label and `ro,noload` root diagnostics. Usable root,
ordinary `/init` and deliberate touch remain task 5b.5's open physical gates.

Host checks for this note: `git diff --cached --check` and
`openspec validate the-board-runs-a-mainline-kernel --strict` passed. Review,
merge/push, source implementation, build and physical proof remain; no source
change or new board claim is supplied by this document.

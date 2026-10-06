# Mainline ordinary boot reaches a qualified root login (clock ownership)

On 2026-10-06 the ordinary mainline DRM system (`.#kernelMainlineDrmTrialBootFiles`,
plain policy, `console=tty0` + ttyS0) reached the controller's qualified
root login with **normal unused-clock cleanup active**:

```
[    3.225745] clk: Disabling unused clocks
...
K230_SYS … system RC=0 VALUE=/nix/store/pjlvaa6q8fq3jhsfpwjfr8kk9jrvvk77-nixos-system-…
K230_SYS … uname RC=0 VALUE=7.3.0-rc5
K230_SYS … pid1 RC=0 VALUE=/nix/store/srwrq12f…-systemd-…-261.2/lib/systemd/systemd
K230_SYS … getty RC=0 VALUE=active
```

Controller status `candidate-ready-qualified-ordinary-init` (begin phase; state
saved for the touch/finish phases). Bundle `f8pfn3qy…`, system `pjlvaa6q…`,
built from `0b327025`. The board was then returned to the protected normal
system by `reboot` from the mainline shell; the reviewed recovery checker
verified a distinct normal boot, exact identities, eight boot hashes, three
services and registration absence. This is physical UART evidence; ordinary
root activation and deliberate glass touch (task5b.5) are still **UNVERIFIED**.

## Cause

Late `clk_disable_unused` gated clocks that U-Boot left running and no mainline
consumer claimed. Retained logs and the [camera-repeat analysis](../mainline-init-exec-transition/camera-repeat-2026-10-05/README.md)
first implicated the display path. Each fix was built, staged under the guarded
pattern and booted once ([all runs](runs.json)):

| change | commit | ordinary boot result |
|---|---|---|
| VO/DSI own display AHB/AXI/DPIP/CFG/REF gates | `ad627a2b` | panel init completes; stage 2 reached; freeze ≈35 s |
| RTC owns PMU APB gate | `c73f6ea2` | same freeze |
| `clk_ignore_unused pd_ignore_unused` ablation | controller `febf6cc1` | **root login** |
| GPIO nodes name their bus/debounce clocks | `f2403a13` | same freeze |
| hold all 68 [unused-but-on gates](unused-but-on-gates.json) from VO (experiment) | `9dd8d3d5` | **root login** |
| bisection rounds A–I (experiment branches) | — | only sets containing `K230_SPI2AXI_GATE` log in |
| `spi2axi_gate` `CLK_IS_CRITICAL` | `0b327025` | **qualified root login** |

The gate list comes from debugfs `clk_summary` read in the live ablation shell.
Bisection: A (USB PHY + IOMUX) fail, B (32 infra gates) pass, C (DDRC/SHRM/SEC)
fail, D (sysctl 8) fail, E (timers + timer APB) fail, F (QSPI/SSI/spi2axi) pass,
G (QSPI AXI subtree) fail, H (spi2axi + SSI0 AXI) pass, I (spi2axi alone) pass.
Why gating `spi2axi` stops the SoC is not established; the vendor kernel never
gates `spi2axi_aclk`. The display, RTC and GPIO ownership fixes correct real
missing consumers; only the display fix and spi2axi were shown to change the
boot outcome. Power domains were not involved (DISP/VPU register as off, the
rest always-on).

The controller also expected `<system>/init` as PID 1; NixOS stage 2 execs
systemd, so `f7cac9ef` expects `<system>/systemd/lib/systemd/systemd` (matches
the observed value). Independent source reviews of all fixes and the controller
changes passed. Failing runs were recovered by NEW operator resets with the
reviewed checker; passing runs rebooted themselves. Raw UART, URLs and boot IDs
remain private; [runs.json](runs.json) binds each private capture by SHA256.

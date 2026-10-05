# Camera repeat of the staged transition capture, and the display-clock pattern

Group5u repeated the unchanged 5t operator command ONCE against the already
staged `jx56x86…` bundle (no build, transfer, source or controller change),
2026-10-05 23:26:44–23:30:12 UTC, while the host recorded the panel
(`/dev/video0`, MJPEG 1280x720 10fps stream copy, locked manual exposure).
Controller exit1, readiness unknown. [Result](result.json).

## UART: identical to 5t

```
[    4.568209] K230_INIT_EXEC_RETURN_V1 ret=0
[    4.568223] K230_INIT_EXEC_TRANSITION_V1 point=kernel-init-return
[    4.568354] K230_INIT_EXEC_TRANSITION_V1 point=first-user-ecall
```

then exactly `\r\n ESC P+q6E616D65 ESC \` and nothing for the rest of the bound.

## Camera: inconclusive by the pre-registered rule

The panel region was lit only from 19.7 to 24.3 s, showing the normal system's
shutdown text ([still](panel-normal-shutdown-text-21s.jpg)). After the reset it
stayed dark and flat for the whole candidate run ([still](panel-dark-candidate-120s.jpg)).
The candidate never visibly lit the panel, so cursor/text liveness could not be
observed: classification (c), inconclusive. Earlier mainline runs where panel
init completed did show boot text (10-01 photograph).

## The pattern this exposed (UART log comparison)

The dark panel led to the panel driver's lines. In this run the panel prepare
sequence started but its completion lines (RDDID/RDDPM probes and
`DCS write 0x51`, about 0.35 s after entry in every completed case) never
appeared before cleanup:

```
[    4.445013] canaan-panel-dsi 90850000.dsi.0: canaan_panel_prepare: entered, init_set_v1_flag=1
[    4.525740] clk: Disabling unused clocks
[    4.525913] PM: genpd: Disabling unused power domains
[    4.557645] Run /init as init process
```

Comparing retained private raw UART logs of earlier runs (timestamps only):

| run | prepare entered | prepare completed | unused-clock cleanup | last kernel timestamp |
|---|---|---|---|---|
| vendor 6.6 normal boot | 3.375 | 3.735 | 5.788 | normal login |
| mainline 10-01 candidate | 2.700 | 3.054 | 3.242 | 7.222 |
| mainline 10-01 diagnostic | 2.718 | 3.072 | 3.264 | 4.029 |
| mainline blkid (10-03) | 2.636 | 2.989 | 3.178 | 36.05 (later stop) |
| mainline boot-trace | 2.659 | not seen | 2.752 | 2.752 |
| mainline p2 ordinary repeat (5r) | 4.389 | not seen | 4.482 | 4.514 |
| mainline 5t / 5u | 4.445 | not seen | 4.526 | 4.568 |

Whenever cleanup ran inside the panel init window, output stopped within
milliseconds; when init finished first, the stop came later. Source inspection
of the selected kernel shows why this is plausible: the mainline DT gives the
`vo` and `dsi` nodes no clocks, the canaan VO/DSI drivers request none, and the
mainline K230 display gates (AHB/AXI/DPIP/CFG/REF at sysctl offset 0x74) use
ordinary `clk_gate_ops` without `CLK_IS_CRITICAL`/`CLK_IGNORE_UNUSED`, so
`clk_disable_unused` gates them while the display path is still in use. The
vendor 6.6 kernel registers these as composite clocks it does not gate.

This is a correlation plus a source-grounded hypothesis, not a proven cause.
It explains the systemd DCS observation without invoking the console: the
SoC can stop on the next display register access after its clocks are gated.
Group5v tests it directly with driver-owned display clocks. Recovery after this
capture is **PENDING a NEW operator reset**. Ordinary root/panel/glass and task
5b.5 remain **UNVERIFIED**.

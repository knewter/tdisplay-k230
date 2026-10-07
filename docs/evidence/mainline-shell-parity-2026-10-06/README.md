# Mainline shell parity: board results (2026-10-06)

Physical evidence for `openspec/changes/the-mainline-shell-reaches-parity`.
Every boot used guarded staging, volatile U-Boot selection and the reviewed
recovery checker; raw serial captures stay private and are bound by SHA256 in
[board-results.json](board-results.json). No Wi-Fi identifier, address or
credential is recorded.

## Full shell, no operator input

On the full coherent shell over the mainline kernel the serial console showed:
`firewall` active and no failed units; `k230-wifi` active with the RTL8189FTV
associated, an IPv4 address and a reachable gateway (each stage checked
separately); the `K230 PMU Power Key` input registered; and the
`K230_I2S_INNO` sound card listed.

## Console variant and thermal

The console mainline variant reached a qualified login with ordinary clock
cleanup once the SD five-clock ownership moved into the base kernel, and it
rebooted itself into the normal system once the restart handler did too. With
the thermal driver converting the TS code (Canaan's documented polynomial) the
zone read 52.4 °C idle and 54.5 °C after 60 s of CPU load.

## Operator session

- Touch in the shell: the trial controller's bounded touch summary reported a
  complete contact (4 down/up pairs with movement and SYN after release); the
  operator, holding the board, reported the shell responded normally. The
  camera lost the board during the taps ([after](after-touch-camera.jpg)).
- Power key: the operator pressed the side button and reported the power sheet;
  the camera shows a sheet on the panel ([still](power-sheet-camera.jpg)) and
  sway logged `output DSI-1 power off`/`on`. `evtest` saw no events because the
  shell holds the device grab.

## Audio

The board has no onboard speaker or buzzer (the MAX98357A amplifier is on an
optional LILYGO base board that is not fitted; LILYGO lists a 3.5 mm jack,
untested). On the vendor kernel `speaker-test` completes. On mainline with the
generic DesignWare I2S driver, starting playback froze the SoC, also with
`clk_ignore_unused pd_ignore_unused`; the operator reset the board each time.
The vendor driver (`dwc_canaan`) differs: DMA xor IRQ, K230 CCR bits, 32-bit
data and burst 4. It was ported; two more defects then surfaced and were fixed. First, the card
bound before the DMA PCM registered, so every open failed with -EINVAL (kprobe
traces: `snd_pcm_hw_constraint_mask(ACCESS, 0)`; `dmaengine_pcm_open` never
ran) — the PCM now registers first. Second, the first transfer hung the bus
silently (no soft-lockup report); with `clk_ignore_unused` playback completed,
and `clk_summary` showed the shared-memory APB/AXI-slave/SRAM gates unclaimed —
the PDMA now holds them. With ordinary cleanup, `speaker-test -D plughw:0,0`
exits 0 with a 48000-frame buffer and 2.09 s periods (vendor: 2.0 s), the
console stays responsive and no unit fails. Audible output is not claimed.

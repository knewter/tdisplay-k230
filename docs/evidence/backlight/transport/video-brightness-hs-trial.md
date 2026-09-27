# Active-video brightness: narrow HS transport trial

2026-09-26. Initial host-tested hypothesis; the subsequent
[physical trial](../live-hs/README.md) now demonstrates live brightness,
Settings backend controls and nondefault brightness retention across DPMS.

The coordinator reports distinct brightness levels only after DPMS cycles
with source `926c7a61`; live-video writes still do not visibly change them.
That physical finding motivates this experiment. It does not establish the
experiment's result.

Primary source precedents, also read in the pinned kernel tree:

- [Linux v6.6 Raydium RM67191 `rad_bl_update_status`](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panel/panel-raydium-rm67191.c#L494)
  explicitly disables `MIPI_DSI_MODE_LPM` before brightness writes.
- [Linux v6.6 JDI `dsi_dcs_bl_update_status`](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panel/panel-jdi-lt070me05000.c#L344)
  disables LPM for the brightness request and restores it afterward.
- [Linux v6.6 DW message configuration](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/bridge/synopsys/dw-mipi-dsi.c#L371)
  selects LP/HS per message. Its fixed LP window values are accompanied by
  a TODO to compute timing from actual blanking and lane configuration;
  copying those constants does not prove our panel's live LP delivery.

The Canaan host now copies a validated message under its existing transfer
mutex and clears only `MIPI_DSI_MSG_USE_LPM` when all these conditions hold:
DSI is in video mode, packet type is DCS short write with one parameter,
length is two bytes, and command byte is `0x51`. Command-mode initialization,
all other packets, ACK flags, and the caller's original message are preserved.
The existing per-message configuration applies HS policy; no video-mode,
power, or PHY-clock register is changed and no DPMS cycle is introduced.

This is a hypothesis based on other panels' upstream drivers, not evidence
that RM69A10 accepts live HS brightness. The physical gate is a fixed-exposure
26/128/255 comparison without intervening DPMS, followed by the existing DPMS
recovery/persistence check. If live levels remain indistinguishable, retain
that negative result; do not infer delivery from empty host FIFOs.

Host command from the candidate worktree:

```sh
python3 tools/test-dsi-message-transport.py /nix/store/6mrbj8w8rlq33v2r11jf7m79l5nkny1f-linux-xuantie-k230-src
```

Result: **31 cases pass** using actual patched host functions and the pinned
kernel's packet constructor, mock MMIO, ASan/UBSan, and warnings-as-errors.
New cases distinguish the exact brightness shape in video versus command
mode, preserve ACK and caller immutability, and keep unrelated short,
generic, and long packets in their requested LP mode. Existing mock MMIO
rejects video-mode, power, or PHY-clock writes. Running the same harness
against the previous realized source
`/nix/store/kmf20m05cfqraigziwid8b0hsm0fyvjz-linux-xuantie-k230-src` fails the
new video-brightness HS assertion, as expected.

The combined system cross-build passed and the candidate booted on the board.
The linked physical record identifies the exact system/kernel and camera
results. Persistent installation is a separate gate.

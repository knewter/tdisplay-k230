# DSI message transport repair: host evidence

2026-09-26. **Host evidence only. Brightness and DPMS acceptance remain
UNVERIFIED pending the combined kernel's physical trial.**

The panel helper requested a one-parameter DCS short packet (`0x15`), but
`canaan_dsi_transfer()` routed it through a helper that unconditionally
wrote a long packet (`0x39`) and put both bytes in the payload FIFO. Thus
previous successful helper return codes did not prove short-packet framing
on the wire. This is an additional bug beyond the previously corrected
brightness value width.

The standalone `nix/patches/canaan-dsi-message-transport.patch`, applied at
the end of kernel source `postPatch`, uses `mipi_dsi_create_packet()` for
framing. A brightness command `{0x51, 0xfe}` now writes header `0x00fe5115`
and no payload FIFO word. The existing supported packet types and one-byte
DCS read limit remain in place.

The host waits for empty transmit FIFOs before changing message policy,
checks payload space before each write, and waits for both command and
payload FIFOs to drain after the header. Each poll is bounded at 20 ms;
a timeout is returned, without speculative controller or PHY reset. A
partial payload left by an earlier failure prevents subsequent messages
from being appended until the hardware is cleared/reinitialized.

Per-message low-power settings follow `dw_mipi_message_config()` in the
pinned kernel's `drivers/gpu/drm/bridge/synopsys/dw-mipi-dsi.c`: LP command
windows, command-type LP flags, and the video-mode LP-command-enable bit.
The panel now requests `MIPI_DSI_MODE_LPM`. Unrelated video configuration
bits are retained. No command path flips `MODE_CFG`, `LPCLK_CTRL`, or
controller power. The message configuration stays set until the next
serialized message, as in the standard DW driver; restoring it on timeout
could change a still-pending command's transmission policy.

A host mutex serializes entire transfers with encoder hardware setup.
Readiness is established for both normal initialization and the retained
stage-1 handoff. Disable permits the final panel/backlight callback, waits
for transfers, closes the host, then powers the panel down. The mutex is
never held across panel callbacks, which can call the host recursively.
This lifecycle wiring has source review here; hardware and kernel locking
behavior require the actual kernel trial.

## Reproduce the narrow host check

From the repository root, using the realized source before this patch:

```sh
python3 tools/test-dsi-message-transport.py /nix/store/6mrbj8w8rlq33v2r11jf7m79l5nkny1f-linux-xuantie-k230-src
```

The runner copies the three affected source files into a temporary tree,
applies the committed patch with zero fuzz, and compiles the actual host
transport functions with the actual pinned kernel packet constructor.
Only MMIO, polling time, and the kernel mutex wrapper are mocked. GCC
`-Wall -Wextra -Werror`, AddressSanitizer and UndefinedBehaviorSanitizer
are enabled. The same runner accepts already-patched realized source.

Result:

```text
PASS: 25 host transport cases; real kernel packet builder, mock MMIO, ASan/UBSan; no board claim
```

Cases cover short DCS and generic headers, virtual channel bits, long
packet payload packing, LP/ACK flag changes, unrelated bit preservation,
pre-write capacity, post-header completion and timeouts, refusing to append
to a prior failed payload, closed-host refusal without MMIO, invalid
messages, bounded stale/read response handling, and two threads issuing
1,000 long packets without interleaving their payloads. Mock MMIO rejects
any message-path video-mode, clock, or power write.

This does not simulate the DSI PHY or RM69A10, measure real time, demonstrate
visible brightness, or prove the LP timing constants suit this board's
video porch. Kernel cross-build, boot, locked-exposure brightness comparison,
repeated DPMS recovery, and Settings interaction remain coordinator-owned
physical gates. See the active `the-panel-brightness-is-adjustable` change.

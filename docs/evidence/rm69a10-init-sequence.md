RM69A10 initialisation sequence, transcribed (change 3, task 1.1)
==================================================================

Source: repo/canmv_k230/src/rtsmart/mpp/kernel/connector/src/rm69a10.c,
function rm69a10_568x1232_dsi_send(), which docs/rtsmart-boot-log.txt shows
running on this board. Transcribed from the vendor's working code, not from
a datasheet -- .skills/k230-spec-change/SKILL.md says a datasheet grounds
nothing.

CORRECTION: the design artifact published earlier states this sequence is
"13 commands, 75 bytes". It is 20 commands and 297 payload bytes. The
short version omits seven commands including the 55-byte gamma table
(0xE0) and the 45-byte 0xB4 block. Use the table below.

Each row is one connecter_dsi_send_pkg() call, in order. The first byte is
the DCS command; the rest are its parameters.

  1. param1   line 41   cmd 0xB9   len   4
      b9 ff 83 99
  2. param21  line 42   cmd 0xD2   len   2
      d2 aa
  3. param2   line 43   cmd 0xB1   len  16
      b1 02 04 71 91 01 32 33 11 11 ab 4d 56 73 02 02
  4. param3   line 44   cmd 0xB2   len  16
      b2 00 80 80 ae 05 07 5a 11 00 00 10 1e 70 03 d4
  5. param4   line 45   cmd 0xB4   len  45
      b4 00 ff 02 c0 02 c0 00 00 08 00 04 06 00 32 04 0a 08 21 03 01 00 
      0f b8 8b 02 c0 02 c0 00 00 08 00 04 06 00 32 04 0a 08 01 00 0f b8 
      01
  6. param5   line 46   cmd 0xD3   len  34
      d3 00 00 00 00 00 00 06 00 00 10 04 00 04 00 00 00 00 00 00 00 00 
      00 00 01 00 05 05 07 00 00 00 05 40
  7. param6   line 47   cmd 0xD5   len  33
      d5 18 18 19 19 18 18 21 20 01 00 07 06 05 04 03 02 18 18 18 18 18 
      18 2f 2f 30 30 31 31 18 18 18 18
  8. param7   line 48   cmd 0xD6   len  33
      d6 18 18 19 19 40 40 20 21 02 03 04 05 06 07 00 01 40 40 40 40 40 
      40 2f 2f 30 30 31 31 40 40 40 40
  9. param8   line 49   cmd 0xD8   len  17
      d8 a2 aa 02 a0 a2 a8 02 a0 b0 00 00 00 b0 00 00 00
 10. param9   line 50   cmd 0xBD   len   2
      bd 01
 11. param10  line 51   cmd 0xD8   len  17
      d8 b0 00 00 00 b0 00 00 00 e2 aa 03 f0 e2 aa 03 f0
 12. param11  line 52   cmd 0xBD   len   2
      bd 02
 13. param12  line 53   cmd 0xD8   len   9
      d8 e2 aa 03 f0 e2 aa 03 f0
 14. param13  line 54   cmd 0xBD   len   2
      bd 00
 15. param14  line 55   cmd 0xB6   len   3
      b6 8d 8d
 16. param15  line 56   cmd 0xCC   len   2
      cc 04
 17. param16  line 57   cmd 0xC6   len   3
      c6 ff f9
 18. param22  line 58   cmd 0xE0   len  55
      e0 00 12 1f 1a 40 4a 59 55 5e 67 6f 75 7a 82 8b 90 95 9f a3 ad a2 
      b2 b6 5e 5a 65 77 00 12 1f 1a 40 4a 59 55 5e 67 6f 75 7a 82 8b 90 
      95 9f a3 ad a2 b2 b6 5e 5a 65 77
 19. param23  line 59   cmd 0x11   len   1
      11
 20. param24  line 60   cmd 0x29   len   1
      29

20 commands, 297 payload bytes.

Delays, from the same function:
    after 0x11 (sleep out)   connector_delay_us(300)
    after 0x29 (display on)  connector_delay_us(100)

Both are MICROseconds in the vendor code. The device-tree binding's delay
field is a u8 of MILLIseconds, so neither is expressible as written; 1 ms
is the smallest non-zero value and is longer than both. Worth watching if
the panel misbehaves at init.

Not sent in the normal path
---------------------------
pag20 (0xB2, 0x0b, 0x77 x8) is sent only when test_mode_en == 1 -- a solid
blue test pattern. Not part of normal init.
param15 (0xCC, 0x04) is patched at runtime when rm69a10_y_mirror != 0.
The device tree cannot express that; 0x04 is the unmirrored default.

Two things the device tree cannot carry
----------------------------------------
panel-canaan-universal hardcodes both in probe():
    dsi->mode_flags = MIPI_DSI_MODE_VIDEO_SYNC_PULSE
    dsi->format     = MIPI_DSI_FMT_RGB888
The vendor runs this panel in K_BURST_MODE, so mode_flags disagrees and no
DT property changes it. Likely a driver patch for change 3.

Timings, from connector_info_list[] in
repo/canmv_k230/src/rtsmart/mpp/userapps/src/connector/mpi_connector.c:

    pclk 39600 kHz   phyclk 475200 kHz   2 lanes   burst mode
    h: 788 total, 568 active, 40 sync, 140 bp, 40 fp
    v: 1268 total, 1232 active, 4 sync, 16 bp, 16 fp
    vth_line = 9

39.6 MHz / (788 x 1268) = 39.63 Hz. The enum is named 60FPS and the numbers
say 39.6; the numbers are self-consistent (39.6 MHz x 24bpp / 2 lanes =
475.2 Mbps/lane, matching phyclk), so the name is wrong.

Reset: GPIO22, pulsed three times before init per docs/rtsmart-boot-log.txt.


Compiled (task 2.1)
-------------------
nix/dts/display-rm69a10-568x1232.dtsi compiles and round-trips:

  $ cpp -nostdinc -undef -x assembler-with-cpp test.dts | dtc -I dts -O dtb
  DTB: 1298 bytes

  panel-init-sequence   357 bytes  = 297 payload + 20 x 3 framing
  clock-frequency       39600000
  hactive/vactive       568 / 1232
  lan-num               2
  panel-width-mm        44

Two syntax mistakes worth recording, since both produce misleading errors:

  1. A DTS bytestring takes BARE hex pairs. Writing `[0x39 0x00 ...]`
     fails with a bare "syntax error" pointing at the opening bracket.
  2. All properties must precede any subnode. panel-init-sequence sat
     after display-timings and dtc said "Properties must precede
     subnodes", naming the whole node rather than the property.

STILL UNVERIFIED: that this lights the panel. Compiling proves the
description is well-formed, not that it is correct. The init sequence is
transcribed from working vendor code, but the timings, the reset polarity
and the burst-mode mismatch are all untested on hardware.

A structural correction (task 2.1, second pass)
------------------------------------------------
The first dtsi compiled and was wrong. Compiling in isolation proved only
that the syntax parsed; it said nothing about whether the driver would ever
see it. Reading display-st7701-480x800.dtsi properly showed four errors:

  wrong    a node at the root, `/ { panel-rm69a10 { ... } }`
  right    a DSI child, `&dsi { lcd: panel@0 { reg = <0>; ... } }`

  wrong    `lan-num = <2>`
  right    `panel-dsi-lane = <2>`

  wrong    `reset-gpios` on the panel node
  right    nothing -- reset and backlight are attached by the BOARD dts as
           `&lcd { dsi_reset-gpios = ...; backlight_gpio-gpios = ...; }`,
           which is why the panel node carries the `lcd:` label

  missing  the ports/endpoint graph binding panel port@0 to &dsi port@1,
           and `&vo { vth_line = <9>; }`

Also learned from the reference board dts: reset on GPIO22 is
GPIO_ACTIVE_HIGH, and GPIO25 is the backlight -- docs/dts-evidence.md
listed "whether IO25 gates a rail" as unestablished.

After the rewrite the only structural difference from the reference is the
label names (st7701 -> rm69a10), and the DTB round-trips with 357 bytes of
init sequence, 39.6 MHz, 568x1232, 2 lanes, vth_line 9, endpoint linked.

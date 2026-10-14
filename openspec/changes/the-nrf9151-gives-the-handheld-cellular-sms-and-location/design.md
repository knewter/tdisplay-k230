## Context

Sources read for this design:

- LILYGO `Xinyuan-LilyGO/T-Display-K230-nRF9151`:
  - `README.MD`;
  - `docs/AT_COMMANDS.MD`;
  - `docs/FLASH_PYOCD.MD`;
  - `serial_modem_k230/k230_serial_modem.conf` and `.overlay`;
  - `k230_at_probe.sh`;
  - `bsp-patches/`.
- LILYGO `Xinyuan-LilyGO/T-Display-K230` at tree `4a87c53c`:
  `k230_bsp/docs/HARDWARE_PINMAP.md`.
- In this repository:
  - `docs/dts-evidence.md`, the FPIOA table from the board's own RT-Smart
    configuration;
  - `docs/research/board-capability-inventory.md`, the UART3 conflict;
  - `nix/dts/k230-tdisplay-mainline.dts`, where the console is `serial0 = &uart0`.

### Facts this design rests on

**Wiring.**
- Enable is K230 IO2, high = on. SWD also needs it high.
- The AT link is K230 UART3 TX on IO28 to nRF P0.26, and RX on IO29 from nRF
  P0.27, at 115200 8N1.
- There is no RTS/CTS, DTR or RI. There is no interrupt or wake line.

**Firmware.**
- Nordic Serial LTE Modem from NCS v3.4.0, LILYGO profile `serial_modem_k230`.
  The vendor source names modem firmware `mfw_nrf91x1_2.0.4`; the unit
  probed on 2026-10-13 reports `mfw_nrf91x1_2.0.3` (`AT+CGMR`) under Serial
  LTE Modem 2.9.0 (`AT#XSLMVER`; `AT#XSMVER` answers `ERROR`). See
  `docs/evidence/nrf9151/probe/`. Its configuration:

  | Setting | Value |
  | --- | --- |
  | `CONFIG_SM_AUTO_CONNECT` | `y`, system mode `"1,1,1,0"` (LTE-M, NB-IoT and GNSS) |
  | `CONFIG_SM_SMS` | `y` |
  | `CONFIG_SM_GNSS` | `y`, with NMEA URCs on by default |
  | `CONFIG_SM_PPP` | `n` |
  | `CONFIG_SM_CMUX` | `n` |

- LILYGO adds `AT#XNMEA=<0|1>`, which gives `#XGNSSNMEA:` URCs, and
  `AT#XK230LED`.

**Vendor recipes** (`AT_COMMANDS.MD`):
- SIM check: `AT+CFUN=1`, `AT%XSIM?`, `AT+CPIN?`. Expect `%XSIM: 1` and
  `+CPIN: READY`.
- GNSS: `AT#XNMEA=1`, `AT%XSYSTEMMODE=0,0,1,0`, `AT+CFUN=31`,
  `AT#XGNSS=1,0,0,0`. That is GNSS-only, with LTE off.

**UART3 pads.** UART3 is available on IO50/51 (wired to CH342 channel 1) and
IO28/29 (wired to the nRF). LILYGO's own kernel patch `0061` forces IO50/51
back to GPIO for this reason.

### GPIO arithmetic

| Pad | Bank line |
| --- | --- |
| IO2 | `gpio0 2` |
| IO28 | `gpio0 28` |
| IO29 | `gpio0 29` |
| IO50 | `gpio1 18` |
| IO51 | `gpio1 19` |

## Goals / Non-Goals

**Goals:**
- Linux owns the modem's power and AT link safely.
- Status, SMS and location reach the shell and ordinary location clients.
- The modem is off by default.
- The console is preserved.

**Non-goals:** see the proposal. In particular, no mobile data and no
firmware changes.

## Decisions

### 1. UART3 moves to IO28/29; channel 1 is given up (device tree)

The pinctrl node (shared with the keyboard-base change) gets three states:

| Pads | State | Effect |
| --- | --- | --- |
| IO28/29 | UART3 | The modem link. |
| IO50/51 | GPIO input | Channel 1 is quiet and cannot back-drive. |
| IO2 | GPIO output, default low | The modem's enable line. |

`&uart3` is enabled with `uart3` and the IO28/29 state as its pinctrl default.
The console stays UART0 on IO38/39.

**Rejected:**
- Keeping IO50/51 on UART3 for a second console. Nothing here uses it, and the
  modem needs the peripheral.
- Bit-banging or a software UART. There is no K230 support for one, and 115200
  baud on one core is not credible.

### 2. One service owns the modem (userspace)

`k230-modem` is a Rust system service, built with the same toolchain as the
shell client. It is the only process that opens `/dev/ttyS3` or the enable
line.

- It requests `gpio0 2` through the GPIO character device.
- It runs a line-oriented AT state machine. Every command has a timeout and
  one command is in flight at a time. URCs are parsed between commands.
- It publishes `/run/k230/modem/state.json`, written atomically:

  | Field | Contents |
  | --- | --- |
  | `power` | modem power |
  | `sim` | SIM state |
  | `registration` | registration state |
  | `operator` | network operator |
  | `rat` | access technology |
  | `rsrp` / `bars` | signal |
  | `gnss` | location state |
  | `last_error` | most recent error |

- It accepts newline-delimited commands on `/run/k230/modem/control`, a socket
  restricted to the shell user's group: `power on|off`, `pin <digits>`,
  `gnss on|off`, `sms send <number>` with the body on stdin, and `status`.
- `k230-modemctl` is the command-line client.

The shell reads the state file and writes commands to the socket. No other
code speaks AT.

**Rejected:**
- **ModemManager.** It has no Serial LTE Modem plugin. Its generic AT probing
  of a no-flow-control UART would race our state and could flip `CFUN`.
- **LILYGO's userspace,** whose launcher drives the modem from LVGL code. It
  is not a service, and it is not separable from that UI.
- **Several processes sharing the tty.** Interleaved AT exchanges corrupt each
  other with no flow control.

### 3. Off by default, and power changes are explicit

At boot the enable line is driven low and the service reports `off`.
"Cellular on" or "Location on", persisted in `/var/lib/k230/modem/settings.json`,
powers the modem.

Because the firmware auto-connects, power on means:
1. enable high;
2. wait for the firmware's ready line, or time out;
3. `AT+CFUN?`;
4. then the mode the person asked for.

Location-only issues the vendor's GNSS-only recipe immediately, so LTE never
attaches. Power off sends `AT+CFUN=0`, waits for `OK` with a timeout, then
drives the enable line low.

### 4. The SIM PIN is a secret

A PIN reaches the service only over the control socket. It is sent once as
`AT+CPIN=` and is never logged, written to state or the journal, or persisted.
The AT trace redacts that command's argument. This follows AGENTS.md: secrets
are never committed and pass only through the designated protected path. Here
that path is the socket, and nothing is stored.

### 5. SMS (userspace)

- On power-up the service selects text mode, `AT+CMGF=1`. `AT+CNMI` routes new
  messages as `+CMT` URCs.
- Each message becomes a shell notification with sender and body. The
  notification center's existing privacy default hides the body in the
  preview.
- Received messages are kept in a bounded store,
  `/var/lib/k230/modem/sms.jsonl`, with the last 200 messages, readable only by
  the shell user. The person can clear it from Settings.
- Sending goes through `AT+CMGS`.
- Concatenated (multi-part) messages are joined when their headers allow, and
  otherwise kept as separate parts.

### 6. GNSS through `gpsd` (userspace, Nix)

The service writes `#XGNSSNMEA:` payloads, stripped of the prefix, to a pty at
`/run/k230/modem/nmea`. `gpsd` is started on demand against that pty, so any
`gpsd` client works.

GNSS and LTE share one radio. On the nRF91, GNSS runs only while LTE is idle,
or with LTE off:
- Location alone uses the vendor's GNSS-only recipe, which gives the fastest
  fix.
- Location while Cellular is on uses system mode `1,1,1,0` with `AT#XGNSS`, and
  accepts slower or interrupted fixes. The UI says "searching" honestly rather
  than inventing a position.

No position is written to disk by the service.

**Rejected:**
- A private location API. `gpsd` is the established interface, and maps and
  CLI tools already speak it.
- nRF Cloud A-GNSS. It needs a data path and an account, both out of scope.

### 7. Considered and deferred

- **Mobile data.** Option (a) is a PPP+CMUX firmware build flashed over SWD
  with pyOCD (`FLASH_PYOCD.MD`), then `pppd` over a CMUX channel. That needs
  the SWD pads and a recovery story, so it is a successor proposal. Option (b)
  is the firmware's socket and HTTP AT commands. That is not a Linux network
  interface, and it is rejected for general data.
- **Network time** (`AT+CCLK?`) when NTP is unreachable. It is small, but it
  touches `system/rtc` policy and is better proposed with the RTC work.

## Risks / Trade-offs

- **No flow control.** The UART is at 115200 with no flow control, so NMEA
  bursts at 1 Hz with satellites enabled could overrun. Mitigation: measure
  the URC rate in the probe. If needed, disable satellite sentences
  (`AT#XNMEA`) or lower the rate.
- **The second console channel is lost.** Mitigation: it is documented here,
  and the first boot re-checks channel 0.
- **Auto-connect** could attach to a network before the service sets the
  mode. Mitigation: the service's first command after power-on fixes the mode.
  The probe measures how quickly the firmware attaches. If that is faster than
  the service, the vendor's GNSS-only path still holds, because LTE attach
  needs a SIM and an antenna.
- **Antennas and SIM are unknown.** Cellular groups that need them stay open
  until one is fitted. The probe records what exists.
- **Power.** The modem draws from the base battery. Off by default limits
  this, and the battery change makes the draw visible.

## Open Questions

- IO2's level before Linux takes it: U-Boot's default, pulled or floating.
- Which antennas are fitted (LTE, GNSS, any LNA). Whether a SIM is present, and
  which kind.
- ~~Exact firmware and modem-firmware versions on this unit~~ Answered by the
  probe: modem firmware 2.0.3, Serial LTE Modem 2.9.0.

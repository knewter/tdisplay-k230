## Why

Away from Wi-Fi, the handheld cannot tell a person whether there is cell
coverage. It cannot receive a text message, and it cannot say where it is. The
keyboard base already carries a cellular and GNSS modem, a Nordic nRF9151
running LILYGO's build of Nordic's Serial LTE Modem firmware. Linux never
powers it or talks to it, so none of this works.

There is also a cost to leaving it unmanaged. The vendor firmware is built to
attach to the network on its own as soon as it is powered (`CONFIG_SM_AUTO_CONNECT=y`
in `serial_modem_k230/k230_serial_modem.conf`). Using the modem therefore has
to start from a deliberate "off until the person turns it on".

The modem talks AT commands over one UART with no flow control and no wake
line (the firmware overlay: "The K230 board does not route RTS/CTS or DTR/RI").
That UART is the K230's UART3. This board's second console bridge channel is
also wired to UART3, on different pads (`docs/dts-evidence.md`: IO50/51 =
UART3, CH342 channel 1). Only one pad group can carry UART3, and this proposal
says plainly which loses. Under the mainline kernel the Linux console is UART0
on IO38/39 (CH342 channel 0), and nothing in this repository uses channel 1. So
the modem takes UART3, channel 1 goes quiet, and the console that `tools/`
uses is unaffected.

## What Changes

- **Probe first, read-only.** With the modem powered through its enable line,
  record:
  - the firmware and modem-firmware versions;
  - SIM presence;
  - whether antennas are fitted;
  - the state of the enable pad at boot.

  No firmware is changed.
- **Device tree.** Mux IO28/29 to UART3, release IO50/51 from UART3, enable
  `uart3`, and name the modem's enable line.
- **One modem owner.** A small `k230-modem` system service is the only
  process that opens the modem's UART:
  - it powers the modem on and off;
  - it tracks SIM, registration, operator, access technology and signal;
  - it relays incoming SMS;
  - it turns GNSS on and off.

  Its state goes to a small file under `/run` and its commands come through a
  local socket, so the shell never speaks AT.
- **Location.** GNSS NMEA from the modem feeds `gpsd`, so any location-aware
  program can use it.
- **Shell use.**
  - The shade shows a signal indicator and a location indicator when the modem
    is on.
  - Settings gains Cellular and Location pages: on/off, SIM state, SIM PIN
    entry, operator and signal detail.
  - An incoming text raises a privacy-safe notification.
  - Sending a text is a command-line action in this change.
- **Off by default.** The modem stays unpowered at boot until the person turns
  Cellular or Location on. That choice persists in system state.

## Non-goals

- **Mobile data (an IP link).** The installed firmware is built with
  `CONFIG_SM_PPP=n` and `CONFIG_SM_CMUX=n`, so Linux cannot get a network
  interface from it. Data needs a reflash over SWD, from pads inside the base,
  to a PPP+CMUX build. That reflash is a successor proposal, not part of this
  one.
- Reflashing or reconfiguring the nRF9151 firmware or modem firmware in any
  way.
- Voice calls. The nRF9151 has no voice path.
- A messaging app. Receive-and-notify plus command-line send is the bound
  here.
- nRF Cloud A-GNSS, or any other cloud location assistance.
- Network time from the modem. It is considered in the design and deferred.
- The nRF52840 base and the keyboard base's other chips (see
  `the-keyboard-base-types-lights-and-reports-its-battery`).
- ModemManager integration.

## Capabilities

### New Capabilities

- `radio/cellular`: the modem's power, link, SIM, registration status and SMS,
  owned by one Linux service.
- `radio/gnss`: location from the modem's GNSS through `gpsd`, off unless
  asked for.

### Modified Capabilities

- `runtime/notification-center`:
  - incoming SMS as notifications under the existing privacy defaults;
  - cellular and location indicators in the shade.
- `runtime/device-settings`: Cellular and Location pages, shown only when the
  modem is present.

## Impact

- **Device tree:** the pinctrl node is shared with the keyboard-base change.
  If that change has not landed yet, this one adds it.
- **Kernel:** none expected. `SERIAL_8250_DW` already drives the UARTs.
- **Nix:**
  - the `k230-modem` service and its options;
  - `gpsd`;
  - a udev rule that keeps any modem manager off `ttyS3`.
- **Rust shell client:** the shade and Settings.
- **The console:** CH342 channel 1 (`/dev/ttyACM1` on the bench host) no
  longer carries UART3. Channel 0, the console, is unchanged. This must be
  re-checked on the first boot of the new device tree.
- **Needs the board.** Every radio claim needs the physical board with the
  base, plus a SIM and an antenna for the cellular parts, and sky view for
  GNSS. Host tests can drive the service against a recorded or fake AT
  transcript. QEMU cannot prove anything about the radio.
- **Stage 1 is untouched.**

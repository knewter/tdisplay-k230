Evidence classes are named per task: **host** (build or unit test against a
fake or recorded AT transcript), **board-read** (a command on the running
board), **camera**, **operator**, and **radio** (a real network or sky
event). Host results never tick a board or radio task.

Committed evidence never contains any of the following. They are replaced
with `<redacted>` and the redaction is noted:

- SIM PINs;
- phone numbers;
- the IMSI or ICCID;
- message bodies other than a fixed test string;
- coordinates.

## 1. Read-only probe (board)

- [ ] 1.1 Write `tools/nrf9151-probe.sh`. It records IO2's level and the IOMUX
  words for IO2/IO28/IO29/IO50/IO51, then drives IO2 high. For the probe
  only, it switches IO28/29 to UART3 through a runtime path, recorded in the
  script. It then sends only queries:
  - `AT`, `AT+CGMR` and the firmware's version command;
  - `AT+CFUN?`;
  - `AT+CFUN=1`, then `AT%XSIM?`, `AT+CPIN?`, `AT+CEREG?`, `AT+COPS?`
    and `AT+CESQ`;
  - then `AT+CFUN=0` and IO2 low.

  It prints how long the firmware takes after power-on to issue its own
  network attach. Proof (**host**): `bash -n` plus a review that the script
  writes no non-volatile modem setting.
- [ ] 1.2 Run it on the board, holding `flock /tmp/k230-board.lock`, and
  commit the redacted output to `docs/evidence/nrf9151/probe/`. Also commit
  the operator's notes on the fitted antennas and SIM, with a **camera** frame
  of the base's antenna connectors if visible.
- [ ] 1.3 With GNSS on, using the vendor recipe for 60 s, measure the NMEA URC
  byte rate against 115200 baud and record any framing errors from
  `/proc/tty/driver/serial`. Proof (**board-read**).

## 2. Device tree (device tree)

- [ ] 2.1 Add the IO28/29 UART3, IO50/51 GPIO-input and IO2 GPIO states to the
  shared pinctrl node, enable `&uart3`, and name IO2's line `nrf9151-enable`.
  Proof (**host**): `nix build .#deviceTreeMainlineDrm`.
- [ ] 2.2 Push the DTB with
  `tools/push-file.py --src <dtb> --dest /boot/k230-tdisplay.dtb --reboot`.
  Record:
  - console channel 0 logging in;
  - `/dev/ttyS3` present;
  - `AT` answered through `microcom` with IO2 high;
  - channel 1 silent.

  Proof (**board-read**): `docs/evidence/nrf9151/uart/`.

## 3. The modem service (userspace, Nix)

- [ ] 3.1 Write `k230-modem` and `k230-modemctl` in Rust, covering:
  - the AT state machine, with timeouts and URC parsing;
  - the atomic `state.json`;
  - the control socket;
  - power sequencing (Decision 3);
  - PIN redaction;
  - SMS text mode, store and send;
  - the NMEA pty;
  - the one-per-minute recovery.

  Proof (**host**): `cargo test` against recorded transcripts. The
  transcripts include no SIM, PIN-required, a wrong PIN, registered, a
  timeout, an inbound `+CMT`, a multi-part SMS, and an NMEA burst. A test
  asserts that the PIN never appears in any log or state output.
- [ ] 3.2 Add the NixOS module: the service, its group, `/var/lib/k230/modem`,
  `gpsd` started on demand against the pty, and a udev rule tagging `ttyS3`
  `ID_MM_DEVICE_IGNORE`. Defaults are Cellular off and Location off. Proof
  (**host**):
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape.config.system.build.toplevel`.
- [ ] 3.3 Install on the board. Record:
  - after a fresh boot: enable low and state `off` (**board-read**);
  - `k230-modemctl power on`, then `status` without a SIM or with one, per
    1.2 (**board-read**);
  - `k230-modemctl power off` returning the enable line low (**board-read**);
  - a second process refused `/dev/ttyS3` (**board-read**).

  Proof: `docs/evidence/nrf9151/service/`.

## 4. Cellular status, PIN and SMS (board, radio)

These tasks need a SIM and an LTE antenna. They stay open until both are
fitted.

- [ ] 4.1 Registration: record the operator, the access technology, and
  `bars` agreeing with `AT+CESQ`. Proof (**radio**).
- [ ] 4.2 If the SIM has a PIN: unlock it through Settings, then
  `grep -r <digits>` over the journal and `/var/lib/k230`, which must find
  nothing. The digits are never written into evidence; the grep is run with
  the PIN from a protected file and only its exit status is recorded. Proof
  (**board-read**).
- [ ] 4.3 SMS: receive a fixed test string, shown as a notification in a
  native capture and a **camera** frame, then send one with `k230-modemctl`.
  The operator confirms delivery. Proof (**radio** + **operator**).

## 5. Location (board, radio)

These tasks need a GNSS antenna and sky view.

- [ ] 5.1 With Location on and Cellular off, record the time to first fix and
  the `gpspipe -w` fix class. The operator confirms the position is within
  100 m of their known location; coordinates are not committed. Proof
  (**radio** + **operator**).
- [ ] 5.2 With both on, record registration kept and the location state
  sequence. Proof (**radio**).
- [ ] 5.3 After the session, grep `/var` and the journal for coordinate
  patterns, which must find nothing. Proof (**board-read**).

## 6. Shell use (Rust shell client)

- [ ] 6.1 Add the shade's cellular and location indicators, the Settings
  Cellular and Location pages, PIN entry, and clearing stored messages. All
  of them are hidden until the modem has answered once. Proof (**host**):
  `cargo test` in `nix/rust-shell-client`, plus host renders from fake state
  files at 568x1232 and 1232x568.
- [ ] 6.2 Route the service's SMS events to the notification center with the
  hidden-body preview. Proof (**host**): a test feeding a fake SMS event.
- [ ] 6.3 On the board, capture with `grim`: the shade indicators, both
  Settings pages, and an SMS preview and history entry. Record the operator
  turning Location on through Settings and the choice surviving a reboot.
  Proof (**board-read** + **operator**): `docs/evidence/nrf9151/shell/`.

## 7. Close

- [ ] 7.1 Run
  `openspec validate the-nrf9151-gives-the-handheld-cellular-sms-and-location --strict`
  and `python3 tools/blob-scan.py --no-vendor`. Merge, push, and check CI and
  the published spec pages. Archive only when every task has its named proof.
  Mobile data stays in a successor proposal.

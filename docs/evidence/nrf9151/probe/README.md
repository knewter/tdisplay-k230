# nRF9151 read-only probe (tasks 1.1, 1.2 partial)

Evidence class: **board-read**.

`probe-2026-10-13T235537Z.log` is the output of `tools/nrf9151-probe.sh`.
It was run as `bash /root/nrf9151-probe.sh` over SSH on the second board,
clipped into the keyboard base, while the host held
`flock /tmp/k230-board.lock`. The board ran system `iw5x7hn5…`, whose device
tree already has task 2.1's UART3 and `nrf9151-enable` states.

The script redacts as it writes, so the log carries no area code, cell ID
or operator. It never asks for the IMEI, ICCID, IMSI or number.

## What it shows

- **Enable line low:** `AT` got no answer within 2 s, so the modem is off
  while `nrf9151-enable` (IO2) is low. Before the probe the line was an
  unrequested input.
- **Enable line high:** the firmware prints `Ready` about 1.6 s later and
  `+CEREG: 90` about 0.3 s after that.
- **Radio on by itself:** `AT+CFUN?` reads `1` with no command from us, so
  the firmware switches the radio on by itself after power-on.
- **Firmware:**
  - `AT+CGMR` → `mfw_nrf91x1_2.0.3`;
  - `AT#XSLMVER` → `"2.9.0","2.9.0-cellular-a52f6a06a9e4"`;
  - `AT#XSMVER` → `ERROR`.

  So this unit runs the Serial LTE Modem 2.9.0 application on modem firmware
  2.0.3. The design's 2.0.4 is not what is installed here.
- **No SIM:**
  - `AT%XSIM?` → `%XSIM: 0,9`, SIM not initialised;
  - `AT+CPIN?` → `ERROR`;
  - `+CEREG: 5,90` and `+CEREG: 90`, where 90 means the SIM is unavailable;
  - `AT+COPS?` → `+COPS: 0`;
  - `AT+CESQ` → `99,99,255,255,255,255`, no measurement.

  So no SIM is fitted, or it is not detected.
- **Ending:** the probe ends with `AT+CFUN=4`, flight mode, then the enable
  line low. It does not use `AT+CFUN=0`: on the nRF91 that stores the
  modem's network context to flash, and the probe writes nothing
  non-volatile. After the probe the line is left an output, low.

## Still required for task 1.2

- The operator's notes on which antennas (LTE, GNSS) are fitted.
- Whether a SIM is present, with a camera frame of the antenna connectors if
  visible.

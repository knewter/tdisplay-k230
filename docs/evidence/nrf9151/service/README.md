# k230-modem on the board (nRF9151 task 3.3)

Evidence class: **board-read**. First board, landscape profile, system
`gcgvaz29zb5wk4d1sm8kygcrz13dpkk2-nixos-system-nixos-26.11.20260919.20b1ddd`
(built from `impl/nrf9151-service` at "Set the modem UART to 115200 under
glibc 2.42 …"). No SIM is fitted (see `../probe/`), so the cellular path stops
at `sim: absent`. Captured 2026-10-14 00:57 UTC, holding the board lock.

`board-2026-10-14.txt` is the whole capture. The commands, as root on the
board:

```
C="runuser -u shell -- k230-modemctl"
grep nrf9151-enable /sys/kernel/debug/gpio; cat /run/k230/modem/state.json
$C power on; $C status
setpriv --reuid=nobody --regid=dialout --clear-groups -- sh -c 'exec 3<>/dev/ttyS3'
$C power off; grep nrf9151-enable /sys/kernel/debug/gpio
journalctl -b -u k230-modem
```

| Requirement | Observed |
| --- | --- |
| After a fresh boot: enable low, state `off` | `gpio-2 (nrf9151-enable |k230-modem) out lo`; `"power":"off"` |
| `power on`, then `status` without a SIM | `Ready` 1 s after the request; `"power":"on","present":true,"sim":"absent","registration":"sim_failure"`, firmware `mfw_nrf91x1_2.0.3`, SLM `2.9.0`; enable `out hi` |
| `power off` returns the enable line low | `AT+CFUN=0` then `out lo`; `"power":"off"` |
| A second process refused `/dev/ttyS3` | uid `nobody`, gid `dialout` (the device is `root:dialout 0660`): `Device or resource busy` (`TIOCEXCL`). Root bypasses `TIOCEXCL` by design, so the test uses an unprivileged opener |

The `shell` user ran `k230-modemctl` through the control socket, which shows
the `k230-modem` group grant works.

## The first deploy failed, and why

The first image (`cfc847ae`) timed out: the modem never answered `AT`, and
`stty -F /dev/ttyS3` read `speed 4098 baud` afterwards. glibc 2.42 reads
`speed_t` as the plain baud rate, so the Rust `libc` crate's legacy
`B115200` (0o010002 = 4098) set 4098 baud. The read-only probe still worked
in the same boot, so the hardware was fine. The fix tries `cfsetspeed(115200)`
and falls back to the constant on older glibc. Commands now also end in CR LF,
as the probe's do. Host transcript tests cannot see a baud rate, which is why
they passed.

## Limits

- No SIM: PIN, registration, signal and SMS stay unexercised on the radio
  (tasks 4.x).
- `AT+CMGF=1` and `AT+CNMI` answered `+CMS ERROR: 302` (operation not
  allowed) and `AT+CSDH=1` `ERROR`, so the service set
  `last_error: sms_unavailable`. Without a SIM this does not show whether the
  firmware supports text-mode SMS; task 4.x must re-check with a SIM.
- GNSS (`gnss on`) was not exercised: no GPS antenna or sky view is
  confirmed (tasks 5.x).
- The service log withholds the tracking area and cell id from `+CEREG`
  lines and any identity answer; with no SIM, none appeared here.

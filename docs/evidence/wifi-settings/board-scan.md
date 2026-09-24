# Installed Wi-Fi broker scan

On 24 September 2026, the reserved physical board running source `df2c34b18e39fa2b1b5da6a024d830241d38235d`, system `/nix/store/lxi2zx8n8mp7z1dl1i3dz7hjlbhl7f6l-nixos-system-nixos-26.11.20260919.20b1ddd`, answered a read-only Settings broker scan from the shell UID. The broker service was active.

[Allowlisted result](board-scan.json): schema 1, state ok, no error, current connection present, one saved profile, one visible network, WPA2-PSK security. SSIDs, addresses, passphrases and raw radio output were never exported. This confirms the existing protected configuration is compatible with the parser and the real radio scan path works.

The operator held `/tmp/k230-board.lock` and used the console to invoke the installed Python as `shell`. The request on `/run/k230-wifi-settings/broker.sock` was exactly:

```json
{"schema":1,"op":"scan"}
```

The private helper used a 20-second socket deadline and 16-KiB response bound, then emitted only schema/state/error, a Boolean connection indicator, counts and security kinds. The installed broker ran fixed `ip link set dev wlan0 up` and `iw dev wlan0 scan`; no connect/forget operation was requested.

This is physical radio/socket proof, not Settings touch UI, association/change/cancel/Forget or reboot persistence acceptance. Those tasks remain open.

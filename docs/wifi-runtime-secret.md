# One-off Wi-Fi runtime secret procedure

This procedure is for the board operator at the root console after the
credential-free readiness check has found `WIFI_IFACE`. It is a one-off
connection procedure, not persistent configuration. The protected network
configuration remains outside Git, the Nix store, and NixOS configuration.

Use these environment variable names in the private operator session:

```sh
export RUNTIME_SECRET_FILE=/path/known-only-to-root.conf
export WIFI_IFACE=discovered-wireless-interface
```

Create `RUNTIME_SECRET_FILE` privately with mode `0600`. Its `network` stanza
contains the operator's network name and key; documentation may refer to that
name only as `YOUR_SSID`. Do not put the network name or key into shell
history, a command line, source control, a Nix expression, terminal capture,
or this file. Do not print the protected file.

Before association, verify ownership and permissions, then copy it to the
root-owned runtime filesystem. The supplicant reads only the copied `/run`
file, so neither its command line nor its Nix closure carries the secret.

```sh
set -eu
: "${RUNTIME_SECRET_FILE:?set RUNTIME_SECRET_FILE}"
: "${WIFI_IFACE:?set WIFI_IFACE}"
test "$(id -u)" -eq 0
test "$(stat -c '%a' "$RUNTIME_SECRET_FILE")" = 600
install -o root -g root -m 0600 "$RUNTIME_SECRET_FILE" \
  /run/wpa-supplicant-board.conf
wpa_supplicant -B -i "$WIFI_IFACE" -c /run/wpa-supplicant-board.conf
```

The operator may inspect a sanitized association state with
`wpa_cli -i "$WIFI_IFACE" status`, omitting network names and BSSIDs from any
record. The later DHCP and routing checks use the same `WIFI_IFACE`.

Stop the temporary connection and remove the copied runtime secret on failure
or when finished:

```sh
wpa_cli -i "$WIFI_IFACE" terminate || true
rm -f /run/wpa-supplicant-board.conf
```

`RUNTIME_SECRET_FILE` is operator-owned input and is not removed by this
procedure. Its secure removal path is the operator's local policy. No
persistent secret mechanism is selected until a live board connection has
succeeded.

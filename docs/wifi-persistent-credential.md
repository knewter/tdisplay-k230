# Persistent Wi-Fi credential procedure

This optional procedure enables automatic reconnect for the tested `wlan0`
path. It follows a successful one-off connection and does not change the
credential-free default image: `k230-wifi.service` is skipped unless the
root-owned file below exists.

The only persistent credential location is
`/var/lib/k230/wifi/wpa_supplicant.conf`. It and both parent directories are
owned by root; the directories are mode `0700` and the file is mode `0600`.
The file stays outside Git, Nix expressions, generated Nix configuration, and
the Nix store. At each service start, systemd reads it through `LoadCredential`
and exposes a per-service copy at
`$CREDENTIALS_DIRECTORY/wpa_supplicant.conf`. The supplicant receives that
runtime copy, never a secret in its command line.

Before provisioning, stop and clean up any one-off connection using the
explicit completion block in [the runtime procedure](wifi-runtime-secret.md).
That procedure manages `wlan0` too, so the two supplicants must not run at the
same time. The persistent service uses separate runtime state beneath
`/run/k230-wifi`.

In a private root session, make a root-owned mode-`0600` source file and set
its pathname without printing the file. It contains the protected `network`
stanza and this non-secret control directive outside that stanza:

```text
ctrl_interface=DIR=/run/k230-wifi/wpa_supplicant GROUP=root
```

Use placeholders only in any recorded procedure:

```sh
export PERSISTENT_SECRET_FILE=/path/known-only-to-root.conf
```

Provision and start the service as root. The checks prevent a non-root or
over-permissive input from being copied. `dhcpcd.service` is already enabled
for the system and obtains a lease when the persistent supplicant associates;
the Wi-Fi service does not launch a second DHCP client.

```sh
(
  set -eu
  : "${PERSISTENT_SECRET_FILE:?set PERSISTENT_SECRET_FILE}"
  persistent_conf=/var/lib/k230/wifi/wpa_supplicant.conf
  ctrl_dir=/run/k230-wifi/wpa_supplicant

  test "$(id -u)" -eq 0
  test "$(stat -c '%u' "$PERSISTENT_SECRET_FILE")" -eq 0
  test "$(stat -c '%a' "$PERSISTENT_SECRET_FILE")" = 600
  grep -F -x -- "ctrl_interface=DIR=$ctrl_dir GROUP=root" \
    "$PERSISTENT_SECRET_FILE" >/dev/null

  systemctl stop k230-wifi.service
  install -d -o root -g root -m 0700 /var/lib/k230/wifi
  install -o root -g root -m 0600 "$PERSISTENT_SECRET_FILE" "$persistent_conf"
  systemctl start k230-wifi.service
)
```

`k230-wifi.service` waits for the `wlan0` device, creates root-only
`/run/k230-wifi/wpa_supplicant/client` and a mode-`0600` log, then runs the
supplicant in the foreground for systemd. It restarts after a process failure;
the supplicant itself handles normal reassociation. It starts before
`network-online.target`; `dhcpcd.service` starts independently and handles the
interface after association. A reboot with the credential file present is the
physical-board validation for task 4.2, not a result established here.

To query a sanitized state during that validation, use the service-specific
control path and omit network names and BSSIDs from anything recorded:

```sh
wpa_cli -p /run/k230-wifi/wpa_supplicant -i wlan0 status
```

To remove persistent access, stop the service before deleting its source
credential. This disables automatic reconnect on the next boot; it does not
delete the operator's private source file.

```sh
(
  set -eu
  test "$(id -u)" -eq 0
  systemctl stop k230-wifi.service
  rm -f /var/lib/k230/wifi/wpa_supplicant.conf
  systemctl reset-failed k230-wifi.service
)
```

The root-owned empty directories may remain. Their contents never enter the
system closure, and the service condition keeps a credential-free boot normal.

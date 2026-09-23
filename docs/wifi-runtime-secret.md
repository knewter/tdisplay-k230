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

The same protected file must also contain this non-secret control directive,
outside its `network` stanza. It gives the one-off daemon a root-only control
socket directory; it does not persist a connection or disclose a network.

```text
ctrl_interface=DIR=/run/wpa_supplicant GROUP=root
```

Before association, verify ownership and permissions, then copy it to the
root-owned runtime filesystem. Run this block as a root subshell. Its failure
trap removes the copied secret and, if the launched daemon wrote its PID file,
terminates only that PID after confirming its command line names this exact
`/run` configuration file. It cannot target an unrelated supplicant service.

The source file itself must be owned by UID 0 and have mode `0600`. The setup
also refuses existing runtime files before installing or trapping anything;
the operator must explicitly complete or investigate a previous invocation
rather than overwriting a possibly active connection.

The supplicant reads only the copied `/run` file, so neither its command line
nor its Nix closure carries the secret.

```sh
(
  set -eu
  : "${RUNTIME_SECRET_FILE:?set RUNTIME_SECRET_FILE}"
  : "${WIFI_IFACE:?set WIFI_IFACE}"
  runtime_conf=/run/wpa-supplicant-board.conf
  runtime_pid=/run/wpa-supplicant-board.pid
  runtime_ctrl=/run/wpa_supplicant
  runtime_client=$runtime_ctrl/client
  runtime_log=/run/wpa-supplicant-board.log

  cleanup_failed_start() {
    trap - EXIT HUP INT TERM
    if test -r "$runtime_pid"; then
      board_pid=$(cat "$runtime_pid")
      case "$board_pid" in
        *[!0-9]*|'') ;;
        *)
          if test -r "/proc/$board_pid/cmdline" \
            && tr '\0' ' ' < "/proc/$board_pid/cmdline" \
                 | grep -F -- "$runtime_conf" >/dev/null; then
            kill "$board_pid" || true
          fi
          ;;
      esac
    fi
    rm -rf "$runtime_ctrl"
    rm -f "$runtime_pid" "$runtime_conf" "$runtime_log"
  }

  # Do not overwrite a live or stale board invocation. This check is before
  # the trap, so a refusal cannot remove files this invocation does not own.
  if test -e "$runtime_pid" || test -L "$runtime_pid" \
    || test -e "$runtime_conf" || test -L "$runtime_conf" \
    || test -e "$runtime_ctrl" || test -L "$runtime_ctrl" \
    || test -e "$runtime_client" || test -L "$runtime_client" \
    || test -e "$runtime_log" || test -L "$runtime_log"; then
    echo "existing Wi-Fi runtime state; complete or investigate it first" >&2
    exit 1
  fi

  trap 'cleanup_failed_start' EXIT
  trap 'exit 1' HUP INT TERM
  test "$(id -u)" -eq 0
  test "$(stat -c '%u' "$RUNTIME_SECRET_FILE")" -eq 0
  test "$(stat -c '%a' "$RUNTIME_SECRET_FILE")" = 600
  install -o root -g root -m 0600 "$RUNTIME_SECRET_FILE" "$runtime_conf"
  grep -F -x -- "ctrl_interface=DIR=$runtime_ctrl GROUP=root" \
    "$runtime_conf" >/dev/null
  install -d -o root -g root -m 0700 "$runtime_ctrl"
  # wpa_cli creates its local client socket below this path.  The pinned
  # package does not create it, so create it before querying the daemon.
  install -d -o root -g root -m 0700 "$runtime_client"
  # The daemon can report network-specific state.  Keep its output off the
  # console and in a root-only runtime log that cleanup removes.
  install -o root -g root -m 0600 /dev/null "$runtime_log"
  wpa_supplicant -B -f "$runtime_log" -P "$runtime_pid" \
    -i "$WIFI_IFACE" -c "$runtime_conf"
  trap - EXIT HUP INT TERM
)
```

The operator may inspect a sanitized association state with
`wpa_cli -p /run/wpa_supplicant -i "$WIFI_IFACE" status`, omitting network
names and BSSIDs from any record. The explicit socket directory and its
root-only `client` subdirectory avoid depending on a package default. The
later DHCP and routing checks use the same `WIFI_IFACE`.

On explicit completion, stop only the daemon recorded in the board procedure's
PID file. The command-line check prevents a reused PID or another
`wpa_supplicant` service from being killed. It then removes the root-owned
runtime configuration, PID file, and control socket directory. If the recorded daemon already exited, the PID path has no
`/proc` entry, so the procedure removes this invocation's runtime files
without sending a signal. If a live PID does not name this configuration, it
refuses to touch either file.

```sh
(
  set -eu
  runtime_conf=/run/wpa-supplicant-board.conf
  runtime_pid=/run/wpa-supplicant-board.pid
  runtime_ctrl=/run/wpa_supplicant
  runtime_log=/run/wpa-supplicant-board.log
  test -r "$runtime_pid"
  board_pid=$(cat "$runtime_pid")
  case "$board_pid" in
    *[!0-9]*|'') exit 1 ;;
  esac

  if test -e "/proc/$board_pid"; then
    test -r "/proc/$board_pid/cmdline"
    tr '\0' ' ' < "/proc/$board_pid/cmdline" \
      | grep -F -- "$runtime_conf" >/dev/null
    kill "$board_pid" || true
  fi
  rm -rf "$runtime_ctrl"
  rm -f "$runtime_pid" "$runtime_conf" "$runtime_log"
)
```

`RUNTIME_SECRET_FILE` is operator-owned input and is not removed by this
procedure. Its secure removal path is the operator's local policy. No
persistent secret mechanism is selected until a live board connection has
succeeded.

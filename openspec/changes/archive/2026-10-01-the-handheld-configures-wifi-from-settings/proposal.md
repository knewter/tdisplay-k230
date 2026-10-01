## Why

A person can see only a read-only network-link row in Settings today. Joining or changing Wi-Fi requires a root console procedure, so the handheld cannot set up its own connection through touch.

## What Changes

- Make the Settings Network row open a touch-first Wi-Fi view with bounded scan results, current connection and saved-network state, progress, retry, and explicit Forget.
- Let a person tap an open or WPA2-Personal network and enter a masked passphrase with an on-screen keyboard. Persist accepted setup for automatic reconnect after reboot.
- Introduce a narrowly privileged Wi-Fi broker that alone accesses the existing root-private supplicant credential path and radio control; the unprivileged shell never receives saved credentials or passes them through process arguments, environment, logs, Nix, or evidence.
- Keep network discovery, authentication, DHCP, and Internet reachability distinct in status and failure text; a radio link does not imply Internet access.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `radio/wifi`: Add touch provisioning, saved-network management, and secret-safe service behavior to the existing protected runtime and persistent Wi-Fi capability.

## Impact

The system's Wi-Fi service and a protected broker, Settings backend, Rust shell service worker and Settings rendering, and focused host/QEMU and physical evidence. The broker reuses `/var/lib/k230/wifi/wpa_supplicant.conf` and the `k230-wifi.service` credential boundary. The coherent-shell Settings proposal remains the parent navigation and visual contract.

Open and WPA2-Personal networks on the existing `wlan0` path are in scope. Enterprise credentials, captive-portal login, hotspot mode, and hidden-network manual entry are not. Host tests and QEMU can prove parsing, state, focus, and touch behavior; only the physical board can prove scanning, association, reconnect after reboot, and real-glass keyboard usability. Those gates remain unverified until observed.

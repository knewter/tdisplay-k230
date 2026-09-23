## 1. Audit the missing radio path

- [x] 1.1 Compare the physical SDIO function in `docs/evidence/wifi-preflight.txt` with the exact 6.6.36 kernel source, configuration, loaded-module set, and the vendor RTL8189ES source; record the selected driver, compatible-ID support, license, immutable source revision, kernel API compatibility, and firmware requirement. Verify the audit cites each source and does not claim a bound board driver.
- [x] 1.2 Confirm whether the already-enumerated SDIO function needs an additional device-tree power control only after the driver audit; verify the conclusion against the board DTS and a credential-free board boot log rather than changing GPIOs by assumption.
- [x] 1.3 Expose a named, pinned `k230-wifi-driver` derivation for the audited driver and verify it with the narrow `nix build .#k230-wifi-driver`; coordinate any later system-image build separately, because a successful module build is not radio proof.

## 2. Make diagnosis and one-off association available

- [x] 2.1 Add the selected wireless driver plus `iw`, `wpa_supplicant`, `wpa_cli`, and regulatory data while retaining the existing DHCP client to the system closure; verify their paths with a narrow Nix evaluation and inspect the closure for no protected-network material.
- [x] 2.2 Write the root-only runtime-secret procedure using `RUNTIME_SECRET_FILE`, `WIFI_IFACE`, and `YOUR_SSID` placeholders only; verify the procedure passes the configuration file from `/run` with mode `0600` and never places a secret in argv, source control, or Nix configuration.
- [x] 2.3 On the physical board, run credential-free readiness checks for SDIO enumeration, bound driver, `iw dev`, and regulatory state before any scan or connection attempt; commit only sanitized evidence and verify it omits MAC addresses, access-point identifiers, local addresses, and terminal control sequences.

## 3. Prove a live connection on the physical board

- [x] 3.1 With the board operator's protected runtime configuration already present, start `wpa_supplicant` for the discovered `WIFI_IFACE` from `RUNTIME_SECRET_FILE`; verify association with a sanitized state result and remove the runtime secret on failure or cleanup. Do not record the invocation with a real network identifier or secret.
- [x] 3.2 Request an IPv4 lease on `WIFI_IFACE` using the selected DHCP client; verify a sanitized board record distinguishes successful address assignment from DHCP failure without exposing the assigned address.
- [x] 3.3 Validate routing, resolver routing, DNS, and outbound delivery separately: confirm the selected resolver's `ip route get` result uses `WIFI_IFACE`, then run `getent ahostsv4 "$TEST_DNS_NAME"` and `ping -4 -c 3 -I "$WIFI_IFACE" "$TEST_IP"`; commit sanitized evidence that records each stage's result, not raw network identifiers or addresses.
- [x] 3.4 Run the broader physical-board regression after association: confirm console access remains available, touch/display services remain responsive, and the temporary connection can be stopped without leaving a secret under `/run`; record a sanitized result in `docs/evidence/`.

## 4. Decide and verify persistent reconnection

- [x] 4.1 After a successful live connection, select a root-controlled runtime credential mechanism for persistence and document its ownership, permissions, service ordering, and removal path; verify source control and the Nix store still contain no protected-network configuration.
- [x] 4.2 On the physical board, reboot with the approved persistent mechanism and verify sanitized association, lease, route, resolver-route, DNS, and outbound-reachability results; if recovery is needed, use the established known-good image procedure for the custom hard-coded-DTB boot path rather than assuming generation rollback.

2026-09-22: `docs/evidence/offline-wifi-image/README.md` records the first
physical driver bind, runtime regulatory setup, protected one-off association,
DHCP, Wi-Fi resolver routing, DNS, interface-bound outbound delivery, shell
regression and secret cleanup. Persistent credential delivery and reboot
reconnection remain open; no network material enters declarative configuration.

2026-09-22: `docs/evidence/wifi-persistent/README.md` completes task 4.2.
The source-built image and service booted on the board; after private
provisioning, a second boot automatically passed all six network stages.
The systemd credential source remains root-owned 0600 outside the Nix store.

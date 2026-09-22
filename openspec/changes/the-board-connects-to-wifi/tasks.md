## 1. Audit the missing radio path

- [ ] 1.1 Compare the physical SDIO function in `docs/evidence/wifi-preflight.txt` with the exact 6.6.36 kernel source, configuration, loaded-module set, and the vendor RTL8189ES source; record the selected driver, compatible-ID support, license, immutable source revision, kernel API compatibility, and firmware requirement. Verify the audit cites each source and does not claim a bound board driver.
- [ ] 1.2 Confirm whether the already-enumerated SDIO function needs an additional device-tree power control only after the driver audit; verify the conclusion against the board DTS and a credential-free board boot log rather than changing GPIOs by assumption.
- [ ] 1.3 Add a pinned, reviewable package or kernel-module derivation for the audited driver and verify its narrow riscv64 derivation with `nix build .#nixosConfigurations.nixos.config.system.build.toplevel` only after coordinating an image build; a successful host build is not radio proof.

## 2. Make diagnosis and one-off association available

- [ ] 2.1 Add the selected wireless driver plus `iw`, `wpa_supplicant`, `wpa_cli`, regulatory data, and the audited DHCP client to the system closure; verify their paths with a narrow Nix evaluation and inspect the closure for no protected-network material.
- [ ] 2.2 Write the root-only runtime-secret procedure using `RUNTIME_SECRET_FILE`, `WIFI_IFACE`, and `YOUR_SSID` placeholders only; verify the procedure passes the configuration file from `/run` with mode `0600` and never places a secret in argv, source control, or Nix configuration.
- [ ] 2.3 On the physical board, run credential-free readiness checks for SDIO enumeration, bound driver, `iw dev`, and regulatory state before any scan or connection attempt; commit only sanitized evidence and verify it omits MAC addresses, access-point identifiers, local addresses, and terminal control sequences.

## 3. Prove a live connection on the physical board

- [ ] 3.1 With the board operator's protected runtime configuration already present, start `wpa_supplicant` for the discovered `WIFI_IFACE` from `RUNTIME_SECRET_FILE`; verify association with a sanitized state result and remove the runtime secret on failure or cleanup. Do not record the invocation with a real network identifier or secret.
- [ ] 3.2 Request an IPv4 lease on `WIFI_IFACE` using the selected DHCP client; verify a sanitized board record distinguishes successful address assignment from DHCP failure without exposing the assigned address.
- [ ] 3.3 Validate routing, DNS, and outbound delivery separately with `ip route` constrained to `WIFI_IFACE`, `getent ahostsv4 "$TEST_DNS_NAME"`, and `ping -4 -c 3 -I "$WIFI_IFACE" "$TEST_IP"`; commit sanitized evidence that records each stage's result, not raw network identifiers or addresses.
- [ ] 3.4 Run the broader physical-board regression after association: confirm console access remains available, touch/display services remain responsive, and the temporary connection can be stopped without leaving a secret under `/run`; record a sanitized result in `docs/evidence/`.

## 4. Decide and verify persistent reconnection

- [ ] 4.1 After a successful live connection, select a root-controlled runtime credential mechanism for persistence and document its ownership, permissions, service ordering, and removal path; verify source control and the Nix store still contain no protected-network configuration.
- [ ] 4.2 On the physical board, reboot with the approved persistent mechanism and verify sanitized association, lease, route, DNS, and outbound-reachability results; distinguish a successful reconnect from a host-only build or QEMU result.

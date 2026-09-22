## Context

The board routes its RTL8189FTV radio through SDIO. The current Xuantie 6.6.36
kernel configuration has generic wireless and MMC support, but its source and
module set do not include an RTL8189 SDIO driver. A private physical-board
preflight observed an SDIO function with no bound driver, no `ieee80211`
object, no wireless interface, no wireless command-line tools, and no
regulatory database. The sanitized evidence added with this proposal records
that gap. It is not proof of association or connectivity.

The device tree enables the SDIO controller but declares no separate radio
power regulator. Because the SDIO function enumerates, the initial work must
distinguish a missing driver from a power or board-routing fault before
changing power control. Vendor material names an RTL8189ES Linux driver tree,
but its exact compatibility, license, source revision, and module name still
require an audit.

The NixOS image is cross-built for riscv64. Host evaluation and a cross-build
can show that a closure includes selected packages or a module; only the board
can establish driver binding, association, DHCP, DNS, or packet delivery.

## Goals / Non-Goals

**Goals:**

- Give the board operator credential-free diagnostic steps that separate SDIO
enumeration, driver binding, regulatory state, association, address, route,
DNS, and packet delivery.
- Add the smallest driver and userspace path that can make the radio usable.
- Keep protected-network material outside Git, the Nix store, process
arguments, and committed evidence.
- Produce redacted board evidence for both success and failure states.

**Non-Goals:**

- A graphical network manager, access-point mode, Ethernet changes, cellular,
or stored network credentials in declarative Nix configuration.
- Treating RT-Smart vendor behavior, QEMU, a host build, or SDIO enumeration
as proof that Wi-Fi works.
- Changing stage 1, display, touch, AtomVM, or Dozer.

## Decisions

### Audit and add the radio path in layers

First audit the exact SDIO modalias against the current kernel source,
configuration, and the vendor RTL8189ES source. Select a source only if it
has a reviewable license and can be pinned by immutable revision and Nix hash.
Build it against the exact board kernel and record its module name and firmware
requirements. The private preflight makes a missing driver the leading cause,
but an audit must still rule out a wrong compatible-ID table or an independent
power requirement.

Once the driver decision is made, add only the diagnostic and connection
programs needed on the console: `iw`, `wpa_supplicant`/`wpa_cli`, regulatory
data, and one DHCP client selected during the NixOS package audit. These tools
are absent from the current board image. A module load and `iw dev` check come
before any association attempt.

### Use a root-controlled runtime credential for one-off association

The board operator creates the protected network configuration by a private
runtime procedure and makes its file readable only by root. Tracked commands
refer only to `RUNTIME_SECRET_FILE` and `YOUR_SSID`; they never show a real
network identifier or secret-file contents. The procedure must avoid putting a
secret in shell history, argv, system configuration, the Nix store, or a
captured terminal log. `wpa_supplicant` receives the file from `/run` after
its permissions are checked.

The initial connection is deliberately imperative so that driver and network
failures are visible separately. A later persistent option is chosen only
after it works: a systemd credential delivery mechanism or an equivalently
root-controlled runtime file. Declarative wireless network definitions are
rejected because embedding a protected-network secret would copy it into the
Nix store.

For the physical-board operator, the minimal non-secret command shape is:

```sh
install -m 0600 "$RUNTIME_SECRET_FILE" /run/wpa-supplicant-board.conf
wpa_supplicant -B -i "$WIFI_IFACE" -c /run/wpa-supplicant-board.conf
dhcpcd -4 -w "$WIFI_IFACE"
ip route show default dev "$WIFI_IFACE"
getent ahostsv4 "$TEST_DNS_NAME"
ping -4 -c 3 -I "$WIFI_IFACE" "$TEST_IP"
```

`RUNTIME_SECRET_FILE` is prepared privately by the operator and is never
printed, recorded, or supplied as an argument. `WIFI_IFACE`, `TEST_DNS_NAME`,
and `TEST_IP` are discovered or selected at runtime. Cleanup terminates the
supplicant and removes the copied `/run` file.

### Validate in stages and redact evidence before committing it

The operator validates an associated interface in this order: interface and
association state, IPv4 address, default route bound to that interface, a DNS
lookup of an operator-supplied test name, and a reachability probe bound to
the interface and aimed at an operator-supplied test IP. This separates a
radio failure from DHCP, routing, DNS, and upstream failure.

Raw scans, WPA logs, status output carrying network names or BSSIDs, secret
files, and DHCP output with local addressing are not evidence artifacts.
Before committing, the operator reduces outputs to the relevant pass/fail
state, driver/interface information, and redacted identifiers. A failed stage
is evidence of that failure only; it never becomes a connectivity claim.

## Risks / Trade-offs

- The vendor driver can fail to build against 6.6.36 or lack the board's
  compatible ID. Pinning and cross-building it first catches this without a
  misleading hardware claim.
- SDIO enumeration proves the bus function responds, not that the radio is
  powered correctly, has firmware, or can transmit. Driver binding and live
  association remain board gates.
- Regulatory data is necessary for normal station behavior but does not cure
  a driver or antenna fault.
- Imperative one-off association leaves no automatic reconnect. This avoids
  committing a secret early; persistent reconnection is a later, explicitly
  tested decision.

## Migration Plan

1. Audit and package the driver and userspace tools without credential material.
2. Build the affected system derivation and install it only through the normal
   board image/update process.
3. Run the staged physical-board checks, then perform one protected runtime
   connection.
4. If any board stage fails, stop the connection service, remove its `/run`
   file, and roll back to the prior system generation. No persistent network
   configuration is introduced before a successful live validation.

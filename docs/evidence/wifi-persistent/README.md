# Persistent Wi-Fi on the physical board

Host date: 2026-09-22 America/Chicago (2026-09-23 UTC).

The [image record](image.json) identifies the declarative service image built
from `45e5e1a`. UMS wrote 2,308,751,360 bytes successfully in 186.5 seconds.
No full-image readback was requested. The flashing harness ended with status
143 during Linux startup, so its own final boot verdict is incomplete; the
independent [fresh-boot console record](fresh-boot.txt) confirms the new system,
boot ID, and active shell, seatd and firewall.

That fresh image contained no Wi-Fi credential. The service condition skipped
startup as intended; its state was inactive, not failed. The driver log level
was 0, and the persistent directories were root-owned mode 0700.

The operator-authorized credential was transferred through non-echoing serial
input into a mode-0600 runtime source, then installed root-owned mode 0600 at
`/var/lib/k230/wifi/wpa_supplicant.conf`. The runtime source was removed.
The credential never entered Git, argv, Nix expressions or the Nix store.
The image supplies the service; systemd `LoadCredential` supplies the private
runtime copy. The existing dhcpcd service remains the only DHCP client.

[Before reboot](before-reboot.txt), association, address assignment, default
route, resolver route, DNS lookup and interface-bound outbound ping all passed.
The first immediate check raced association and also exposed the pinned
wpa_cli client's separate default socket path. The documented `-s` option now
selects the service's private client directory explicitly; this is a diagnostic
command fix, not a service or connection change.

A real warm reboot on USB power followed. No credential was re-provisioned and
no manual supplicant start or DHCP request was issued after it. Sanitized
post-reboot results and identity are recorded alongside this note. The board
is left connected for the operator.

The source credential is intentional, root-controlled persistent state;
application defaults still come from the image. Reboot retains it. Replacing
the whole SD image does not retain it. Removal instructions are in
[the credential procedure](../../wifi-persistent-credential.md).

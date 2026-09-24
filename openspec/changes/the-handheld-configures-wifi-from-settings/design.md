## Context

See proposal.md. `nix/hardware.nix` already defines `k230-wifi.service`: `wlan0`, root-private `/var/lib/k230/wifi/wpa_supplicant.conf`, systemd `LoadCredential`, and a root-only supplicant control directory. `tools/device_settings.py` reports only link state. The Rust shell has an asynchronous Settings worker and touch-routed Settings panel. Existing physical evidence in `docs/evidence/wifi-persistent/` proves operator-installed persistence, not Settings-driven setup. Stage 1, kernel, device tree and radio driver remain unchanged.

## Goals / Non-Goals

**Goals:** A usable 568×1232 touch route, no terminal procedure in the user flow; strict secret and service ownership; bounded asynchronous work; safe coexistence with the already proven persistent service; inspectable host and physical gates.

**Non-Goals:** Enterprise/EAP, hidden-network manual entry, captive-portal login, hotspot mode, or a claim that association proves Internet access. Do not make the unprivileged shell a network administrator.

## Decisions

1. **A small root-owned userspace broker owns Wi-Fi changes.** A private local socket accepts bounded typed scan/status/connect/forget messages from the shell session UID, authenticates peer credentials, rate-limits scans and connection attempts, and emits bounded typed results. The service never shells out with SSIDs or passwords in argv; diagnostics use fixed error codes. The `wlan0` and root-only supplicant control paths remain authoritative. Rejected: direct `wpa_cli` from the shell (root-only socket and privilege), `sudo` from Settings (argv and authorization surface), or running a second supplicant (radio conflict).
2. **Only the root broker writes persistence.** It validates SSID bytes and supported security, writes a root-owned 0600 candidate file under `/run`, stops the existing service, and runs a private candidate supplicant for `wlan0`. It verifies candidate `COMPLETED` state before writing a root-owned 0600 temporary file in `/var/lib/k230/wifi`, fsyncing and atomically replacing the credential, then starts `k230-wifi.service` to consume its `LoadCredential` copy. Connection failure leaves prior configuration intact; start failure restores it. The initial UI manages one saved network at a time, including an existing single-network operator file; a successful change replaces it. The shell sees network names and statuses but never stored secrets. Rejected: simultaneous supplicants, home-directory persistence or passing a credential through Nix/systemd unit environment.
3. **The shell owns a Wi-Fi subview under Settings.** Network opens a list with current/saved badges, a refresh action, and tap selection. The selected WPA2-Personal entry opens a masked editor and an integrated touch keyboard; open networks skip password. Connect/Forget are explicit distinct actions. The editor has backspace, case/symbol pages, cancel and disabled/working states; the password buffer is cleared on exit, successful submit and route teardown. Worker requests carry monotonically increasing IDs, and the UI accepts only the active route's matching reply. Rejected: relying on external terminal or a Wayland keyboard aimed at a nonfocused layer surface. The integrated keyboard avoids stealing focus from the current app.
4. **Status is a staged state machine.** A scan result is not association; association is not DHCP or Internet. The backend reports radio unavailable, scan pending/empty/failure, connecting, authentication failure, association, and saved state independently. Timeout and cancellation do not claim success. Long-running requests stay off the Wayland loop and bounded queues coalesce scans; no secret enters debug formatting or UI error strings.
5. **A separate systemd recovery timer is armed before stopping the persistent service.** The candidate remains in the broker service cgroup. If the broker crashes or exceeds the bounded attempt window, the timer stops that cgroup, restarts the previously saved service, and restores the broker. A normal completion cancels the timer only after service restart. The timer's fixed arguments contain no network data.

## Risks / Trade-offs

- [Vendor driver scanning or control differs on the board] → keep scan/connect physical gates open, capture only sanitized status and real-glass observation, and preserve existing root operator path for recovery.
- [Power loss between association and persistence] → atomic root-private replacement; previous credential remains until a confirmed new connection.
- [Privilege broker reachable by an unrelated local client] → peer UID check, private socket directory, no broad group access, bounded requests and fixed commands.
- [Password remains in shell process memory during entry] → clear on route exit; do not clone into logs, history, argv or long-lived worker state. Process memory cannot be promised zeroized by ordinary Rust strings; avoid claiming that.
- [Long SSIDs, duplicates, or stale scans crowd the small display] → bounded rows, safe text layout, stable selection IDs and explicit refresh/retry; never select by truncated display text.
- [A configured operator file contains multiple network blocks] → leave its contents untouched on failed setup and report its saved identity as unknown; the first accepted Settings connection explicitly replaces it with the selected single-network configuration.

## Migration Plan

Add the broker and Settings client without changing the credential-free default or existing operator file format. Install and host-test the isolated package, then cross-build the full closure. The root operator activates a recovery-capable image and tests open/WPA2 connection, Forget and reboot reconnect on the physical board. Rollback disables the new broker and restores the previous image; the existing root-owned credential remains usable by the proven service.
